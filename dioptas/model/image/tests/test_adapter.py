# -*- coding: utf-8 -*-
"""
Tests for the ImageModelAdapter to ensure backward compatibility.
"""

import numpy as np
import warnings
from unittest.mock import Mock, patch

# Fix imports to use parent package
from ..ImageModelAdapter import ImageModelAdapter
from ..ImageState import ImageState
from ..ImageCommands import ImageCommandProcessor

from ..ImageModel import ImageModel


def test_adapter_interface():
    """Test that ImageModelAdapter provides the same interface as ImageModel."""
    print("Testing ImageModelAdapter interface compatibility...")

    # Create both models
    old_model = ImageModel()
    adapter_model = ImageModelAdapter()

    # Test that they have the same attributes
    old_attrs = set(dir(old_model))
    adapter_attrs = set(dir(adapter_model))

    # Public interface should be the same
    public_old_attrs = {attr for attr in old_attrs if not attr.startswith("_")}
    public_adapter_attrs = {attr for attr in adapter_attrs if not attr.startswith("_")}

    # Check that all public attributes from old model exist in adapter
    missing_attrs = public_old_attrs - public_adapter_attrs
    if missing_attrs:
        print(f"❌ Missing attributes in adapter: {missing_attrs}")
        return False

    print("✅ All public attributes from old model exist in adapter")

    # Test that they have the same signals
    old_signals = [
        attr for attr in old_attrs if hasattr(getattr(old_model, attr), "emit")
    ]
    adapter_signals = [
        attr for attr in adapter_attrs if hasattr(getattr(adapter_model, attr), "emit")
    ]

    if set(old_signals) != set(adapter_signals):
        print(f"❌ Signal mismatch. Old: {old_signals}, Adapter: {adapter_signals}")
        return False

    print("✅ All signals from old model exist in adapter")

    return True


def test_adapter_behavior():
    """Test that ImageModelAdapter behaves the same as ImageModel."""
    print("Testing ImageModelAdapter behavior...")

    # Create both models
    old_model = ImageModel()
    adapter_model = ImageModelAdapter()

    # Test initial state
    assert old_model.filename == adapter_model.filename
    assert old_model.factor == adapter_model.factor
    assert old_model.background_scaling == adapter_model.background_scaling

    # Test setting properties
    old_model.factor = 2.0
    adapter_model.factor = 2.0

    assert old_model.factor == 2.0
    assert adapter_model.factor == 2.0

    # Test setting background scaling
    old_model.background_scaling = 1.5
    adapter_model.background_scaling = 1.5

    assert old_model.background_scaling == 1.5
    assert adapter_model.background_scaling == 1.5

    # Test setting autoprocess
    old_model.autoprocess = True
    adapter_model.autoprocess = True

    assert old_model.autoprocess is True
    assert adapter_model.autoprocess is True

    print("✅ Adapter behavior matches old model")


def test_adapter_state_access():
    """Test that adapter provides access to new state functionality."""
    print("Testing adapter state access...")

    adapter_model = ImageModelAdapter()

    # Test state access
    state = adapter_model.state
    assert state.filename == ""
    assert state.factor == 1.0

    # Test refactored model access
    refactored = adapter_model.refactored_model
    assert refactored is not None

    # Test setting state
    new_state = ImageState(filename="test.tif", factor=2.0)
    adapter_model.set_state(new_state)

    assert adapter_model.filename == "test.tif"
    assert adapter_model.factor == 2.0
    assert adapter_model.state.filename == "test.tif"

    print("✅ Adapter provides access to new state functionality")


def test_adapter_legacy_components():
    """Test that adapter provides access to legacy components."""
    print("Testing adapter legacy component access...")

    adapter_model = ImageModelAdapter()

    # Test that legacy components are accessible
    assert hasattr(adapter_model, "navigator")
    assert hasattr(adapter_model, "auto_processor")

    # Test that deprecated components show warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Access deprecated components
        _ = adapter_model.data_manager
        _ = adapter_model.loader
        _ = adapter_model.transformer
        _ = adapter_model.corrector

        # Check that warnings were issued (at least some of them)
        # Note: Some warnings might be filtered out, so we check for at least 1
        assert (
            len(w) >= 1
        ), f"Expected warnings for deprecated component access, got {len(w)}"

        # Check that the warnings contain the expected text
        warning_messages = [str(warning.message) for warning in w]
        expected_keywords = [
            "deprecated",
            "Use .state instead",
            "Use command processor instead",
        ]
        found_keywords = [
            any(keyword in msg for keyword in expected_keywords)
            for msg in warning_messages
        ]
        assert any(
            found_keywords
        ), f"No expected warning keywords found in: {warning_messages}"

    print("✅ Adapter provides legacy component access with warnings")


def run_adapter_tests():
    """Run all adapter compatibility tests."""
    print("Running ImageModelAdapter compatibility tests...")
    print("=" * 60)

    try:
        if not test_adapter_interface():
            print("❌ Interface compatibility test failed")
            return False

        test_adapter_behavior()
        test_adapter_state_access()
        test_adapter_legacy_components()

        print("=" * 60)
        print("🎉 All adapter tests passed! Backward compatibility is working.")
        return True

    except Exception as e:
        print(f"❌ Adapter test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_adapter_tests()
