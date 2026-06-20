"""US14A self-test fixture — added by Jarvis Coding Workbench."""

US14A_MARKER = "Jarvis Coding Workbench E2E proof 20260620T235354"


def test_us14a_marker():
    """Verify US14A marker is present."""
    assert US14A_MARKER.startswith("Jarvis Coding Workbench E2E proof")
