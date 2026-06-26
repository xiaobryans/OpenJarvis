"""Tests for the Option-A Stage 1 request tier classifier."""

import pytest

from openjarvis.orchestrator.request_classifier import (
    COMPLEX,
    FAST,
    INSTANT,
    STANDARD,
    classify_request,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        # INSTANT — trivial/direct
        ("hi", INSTANT),
        ("what time is it?", INSTANT),
        ("what day is it", INSTANT),
        ("what is my name?", INSTANT),
        ("thanks", INSTANT),
        ("who are you", INSTANT),
        # FAST — single bounded lookup/action
        ("what's the weather in Singapore", FAST),
        ("any important emails?", FAST),
        ("what's on my calendar today", FAST),
        # COMPLEX — build/creation
        ("build me a landing page for my plumbing business", COMPLEX),
        ("implement a REST API with auth and tests", COMPLEX),
        ("create a full stack web app for booking jobs", COMPLEX),
        ("fix the bug in the streaming handler", COMPLEX),
    ],
)
def test_tier_classification(text, expected):
    result = classify_request(text)
    assert result.tier == expected, (
        f"{text!r} -> {result.tier} (expected {expected}); reason={result.reason}"
    )


def test_multistep_is_standard_or_higher():
    r = classify_request(
        "summarize my unread emails and then draft replies to the urgent ones"
    )
    assert r.tier in (STANDARD, COMPLEX)


def test_result_has_audit_fields():
    r = classify_request("what's the weather")
    assert r.tier and r.reason and isinstance(r.signals, dict)
    assert "score" in r.signals


def test_empty_is_instant():
    assert classify_request("").tier == INSTANT
    assert classify_request("   ").tier == INSTANT


@pytest.mark.parametrize(
    "text",
    [
        # Real-world actions must reach the orchestrator (never INSTANT), or
        # the action tool never runs and Bryan gets a generic reply.
        "post to vanta-logs hello",
        "send a message to vanta-logs saying VANTA is live",
        "send a slack message to vanta-logs",
        "reply to that email",
        "schedule a meeting tomorrow at 3pm",
        "delete the dentist event",
        "email john that I am running late",
        "draft a reply to the last message",
    ],
)
def test_action_intent_never_instant(text):
    """Side-effecting action verbs must route through the orchestrator."""
    r = classify_request(text)
    assert r.tier != INSTANT, f"{text!r} wrongly classified INSTANT ({r.reason})"


@pytest.mark.parametrize(
    "text",
    ["what time is it", "hey", "what's my name", "who are you", "thanks"],
)
def test_genuine_instant_preserved(text):
    """Action detection must not over-trigger on trivial direct queries."""
    assert classify_request(text).tier == INSTANT
