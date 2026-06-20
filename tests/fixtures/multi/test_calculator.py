"""Multi-file fixture: calculator test suite.

This test file has one deliberate bug that depends on the calculator module bug:
  - test_divide_by_zero expects ValueError but the unfixed calculator raises
    ZeroDivisionError, so the test fails (wrong exception type asserted).

When calculator.py is fixed to raise ValueError, this test must also be updated
to assert ValueError (not ZeroDivisionError), so BOTH files need patching.

DO NOT modify this file without updating tests/workbench/test_plan3_multi_file.py.
"""

from __future__ import annotations

import pytest

from calculator import add, subtract, multiply, divide, percentage

TEST_VERSION = "plan3-multi-fixture-v1"


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(10, 4) == 6


def test_multiply():
    assert multiply(3, 4) == 12


def test_divide_normal():
    assert divide(10, 2) == 5.0


def test_divide_by_zero():
    """BUG in test: expects ValueError but unfixed calculator raises ZeroDivisionError."""
    with pytest.raises(ValueError):  # BUG: calculator raises ZeroDivisionError, not ValueError
        divide(10, 0)


def test_percentage():
    """Fails because calculator.percentage() calls undefined calculate()."""
    result = percentage(25, 100)
    assert result == 25.0
