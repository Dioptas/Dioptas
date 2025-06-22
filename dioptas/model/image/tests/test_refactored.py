# -*- coding: utf-8 -*-
"""
Tests for the refactored image model components.
"""

import numpy as np
import os
import tempfile
import pytest
from unittest.mock import Mock, patch

from ..ImageState import ImageState
from ..ImageCommands import (
    ImageCommandProcessor, 
    RotationDirection, 
    FlipDirection,
    BackgroundDimensionWrongException
)
from ..ImageModelRefactored import ImageModelRefactored


def test_image_state():
    """Test ImageState creation and operations."""
    print("Testing ImageState...")
    
    # Create empty state
    state = ImageState()
    assert state.filename == ""
    assert state.factor == 1.0
    assert state.raw_image_data is None
    
    # Create state with data
    test_data = np.zeros((100, 100))
    state_with_data = ImageState(
        filename="test.tif",
        raw_image_data=test_data,
        factor=2.0
    )
    assert state_with_data.filename == "test.tif"
    assert state_with_data.factor == 2.0
    assert state_with_data.raw_image_data is test_data
    
    # Test copy with changes
    new_state = state_with_data.copy(factor=3.0)
    assert new_state.filename == "test.tif"
    assert new_state.factor == 3.0
    assert new_state.raw_image_data is test_data
    
    # Test serialization
    state_dict = state_with_data.to_dict()
    assert state_dict["filename"] == "test.tif"
    assert state_dict["factor"] == 2.0
    
    # Test deserialization
    restored_state = ImageState.from_dict(state_dict)
    assert restored_state.filename == "test.tif"
    assert restored_state.factor == 2.0
    
    print("✅ ImageState tests passed")


def test_command_processor():
    """Test ImageCommandProcessor operations."""
    print("Testing ImageCommandProcessor...")
    
    processor = ImageCommandProcessor()
    initial_state = ImageState()
    
    # Test parameter setting
    new_state = processor.set_factor(initial_state, factor=1.5)
    assert new_state.factor == 1.5
    
    # Test multiple parameter setting
    new_state = processor.set_parameter(
        initial_state, 
        factor=2.0, 
        background_scaling=1.2
    )
    assert new_state.factor == 2.0
    assert new_state.background_scaling == 1.2
    
    # Test convenience methods
    new_state = processor.set_background_scaling(initial_state, scaling=1.5)
    assert new_state.background_scaling == 1.5
    
    new_state = processor.set_autoprocess(initial_state, autoprocess=True)
    assert new_state.autoprocess is True
    
    print("✅ ImageCommandProcessor tests passed")


def test_image_model_refactored():
    """Test ImageModelRefactored basic functionality."""
    print("Testing ImageModelRefactored...")
    
    model = ImageModelRefactored()
    
    # Test initial state
    initial_state = model.state
    assert initial_state.filename == ""
    assert initial_state.factor == 1.0
    assert initial_state.raw_image_data is None
    
    # Test parameter setting
    new_state = model.set_factor(2.0)
    assert new_state.factor == 2.0
    assert model.state.factor == 2.0
    
    # Test multiple operations
    new_state = model.set_background_scaling(1.5)
    assert new_state.background_scaling == 1.5
    assert model.state.background_scaling == 1.5
    
    # Test state access
    current_state = model.state
    assert current_state.factor == 2.0
    assert current_state.background_scaling == 1.5
    
    # Test setting state directly
    test_state = ImageState(filename="test.tif", factor=3.0)
    model.set_state(test_state)
    assert model.state.filename == "test.tif"
    assert model.state.factor == 3.0
    
    print("✅ ImageModelRefactored tests passed")


def test_enum_types():
    """Test enum types for rotation and flip directions."""
    print("Testing enum types...")
    
    # Test rotation directions
    assert RotationDirection.PLUS_90.value == "p90"
    assert RotationDirection.MINUS_90.value == "m90"
    
    # Test flip directions
    assert FlipDirection.HORIZONTAL.value == "horizontal"
    assert FlipDirection.VERTICAL.value == "vertical"
    
    print("✅ Enum type tests passed")


def run_all_tests():
    """Run all tests for the refactored components."""
    print("Running tests for refactored ImageModel components...")
    print("=" * 60)
    
    try:
        test_image_state()
        test_command_processor()
        test_image_model_refactored()
        test_enum_types()
        
        print("=" * 60)
        print("🎉 All tests passed! Refactored components are working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests() 