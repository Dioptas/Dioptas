# -*- coding: utf-8 -*-
# Test file for Configuration with refactored ImageModel

import numpy as np
import os
import tempfile

from .Configuration import Configuration


def test_configuration_initialization():
    """Test that Configuration initializes correctly with refactored ImageModel."""
    print("Testing Configuration initialization...")
    
    # Create configuration
    config = Configuration()
    
    # Test that all models are properly initialized
    assert config.img_model is not None
    assert config.mask_model is not None
    assert config.calibration_model is not None
    assert config.pattern_model is not None
    assert config.batch_model is not None
    assert config.map_model is not None
    
    # Test that img_model is using the refactored components
    assert hasattr(config.img_model, 'refactored_model')
    assert hasattr(config.img_model, 'state')
    
    # Test that the interface is the same as before
    assert hasattr(config.img_model, 'img_changed')
    assert hasattr(config.img_model, 'load')
    assert hasattr(config.img_model, 'img_data')
    assert hasattr(config.img_model, 'filename')
    
    print("✅ Configuration initialization works with refactored ImageModel")


def test_configuration_image_model_interface():
    """Test that Configuration can use ImageModel interface correctly."""
    print("Testing Configuration ImageModel interface...")
    
    config = Configuration()
    
    # Test basic ImageModel operations
    assert config.img_model.filename == ""
    assert config.img_model.factor == 1.0
    assert config.img_model.background_scaling == 1.0
    
    # Test setting properties
    config.img_model.factor = 2.0
    assert config.img_model.factor == 2.0
    
    config.img_model.background_scaling = 1.5
    assert config.img_model.background_scaling == 1.5
    
    # Test that signals are connected
    assert config.img_model.img_changed is not None
    
    print("✅ Configuration ImageModel interface works correctly")


def test_configuration_state_access():
    """Test that Configuration can access the new state functionality."""
    print("Testing Configuration state access...")
    
    config = Configuration()
    
    # Test state access
    state = config.img_model.state
    assert state.filename == ""
    assert state.factor == 1.0
    
    # Test refactored model access
    refactored = config.img_model.refactored_model
    assert refactored is not None
    
    # Test setting state
    from .image import ImageState
    new_state = ImageState(filename="test.tif", factor=2.0)
    config.img_model.set_state(new_state)
    
    assert config.img_model.filename == "test.tif"
    assert config.img_model.factor == 2.0
    
    print("✅ Configuration can access new state functionality")


def test_configuration_working_directories():
    """Test that Configuration working directories work correctly."""
    print("Testing Configuration working directories...")
    
    # Test default working directories
    config = Configuration()
    assert "image" in config.working_directories
    assert "pattern" in config.working_directories
    assert "mask" in config.working_directories
    assert "calibration" in config.working_directories
    
    # Test custom working directories
    custom_dirs = {
        "image": "/custom/image/path",
        "pattern": "/custom/pattern/path",
        "mask": "/custom/mask/path",
        "calibration": "/custom/calibration/path",
        "overlay": "/custom/overlay/path",
        "phase": "/custom/phase/path",
        "batch": "/custom/batch/path",
    }
    
    config_custom = Configuration(working_directories=custom_dirs)
    assert config_custom.working_directories["image"] == "/custom/image/path"
    assert config_custom.working_directories["pattern"] == "/custom/pattern/path"
    
    print("✅ Configuration working directories work correctly")


def test_configuration_integration_properties():
    """Test that Configuration integration properties work correctly."""
    print("Testing Configuration integration properties...")
    
    config = Configuration()
    
    # Test default values
    assert config.integration_unit == "2th_deg"
    assert config.trim_trailing_zeros is True
    assert config.auto_integrate_pattern is True
    assert config.auto_integrate_cake is False
    
    # Test setting properties
    config.integration_unit = "q_A^-1"
    assert config.integration_unit == "q_A^-1"
    
    config.auto_integrate_pattern = False
    assert config.auto_integrate_pattern is False
    
    config.auto_integrate_cake = True
    assert config.auto_integrate_cake is True
    
    print("✅ Configuration integration properties work correctly")


def test_configuration_copy():
    """Test that Configuration copy method works correctly."""
    print("Testing Configuration copy...")
    
    config = Configuration()
    
    # Set some properties
    config.img_model.factor = 2.0
    config.integration_unit = "q_A^-1"
    config.auto_integrate_pattern = False
    
    # Copy configuration
    config_copy = config.copy()
    
    # Test that copy has same values
    assert config_copy.img_model.factor == 2.0
    assert config_copy.integration_unit == "q_A^-1"
    assert config_copy.auto_integrate_pattern is False
    
    # Test that copy is independent
    config_copy.img_model.factor = 3.0
    assert config.img_model.factor == 2.0  # Original unchanged
    assert config_copy.img_model.factor == 3.0  # Copy changed
    
    print("✅ Configuration copy works correctly")


def run_configuration_tests():
    """Run all Configuration tests."""
    print("Running Configuration tests with refactored ImageModel...")
    print("=" * 60)
    
    try:
        test_configuration_initialization()
        test_configuration_image_model_interface()
        test_configuration_state_access()
        test_configuration_working_directories()
        test_configuration_integration_properties()
        test_configuration_copy()
        
        print("=" * 60)
        print("🎉 All Configuration tests passed! Refactored ImageModel integration works correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_configuration_tests() 