# -*- coding: utf-8 -*-
# Tests for the refactored image model components

"""
Test suite for the refactored image model components.

This package contains tests for:
- ImageState: Immutable state container
- ImageCommands: Type-safe command operations  
- ImageModelRefactored: New model with explicit state access
- ImageModelAdapter: Backward compatibility adapter
- Transfer function implementation
"""

from .test_refactored import run_all_tests as run_refactored_tests
from .test_adapter import run_adapter_tests
from .test_transfer_function import run_transfer_function_tests


def run_all_image_tests():
    """Run all image model tests."""
    print("Running all image model tests...")
    print("=" * 60)
    
    success = True
    
    # Run refactored component tests
    if not run_refactored_tests():
        success = False
    
    # Run adapter compatibility tests
    if not run_adapter_tests():
        success = False
    
    # Run transfer function tests
    if not run_transfer_function_tests():
        success = False
    
    print("=" * 60)
    if success:
        print("🎉 All image model tests passed!")
    else:
        print("❌ Some image model tests failed!")
    
    return success


if __name__ == "__main__":
    run_all_image_tests() 