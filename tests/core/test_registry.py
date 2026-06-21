"""Tests for the decorator-based registry system."""

from __future__ import annotations

import pytest

from openjarvis.core.registry import (
    EngineRegistry,
    ModelRegistry,
    RouterPolicyRegistry,
)


class TestRegistryBase:
    def test_register_and_get(self) -> None:
        @ModelRegistry.register("test-model")
        class _Dummy:
            pass

        assert ModelRegistry.get("test-model") is _Dummy

    def test_register_value(self) -> None:
        ModelRegistry.register_value("val", 42)
        assert ModelRegistry.get("val") == 42

    def test_duplicate_raises(self) -> None:
        ModelRegistry.register_value("dup", 1)
        with pytest.raises(ValueError, match="already has an entry"):
            ModelRegistry.register_value("dup", 2)

    def test_get_missing_raises(self) -> None:
        with pytest.raises(KeyError, match="does not have an entry"):
            ModelRegistry.get("nonexistent")

    def test_create_instantiates(self) -> None:
        @ModelRegistry.register("factory")
        class _Cls:
            def __init__(self, x: int) -> None:
                self.x = x

        obj = ModelRegistry.create("factory", 7)
        assert obj.x == 7

    def test_create_non_callable_raises(self) -> None:
        ModelRegistry.register_value("plain", "hello")
        with pytest.raises(TypeError, match="not callable"):
            ModelRegistry.create("plain")

    def test_items(self) -> None:
        ModelRegistry.register_value("a", 1)
        ModelRegistry.register_value("b", 2)
        assert dict(ModelRegistry.items()) == {"a": 1, "b": 2}

    def test_keys(self) -> None:
        ModelRegistry.register_value("x", 10)
        ModelRegistry.register_value("y", 20)
        assert set(ModelRegistry.keys()) == {"x", "y"}

    def test_contains(self) -> None:
        ModelRegistry.register_value("present", True)
        assert ModelRegistry.contains("present")
        assert not ModelRegistry.contains("absent")

    def test_clear(self) -> None:
        ModelRegistry.register_value("temp", 0)
        ModelRegistry.clear()
        assert ModelRegistry.keys() == ()

    def test_isolation_between_registries(self) -> None:
        """Entries in ModelRegistry must not leak into EngineRegistry."""
        ModelRegistry.register_value("shared-key", "model")
        with pytest.raises(KeyError):
            EngineRegistry.get("shared-key")


class TestRouterPolicyRegistry:
    def test_register_and_get(self) -> None:
        RouterPolicyRegistry.register_value("test-policy", "dummy")
        assert RouterPolicyRegistry.get("test-policy") == "dummy"

    def test_keys(self) -> None:
        RouterPolicyRegistry.register_value("a", 1)
        RouterPolicyRegistry.register_value("b", 2)
        assert set(RouterPolicyRegistry.keys()) == {"a", "b"}

    def test_contains(self) -> None:
        RouterPolicyRegistry.register_value("present", True)
        assert RouterPolicyRegistry.contains("present")
        assert not RouterPolicyRegistry.contains("absent")

    def test_duplicate_raises(self) -> None:
        RouterPolicyRegistry.register_value("dup", 1)
        with pytest.raises(ValueError, match="already has an entry"):
            RouterPolicyRegistry.register_value("dup", 2)


def test_miner_registry_register_and_get():
    from openjarvis.core.registry import MinerRegistry

    class _Stub:
        provider_id = "stub-pearl"

    MinerRegistry.register_value("stub-pearl", _Stub)
    assert MinerRegistry.contains("stub-pearl") is True
    assert MinerRegistry.get("stub-pearl") is _Stub


def test_miner_registry_cleared_between_tests():
    from openjarvis.core.registry import MinerRegistry
    # If autouse clear works, no entry from prior tests remains
    assert MinerRegistry.contains("stub-pearl") is False


# ---------------------------------------------------------------------------
# Idempotent re-registration tests (covers the ``-m`` double-import fix)
# ---------------------------------------------------------------------------


def test_idempotent_reregister_same_qualname():
    """Re-registering the same class name under the same key must be a no-op."""
    from openjarvis.core.registry import ConnectorRegistry

    ConnectorRegistry.clear()

    @ConnectorRegistry.register("test-idem")
    class _MyConnector:
        pass

    # Simulate the ``-m`` double-import: a second class object with the
    # same __qualname__ (Python creates a fresh class object on re-exec).
    @ConnectorRegistry.register("test-idem")
    class _MyConnector:  # noqa: F811 — intentional redefinition for test
        pass

    assert ConnectorRegistry.contains("test-idem")


def test_duplicate_different_class_still_raises():
    """Different classes registered under the same key must still raise."""
    from openjarvis.core.registry import ConnectorRegistry

    ConnectorRegistry.clear()

    @ConnectorRegistry.register("test-conflict")
    class _FirstConnector:
        pass

    with pytest.raises(ValueError, match="already has an entry"):

        @ConnectorRegistry.register("test-conflict")
        class _SecondConnector:
            pass


def test_registry_module_dash_m_no_crash():
    """Importing connectors.gmail does not crash due to duplicate registration."""
    from openjarvis.core.registry import ConnectorRegistry

    # Clear so we start from a known state.
    ConnectorRegistry.clear()

    # First import registers the connector.
    import importlib
    import sys

    # Remove cached module so the import runs module-level code again.
    sys.modules.pop("openjarvis.connectors.gmail", None)
    importlib.import_module("openjarvis.connectors.gmail")

    # Second import of the same module must be a no-op (cached in sys.modules).
    importlib.import_module("openjarvis.connectors.gmail")

    assert ConnectorRegistry.contains("gmail")
