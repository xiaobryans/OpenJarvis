"""Multi-file fixture: calculator module.

This module has TWO deliberate bugs for the Plan 3 multi-file proof:
  1. divide() crashes with ZeroDivisionError when divisor is 0 (no guard)
  2. percentage() references calculate() which does not exist (NameError)

The Plan 3 multi-file worker must:
  - Identify this file and test_calculator.py as the relevant pair
  - Read both files
  - Patch both files
  - Pass pre/post validation that spans both files

DO NOT modify this file without updating tests/workbench/test_plan3_multi_file.py.
"""

from __future__ import annotations

CALCULATOR_VERSION = "plan3-multi-fixture-v1"


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    """BUG 1: no zero-divisor guard — raises ZeroDivisionError."""
    return a / b  # BUG: missing `if b == 0: raise ValueError("division by zero")`


def percentage(value: float, total: float) -> float:
    """BUG 2: calls calculate() which does not exist — raises NameError."""
    return calculate(value, total)  # BUG: undefined function, should be: value / total * 100
