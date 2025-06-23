# -*- coding: utf-8 -*-
"""
Tests for transfer function correction functionality.
"""

import numpy as np
import os
import tempfile
import pytest
from unittest.mock import Mock, patch

from ..ImageState import ImageState
from ..ImageCommands import ImageCommandProcessor
from ..ImageModel import ImageModel
from ..ImageModelAdapter import ImageModelAdapter


def test_transfer_function_state():
    """Test transfer function state management."""
    print("Testing transfer function state...")
    
    # Create state with transfer function data
    original_data = np.ones((100, 100)) * 10
    response_data = np.ones((100, 100)) * 5
    
    state = ImageState(
        transfer_function_enabled=True,
        transfer_function_original_filename="original.tif",
        transfer_function_response_filename="response.tif",
        transfer_function_original_data=original_data,
        transfer_function_response_data=response_data
    )
    
    assert state.transfer_function_enabled is True
    assert state.transfer_function_original_filename == "original.tif"
    assert state.transfer_function_response_filename == "response.tif"
    assert state.transfer_function_original_data is original_data
    assert state.transfer_function_response_data is response_data
    
    # Test state copy
    new_state = state.copy(transfer_function_enabled=False)
    assert new_state.transfer_function_enabled is False
    assert new_state.transfer_function_original_data is original_data
    
    # Test serialization
    state_dict = state.to_dict()
    assert state_dict["transfer_function_enabled"] is True
    assert state_dict["transfer_function_original_filename"] == "original.tif"
    
    # Test deserialization
    restored_state = ImageState.from_dict(state_dict)
    assert restored_state.transfer_function_enabled is True
    assert restored_state.transfer_function_original_filename == "original.tif"
    assert np.array_equal(restored_state.transfer_function_original_data, original_data)
    
    print("✅ Transfer function state management works correctly")


def test_transfer_function_commands():
    """Test transfer function commands."""
    print("Testing transfer function commands...")
    
    processor = ImageCommandProcessor()
    initial_state = ImageState()
    
    # Test enable/disable
    new_state = processor.enable_transfer_function(initial_state)
    assert new_state.transfer_function_enabled is False  # No data loaded yet
    
    # Test with data
    original_data = np.ones((100, 100)) * 10
    response_data = np.ones((100, 100)) * 5
    
    state_with_data = initial_state.copy(
        transfer_function_original_data=original_data,
        transfer_function_response_data=response_data
    )
    
    enabled_state = processor.enable_transfer_function(state_with_data)
    assert enabled_state.transfer_function_enabled is True
    
    disabled_state = processor.disable_transfer_function(enabled_state)
    assert disabled_state.transfer_function_enabled is False
    
    # Test reset
    reset_state = processor.reset_transfer_function(enabled_state)
    assert reset_state.transfer_function_enabled is False
    assert reset_state.transfer_function_original_data is None
    assert reset_state.transfer_function_response_data is None
    
    print("✅ Transfer function commands work correctly")


def test_transfer_function_model():
    """Test transfer function in refactored model."""
    print("Testing transfer function in refactored model...")
    
    model = ImageModel()
    
    # Test enable/disable without data
    new_state = model.enable_transfer_function()
    assert new_state.transfer_function_enabled is False
    
    # Test with mock data
    original_data = np.ones((100, 100)) * 10
    response_data = np.ones((100, 100)) * 5
    
    # Set up state with transfer function data
    state_with_data = model.state.copy(
        raw_image_data=np.ones((100, 100)) * 20,  # Test image
        transfer_function_original_data=original_data,
        transfer_function_response_data=response_data
    )
    model.set_state(state_with_data)
    
    # Enable transfer function
    new_state = model.enable_transfer_function()
    assert new_state.transfer_function_enabled is True
    
    # Test that img_data applies transfer function correction
    # The transfer function should divide by (response/original) = 5/10 = 0.5
    # So 20 / 0.5 = 40
    corrected_data = model.img_data
    expected_value = 20 / (5/10)  # 40
    assert np.allclose(corrected_data, expected_value, atol=1e-10)
    
    # Test disable
    new_state = model.disable_transfer_function()
    assert new_state.transfer_function_enabled is False
    
    # Test that img_data no longer applies transfer function
    corrected_data = model.img_data
    assert np.allclose(corrected_data, 20, atol=1e-10)  # No correction applied
    
    print("✅ Transfer function in refactored model works correctly")


def test_transfer_function_adapter():
    """Test transfer function in adapter."""
    print("Testing transfer function in adapter...")
    
    adapter = ImageModelAdapter()
    
    # Test enable/disable
    new_state = adapter.enable_transfer_function()
    assert new_state.transfer_function_enabled is False
    
    new_state = adapter.disable_transfer_function()
    assert new_state.transfer_function_enabled is False
    
    # Test that adapter provides the same interface as old model
    assert hasattr(adapter, 'enable_transfer_function')
    assert hasattr(adapter, 'disable_transfer_function')
    
    print("✅ Transfer function in adapter works correctly")


def run_transfer_function_tests():
    """Run all transfer function tests."""
    print("Running transfer function tests...")
    print("=" * 60)
    
    try:
        test_transfer_function_state()
        test_transfer_function_commands()
        test_transfer_function_model()
        test_transfer_function_adapter()
        
        print("=" * 60)
        print("🎉 All transfer function tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Transfer function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_transfer_function_tests() 