# ImageModel Refactoring: State vs Logic Separation

## Current Problems with Mixed State/Logic

### 1. **Single Responsibility Violation**
The current `ImageModel` handles:
- State management (data, metadata, parameters)
- Business logic (loading, transformations, corrections)
- Component coordination
- Signal management
- Legacy compatibility

### 2. **Testing Difficulties**
- Can't test logic without state side effects
- Hard to mock individual operations
- State changes make tests brittle
- Complex setup required for each test

### 3. **Serialization Complexity**
- State scattered across multiple components
- Hard to version individual parts
- Migration logic mixed with business logic
- Inconsistent serialization patterns

### 4. **Tight Coupling**
- Components tightly coupled through main class
- Changes in one area affect others
- Hard to modify individual features
- Difficult to add new functionality

## Proposed Solution: Command Pattern + Immutable State

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ImageState    │    │ ImageCommands    │    │ ImageModel      │
│   (Immutable)   │◄──►│   (Logic)        │◄──►│   (Coordinator) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Serialization │    │   Testability    │    │   Extensibility │
│   (Easy)        │    │   (High)         │    │   (High)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Key Components

#### 1. **ImageState** (Immutable State Container)
```python
@dataclass
class ImageState:
    version: str = "3.0"
    raw_image_data: Optional[np.ndarray] = None
    background_data: Optional[np.ndarray] = None
    filename: str = ""
    factor: float = 1.0
    transformations: List[str] = field(default_factory=list)
    # ... other state fields
```

**Benefits:**
- ✅ Immutable: No accidental state mutations
- ✅ Serializable: Easy to save/load
- ✅ Versionable: Clear version history
- ✅ Testable: Can create any state for testing

#### 2. **ImageCommands** (Pure Logic)
```python
class LoadImageCommand(ImageCommand):
    def execute(self, state: ImageState, filename: str, pos: int = 0) -> ImageState:
        # Pure logic - no side effects
        image_data = self.loader.get_image_data(filename, pos)
        return state.copy(
            filename=filename,
            raw_image_data=image_data.get("img_data"),
            # ... other updates
        )
```

**Benefits:**
- ✅ Pure functions: No side effects
- ✅ Testable: Easy to unit test
- ✅ Composable: Commands can be combined
- ✅ Reversible: Can implement undo/redo

#### 3. **ImageModelRefactored** (Coordinator)
```python
class ImageModelRefactored:
    def load(self, filename: str, pos: int = 0):
        new_state = self._command_processor.execute(
            "load_image", self._state, filename=filename, pos=pos
        )
        self._update_state(new_state)
```

**Benefits:**
- ✅ Thin: Minimal coordination logic
- ✅ Focused: Single responsibility
- ✅ Maintainable: Easy to understand and modify

## Comparison: Before vs After

### Before (Mixed State/Logic)
```python
class ImageModel:
    def __init__(self):
        # State scattered across components
        self.data_manager = ImageDataManager()
        self.loader = ImageLoader()
        self.transformer = ImageTransformer()
        self.corrector = ImageCalculator()
        # ... more components
        
        # Legacy attributes for compatibility
        self.filename = self.data_manager.filename
        self.img_transformations = self.transformer.img_transformations
        # ... more duplicates
    
    def load(self, filename, pos=0):
        # Mixed logic and state updates
        self.data_manager.filename = filename
        image_file_data = self.loader.get_image_data(filename, pos)
        self.data_manager.set_loadable_attributes(image_file_data)
        self.navigator.update_filename(filename)
        self._perform_img_transformations()
        self._update_legacy_attributes()
        # ... more mixed operations
```

### After (Separated State/Logic)
```python
class ImageModelRefactored:
    def __init__(self):
        # Clean state container
        self._state = ImageState()
        
        # Command processor for logic
        self._command_processor = ImageCommandProcessor()
        
        # Only external components
        self.navigator = FileNavigator()
        self.auto_processor = AutoProcessor(load_callback=self.load)
    
    def load(self, filename: str, pos: int = 0):
        # Pure logic execution
        new_state = self._command_processor.execute(
            "load_image", self._state, filename=filename, pos=pos
        )
        
        # Simple state update
        self._update_state(new_state)
```

## Benefits of the Refactoring

### 1. **Improved Testability**
```python
# Test logic without state side effects
def test_load_image_command():
    state = ImageState()
    command = LoadImageCommand(mock_loader)
    new_state = command.execute(state, "test.tif", pos=0)
    assert new_state.filename == "test.tif"
    assert new_state.raw_image_data is not None

# Test state transitions
def test_state_transitions():
    model = ImageModelRefactored()
    model.set_state(ImageState(filename="test.tif"))
    assert model.filename == "test.tif"
```

### 2. **Easy Serialization**
```python
# Save state
def save_state(self, hdf5_group):
    state_dict = self._state.to_dict()
    hdf5_group.attrs["version"] = state_dict["version"]
    # ... simple serialization

# Load state
def load_state(self, hdf5_group):
    state_dict = self._extract_state_dict(hdf5_group)
    state = ImageState.from_dict(state_dict)
    self.set_state(state)
```

### 3. **Version Migration**
```python
def migrate_state(self, old_state, from_version):
    if from_version == "2.0":
        return self._migrate_v2_to_v3(old_state)
    elif from_version == "1.0":
        return self._migrate_v1_to_v3(old_state)
    return old_state
```

### 4. **Extensibility**
```python
# Easy to add new commands
class CustomTransformCommand(ImageCommand):
    def execute(self, state: ImageState, **params) -> ImageState:
        # New transformation logic
        return state.copy(transformations=state.transformations + ["custom"])

# Register new command
self._command_processor.commands["custom_transform"] = CustomTransformCommand()
```

### 5. **Undo/Redo Support**
```python
class ImageModelWithHistory:
    def __init__(self):
        self._state_history = []
        self._current_index = -1
    
    def execute_command(self, command_name, **kwargs):
        # Save current state
        self._state_history.append(self._state.copy())
        self._current_index += 1
        
        # Execute command
        new_state = self._command_processor.execute(command_name, self._state, **kwargs)
        self._update_state(new_state)
    
    def undo(self):
        if self._current_index > 0:
            self._current_index -= 1
            self._update_state(self._state_history[self._current_index])
```

## Migration Strategy

### Phase 1: Create New Classes
- ✅ Create `ImageState`
- ✅ Create `ImageCommands`
- ✅ Create `ImageModelRefactored`

### Phase 2: Gradual Migration
- Add new classes alongside existing ones
- Create adapter for backward compatibility
- Test new implementation thoroughly

### Phase 3: Replace Old Implementation
- Update all references to use new classes
- Remove old `ImageModel`
- Clean up legacy code

### Phase 4: Optimize
- Add caching for expensive operations
- Implement lazy loading where appropriate
- Add performance monitoring

## Conclusion

Separating state from logic in the `ImageModel` provides:

1. **Better Testability**: Pure functions and immutable state
2. **Easier Serialization**: Centralized state management
3. **Improved Maintainability**: Clear separation of concerns
4. **Enhanced Extensibility**: Command pattern for new features
5. **Future-Proofing**: Easy to add undo/redo, history, etc.

This refactoring follows established software engineering principles and makes the codebase more robust, maintainable, and extensible. 