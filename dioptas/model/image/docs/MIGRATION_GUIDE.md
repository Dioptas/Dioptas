# ImageModel Refactoring Migration Guide

## Overview

The ImageModel has been refactored to separate state from logic, providing better testability, serialization, and maintainability. This guide helps you migrate from the old `ImageModel` to the new architecture.

## Quick Migration Options

### Option 1: Use the Adapter (Recommended for existing code)

The `ImageModelAdapter` provides the exact same interface as the old `ImageModel` but uses the new refactored components internally.

```python
# Old code (still works)
from dioptas.model.image import ImageModel
model = ImageModel()

# New code with adapter (same interface)
from dioptas.model.image import ImageModelAdapter
model = ImageModelAdapter()  # Drop-in replacement
```

### Option 2: Use the New Refactored Model

For new code or when you want to take advantage of the new features:

```python
from dioptas.model.image import ImageModelRefactored, ImageState
model = ImageModelRefactored()
```

## Migration Steps

### Phase 1: Immediate (No Code Changes)

1. **Replace imports** (optional):
   ```python
   # Old
   from dioptas.model.image import ImageModel
   
   # New (same interface)
   from dioptas.model.image import ImageModelAdapter as ImageModel
   ```

2. **Test existing code** - it should work exactly the same

### Phase 2: Gradual Migration

1. **Access state explicitly**:
   ```python
   # Old way
   filename = model.filename
   factor = model.factor
   
   # New way
   state = model.state
   filename = state.filename
   factor = state.factor
   ```

2. **Use operations that return states**:
   ```python
   # Old way
   model.load("image.tif")
   model.rotate_img_p90()
   
   # New way
   new_state = model.load("image.tif")
   new_state = model.rotate_img_p90()
   ```

3. **Access new functionality**:
   ```python
   # Get underlying refactored model
   refactored = model.refactored_model
   
   # Direct state access
   current_state = model.state
   
   # Set state directly
   new_state = ImageState(filename="test.tif", factor=1.5)
   model.set_state(new_state)
   ```

### Phase 3: Full Migration

1. **Replace ImageModelAdapter with ImageModelRefactored**:
   ```python
   # Old
   from dioptas.model.image import ImageModelAdapter
   model = ImageModelAdapter()
   
   # New
   from dioptas.model.image import ImageModelRefactored
   model = ImageModelRefactored()
   ```

2. **Update state access patterns**:
   ```python
   # Always access state explicitly
   state = model.state
   filename = state.filename
   factor = state.factor
   ```

3. **Use typed enums for operations**:
   ```python
   from dioptas.model.image import RotationDirection, FlipDirection
   
   # Old way (still works)
   model.rotate_img_p90()
   
   # New way (type-safe)
   new_state = model.rotate_img_p90()  # Returns new state
   ```

## API Changes

### What's the Same

- All public methods and properties
- Signal names and behavior
- File loading and navigation
- Image transformations
- Background handling
- Corrections

### What's New

- **Explicit state access**: `model.state` property
- **State return values**: Operations return new states
- **Type-safe enums**: `RotationDirection.PLUS_90` instead of `"p90"`
- **Direct state manipulation**: `model.set_state(new_state)`
- **Better serialization**: State is easily serializable

### What's Deprecated

- Direct access to internal components (use `.state` instead)
- String-based command execution (use typed methods)

## Examples

### Basic Usage

```python
from dioptas.model.image import ImageModelRefactored, ImageState

# Create model
model = ImageModelRefactored()

# Load image
new_state = model.load("image.tif")
print(f"Loaded: {new_state.filename}")

# Apply operations
state_after_rotate = model.rotate_img_p90()
state_after_factor = model.set_factor(1.5)

# Access current state
current_state = model.state
print(f"Current factor: {current_state.factor}")
```

### State Inspection

```python
# Inspect state directly
state = model.state
print(f"File: {state.filename}")
print(f"Factor: {state.factor}")
print(f"Transformations: {state.transformations}")
print(f"Has background: {state.background_data is not None}")
```

### Serialization

```python
# Save state
state_to_save = model.state
state_dict = state_to_save.to_dict()

# Load state
loaded_state = ImageState.from_dict(state_dict)
model.set_state(loaded_state)
```

### Testing

```python
# Test with specific state
test_state = ImageState(filename="test.tif", factor=2.0)
model.set_state(test_state)
assert model.state.factor == 2.0

# Test operations
new_state = model.rotate_img_p90()
assert "rotate_matrix_p90" in new_state.transformations
```

## Benefits of Migration

1. **Better Testability**: Pure functions and immutable state
2. **Easier Serialization**: Centralized state management
3. **Improved Maintainability**: Clear separation of concerns
4. **Enhanced Extensibility**: Command pattern for new features
5. **Type Safety**: Full IDE support and type checking
6. **Future-Proofing**: Easy to add undo/redo, history, etc.

## Troubleshooting

### Common Issues

1. **"AttributeError: 'ImageModelRefactored' object has no attribute 'data_manager'"**
   - Use `model.state` instead of `model.data_manager`
   - Or use `ImageModelAdapter` for backward compatibility

2. **"TypeError: expected str, got RotationDirection"**
   - Use the typed methods: `model.rotate_img_p90()` instead of string-based commands

3. **"State not updating after operations"**
   - Operations return new states, check the return value
   - Use `model.state` to get current state

### Getting Help

- Check the test file: `dioptas/model/image/test_refactored.py`
- Use the adapter for backward compatibility: `ImageModelAdapter`
- Review the benefits document: `dioptas/model/image/REFACTORING_BENEFITS.md`

## Timeline

- **Phase 1**: Use `ImageModelAdapter` (immediate, no changes needed)
- **Phase 2**: Gradual migration to new patterns (ongoing)
- **Phase 3**: Full migration to `ImageModelRefactored` (future)
- **Phase 4**: Remove old `ImageModel` (deprecated, will be removed in future version) 