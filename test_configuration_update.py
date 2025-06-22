#!/usr/bin/env python3
"""
Test script to verify that the Configuration class works correctly 
with the new ImageModel structure.
"""

import sys
import os
import numpy as np

# Add the dioptas directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dioptas'))

from dioptas.model.Configuration import Configuration

def test_configuration_basic():
    """Test basic Configuration functionality with new ImageModel structure."""
    print("Testing Configuration with new ImageModel structure...")
    
    # Create a configuration
    config = Configuration()
    
    # Test that we can access image data through the new structure
    print("Testing image data access...")
    config.img_model.data_manager.img_data = np.ones((100, 100))
    assert config.img_model.img_data.shape == (100, 100)
    print("✓ Image data access works correctly")
    
    # Test that we can access background data through the new structure
    print("Testing background data access...")
    config.img_model.data_manager.background_data = np.ones((100, 100)) * 0.5
    assert config.img_model.background_data.shape == (100, 100)
    print("✓ Background data access works correctly")
    
    # Test that we can access transformations through the new structure
    print("Testing transformations access...")
    config.img_model.transformer.img_transformations = []
    assert len(config.img_model.transformer.img_transformations) == 0
    print("✓ Transformations access works correctly")
    
    # Test that we can access corrections through the new structure
    print("Testing corrections access...")
    assert not config.img_model.corrector.has_corrections()
    print("✓ Corrections access works correctly")
    
    # Test that we can access autoprocess through the new structure
    print("Testing autoprocess access...")
    config.img_model.auto_processor.autoprocess = True
    assert config.img_model.autoprocess == True
    print("✓ Autoprocess access works correctly")
    
    # Test that we can access factor through the new structure
    print("Testing factor access...")
    config.img_model.data_manager.factor = 2.0
    assert config.img_model.factor == 2.0
    print("✓ Factor access works correctly")
    
    # Test that we can access filename through the new structure
    print("Testing filename access...")
    config.img_model.data_manager.filename = "test.tif"
    config.img_model._update_legacy_attributes()  # Update legacy attributes
    assert config.img_model.filename == "test.tif"
    print("✓ Filename access works correctly")
    
    # Test that we can access series information through the new structure
    print("Testing series information access...")
    config.img_model.data_manager.series_max = 10
    config.img_model.data_manager.series_pos = 5
    config.img_model._update_legacy_attributes()  # Update legacy attributes
    assert config.img_model.series_max == 10
    assert config.img_model.series_pos == 5
    print("✓ Series information access works correctly")
    
    print("All tests passed! ✓")

if __name__ == "__main__":
    test_configuration_basic() 