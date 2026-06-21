"""Tests for cloud mobile auth flow and chat payload fixes.

Validates:
1. /mobile page includes API key input section.
2. /mobile page submitText() uses /v1/chat/completions (not /v1/company-org/task).
3. /mobile page includes Authorization header logic in submitText().
4. /mobile page includes model field in chat payload.
5. detect_coding_intent() does not classify conversational "Say X" prompts as coding.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.company_org_routes import router as mobile_router


@pytest.fixture(scope="module")
def mobile_client():
    app = FastAPI()
    app.include_router(mobile_router)
    return TestClient(app)


class TestMobilePageAuthAndPayload:
    def test_mobile_page_is_200(self, mobile_client):
        resp = mobile_client.get("/mobile")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_mobile_page_has_api_key_input(self, mobile_client):
        """Cloud mode requires API key input on the mobile page."""
        html = mobile_client.get("/mobile").text
        assert 'api-key-input' in html, "API key input element missing from /mobile"

    def test_mobile_page_has_save_api_key_function(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert 'saveApiKey' in html, "saveApiKey() function missing from /mobile"

    def test_mobile_page_submits_to_chat_completions(self, mobile_client):
        """submitText() must use /v1/chat/completions, not /v1/company-org/task."""
        html = mobile_client.get("/mobile").text
        assert '/v1/chat/completions' in html, (
            "submitText() must POST to /v1/chat/completions for cloud auth to work"
        )
        assert '/v1/company-org/task' not in html.split('submitText')[1].split('</script>')[0], (
            "submitText() must not use /v1/company-org/task"
        )

    def test_mobile_page_includes_authorization_header(self, mobile_client):
        """submitText() must set Authorization header from stored API key."""
        html = mobile_client.get("/mobile").text
        assert "Authorization" in html, (
            "Authorization header missing from mobile submitText()"
        )
        assert "Bearer" in html, "Bearer token pattern missing from mobile submitText()"

    def test_mobile_page_includes_model_field(self, mobile_client):
        """Chat payload must include model field (required by /v1/chat/completions)."""
        html = mobile_client.get("/mobile").text
        assert '"model"' in html or "'model'" in html or "model:" in html, (
            "model field missing from mobile chat payload"
        )

    def test_mobile_page_uses_messages_array(self, mobile_client):
        """Chat payload must use messages array (OpenAI-compatible shape)."""
        html = mobile_client.get("/mobile").text
        assert "messages" in html, "messages field missing from mobile chat payload"


class TestConversationalRoutingGuard:
    """Ensure 'Say X' conversational prompts don't hit CodingPipeline."""

    def test_say_command_is_not_coding_intent(self):
        from openjarvis.workbench.pipeline import detect_coding_intent

        assert not detect_coding_intent(
            "Say cloud Jarvis test OK and tell me what runtime you are using."
        ), "Conversational 'Say X' prompt must not route to CodingPipeline"

    def test_say_hello_is_not_coding_intent(self):
        from openjarvis.workbench.pipeline import detect_coding_intent

        assert not detect_coding_intent("Say hello")

    def test_greeting_is_not_coding_intent(self):
        from openjarvis.workbench.pipeline import detect_coding_intent

        assert not detect_coding_intent("Hi Jarvis, how are you?")
        assert not detect_coding_intent("Hello Jarvis")

    def test_are_you_running_is_not_coding_intent(self):
        from openjarvis.workbench.pipeline import detect_coding_intent

        assert not detect_coding_intent("are you running in cloud mode?")
        assert not detect_coding_intent("is this the cloud runtime?")

    def test_coding_requests_still_route_correctly(self):
        """Coding requests must still be classified correctly after the guard."""
        from openjarvis.workbench.pipeline import detect_coding_intent

        assert detect_coding_intent("fix this bug in user.py")
        assert detect_coding_intent("patch the failing test")
        assert detect_coding_intent("continue the current sprint")
        assert detect_coding_intent("implement the new auth route")
