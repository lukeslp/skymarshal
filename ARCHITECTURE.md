# Skymarshal Architecture Guide

This document provides a comprehensive overview of Skymarshal's architecture, design patterns, and component relationships.

## Table of Contents

- [System Overview](#system-overview)
- [Core Architecture](#core-architecture)
- [Module Design](#module-design)
- [Data Flow](#data-flow)
- [Design Patterns](#design-patterns)
- [Security Model](#security-model)
- [Performance Considerations](#performance-considerations)
- [Extension Points](#extension-points)

## System Overview

Skymarshal is a modular CLI application built around the **Manager Pattern**, where each functional domain is encapsulated in a dedicated manager class. The architecture emphasizes:

- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Loose Coupling**: Modules interact through well-defined interfaces
- **High Cohesion**: Related functionality is grouped together
- **Testability**: Each component can be tested in isolation
- **Extensibility**: New features can be added without modifying existing code

## Core Architecture

### Application Controller Pattern

The main application follows the **Application Controller** pattern, where `app.py` serves as the central orchestrator:

```python
class InteractiveCARInspector:
    """Main application controller orchestrating all components."""
    
    def __init__(self):
        # Initialize all managers
        self.auth_manager = AuthManager()
        self.ui_manager = UIManager(settings)
        self.data_manager = DataManager()
        self.search_manager = SearchManager()
        self.deletion_manager = DeletionManager()
        self.settings_manager = SettingsManager()
        self.help_manager = HelpManager()
```

### Manager Pattern Implementation

Each functional domain is managed by a dedicated manager class:

| Manager | Responsibility | Key Methods |
|---------|---------------|-------------|
| `AuthManager` | Authentication & session management | `authenticate_client()`, `is_authenticated()` |
| `UIManager` | User interface and Rich displays | `show_main_menu()`, `display_results()` |
| `DataManager` | Data import/export operations | `download_data()`, `import_car_file()` |
| `SearchManager` | Content search and filtering | `search_content()`, `build_filters()` |
| `DeletionManager` | Safe deletion workflows | `delete_content()`, `confirm_deletion()` |
| `SettingsManager` | User preferences persistence | `load_settings()`, `save_settings()` |
| `HelpManager` | Help system and documentation | `show_help()`, `get_contextual_help()` |

## 🧩 Module Design

### Core Modules

#### 1. `app.py` - Application Controller
**Purpose**: Main application orchestration and interactive UI control

**Key Responsibilities**:
- Initialize and coordinate all managers
- Handle CLI command routing
- Manage application lifecycle
- Orchestrate complex workflows

**Design Patterns**:
- **Facade Pattern**: Provides simplified interface to complex subsystem
- **Command Pattern**: CLI commands as encapsulated operations
- **Template Method**: Standardized workflow patterns

#### 2. `models.py` - Data Structures
**Purpose**: Core data models and enumerations

**Key Components**:
```python
@dataclass
class ContentItem:
    """Represents a piece of Bluesky content."""
    uri: str
    cid: str
    content_type: str
    text: Optional[str] = None
    created_at: Optional[str] = None
    engagement_score: float = 0.0
    # ... additional fields

class ContentType(Enum):
    """Content type enumeration."""
    ALL = "all"
    POSTS = "posts"
    REPLIES = "replies"
    # ... other types
```

**Design Patterns**:
- **Data Transfer Object (DTO)**: Clean data structures
- **Enum Pattern**: Type-safe constants
- **Immutable Data**: Dataclasses with optional mutability

#### 3. `auth.py` - Authentication Management
**Purpose**: Handle Bluesky authentication and session management

**Key Features**:
- AT Protocol client management
- Session validation and refresh
- Handle normalization
- Secure credential handling

**Design Patterns**:
- **Singleton Pattern**: Single authentication state
- **Strategy Pattern**: Different authentication methods
- **Proxy Pattern**: Client abstraction

#### 4. `ui.py` - User Interface Components
**Purpose**: Rich-based terminal interface components

**Key Features**:
- Interactive menus and prompts
- Data tables and visualizations
- Progress indicators
- Error handling and user feedback

**Design Patterns**:
- **Builder Pattern**: Complex UI construction
- **Observer Pattern**: Progress tracking
- **Factory Pattern**: UI component creation

#### 5. `data_manager.py` - Data Operations
**Purpose**: Handle data import/export and file operations

**Key Features**:
- CAR file processing
- JSON import/export
- File discovery and management
- Data validation and transformation

**Design Patterns**:
- **Strategy Pattern**: Different data sources
- **Adapter Pattern**: Format conversion
- **Chain of Responsibility**: Data processing pipeline

#### 6. `search.py` - Search and Filtering
**Purpose**: Content search and filtering engine

**Key Features**:
- Multi-criteria filtering
- Engagement scoring algorithms
- Search result ranking
- Export capabilities

**Design Patterns**:
- **Filter Pattern**: Chainable filters
- **Strategy Pattern**: Different search algorithms
- **Iterator Pattern**: Result iteration

#### 7. `deletion.py` - Safe Deletion Workflows
**Purpose**: Manage content deletion with safety measures

**Key Features**:
- Multiple approval modes
- Dry-run capabilities
- Progress tracking
- Undo functionality

**Design Patterns**:
- **Command Pattern**: Deletion operations
- **Memento Pattern**: Undo functionality
- **Template Method**: Standardized deletion workflows

## Data Flow

### 1. Application Initialization
```
Startup → Banner Display → Auth Check → Data Discovery → Main Menu
```

### 2. Authentication Flow
```
User Input → Handle Normalization → AT Protocol Auth → Session Storage → Client Initialization
```

### 3. Data Loading Flow
```
Data Source Selection → Download/Import → Processing → Validation → Storage → Analysis Ready
```

### 4. Search and Analysis Flow
```
Filter Building → Search Execution → Result Processing → Ranking → Display → Export Options
```

### 5. Deletion Flow
```
Content Selection → Confirmation → Dry-run (optional) → Execution → Progress Tracking → Summary
```

## 🎨 Design Patterns

### Manager Pattern
Each functional domain is encapsulated in a manager class:

```python
class AuthManager:
    """Manages authentication state and operations."""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.current_did: Optional[str] = None
        self.current_handle: Optional[str] = None
    
    def authenticate_client(self, handle: str, password: str) -> bool:
        """Authenticate client for API operations."""
        # Implementation details...
```

### Strategy Pattern
Different algorithms for the same operation:

```python
class SearchManager:
    """Search and filtering with multiple strategies."""
    
    def search_content(self, filters: SearchFilters) -> List[ContentItem]:
        """Search content using configured strategy."""
        if filters.content_type == ContentType.POSTS:
            return self._search_posts(filters)
        elif filters.content_type == ContentType.LIKES:
            return self._search_likes(filters)
        # ... other strategies
```

### Template Method Pattern
Standardized workflows with customizable steps:

```python
class DeletionManager:
    """Safe deletion with standardized workflow."""
    
    def delete_content(self, items: List[ContentItem], mode: DeleteMode) -> bool:
        """Template method for deletion workflow."""
        # Step 1: Validate input
        if not self._validate_items(items):
            return False
        
        # Step 2: Show preview
        self._show_preview(items)
        
        # Step 3: Get confirmation
        if not self._get_confirmation(mode):
            return False
        
        # Step 4: Execute deletion
        return self._execute_deletion(items, mode)
```

### Observer Pattern
Progress tracking and user feedback:

```python
class ProgressTracker:
    """Track and display operation progress."""
    
    def __init__(self):
        self.observers: List[ProgressObserver] = []
    
    def add_observer(self, observer: ProgressObserver):
        """Add progress observer."""
        self.observers.append(observer)
    
    def notify_progress(self, progress: float, message: str):
        """Notify all observers of progress update."""
        for observer in self.observers:
            observer.update_progress(progress, message)
```

## Security Model

### Authentication Security
- **Session Management**: Secure session storage and validation
- **Credential Protection**: No plaintext password storage
- **Handle Normalization**: Consistent input validation
- **Re-authentication**: Automatic session refresh

### Data Security
- **User Isolation**: Each user's data is isolated by handle
- **File Access Control**: Secure file permissions
- **Input Validation**: Comprehensive input sanitization
- **Error Handling**: No sensitive data in error messages

### Operation Security
- **Confirmation Prompts**: Multiple verification steps
- **Dry-run Mode**: Safe operation preview
- **Audit Logging**: Operation tracking and logging
- **Rollback Capability**: Undo functionality for critical operations

## Performance Considerations

### Memory Management
- **Lazy Loading**: Load data on demand
- **Batch Processing**: Process large datasets in chunks
- **Memory Cleanup**: Explicit resource cleanup
- **Streaming**: Process data without loading everything into memory

### API Optimization
- **Rate Limiting**: Respect Bluesky API limits
- **Caching**: Cache frequently accessed data
- **Connection Pooling**: Reuse HTTP connections
- **Retry Logic**: Handle transient failures gracefully

### File I/O Optimization
- **Async Operations**: Non-blocking file operations where possible
- **Compression**: Efficient data storage
- **Indexing**: Fast data retrieval
- **Incremental Updates**: Update only changed data

## 🔌 Extension Points

### Adding New Content Types
```python
# In models.py
class ContentType(Enum):
    # ... existing types
    NEW_TYPE = "new_type"

# In search.py
class SearchManager:
    def _search_new_type(self, filters: SearchFilters) -> List[ContentItem]:
        """Search implementation for new content type."""
        # Implementation...
```

### Adding New Data Sources
```python
# In data_manager.py
class DataManager:
    def import_new_format(self, file_path: str) -> List[ContentItem]:
        """Import data from new format."""
        # Implementation...
```

### Adding New UI Components
```python
# In ui.py
class UIManager:
    def show_new_component(self, data: Any) -> str:
        """Display new UI component."""
        # Implementation...
```

### Adding New Deletion Modes
```python
# In models.py
class DeleteMode(Enum):
    # ... existing modes
    NEW_MODE = "new_mode"

# In deletion.py
class DeletionManager:
    def _execute_new_mode(self, items: List[ContentItem]) -> bool:
        """Execute deletion in new mode."""
        # Implementation...
```

## 🧪 Testing Architecture

### Unit Testing
Each manager can be tested in isolation:

```python
class TestAuthManager:
    def test_authenticate_client_success(self):
        """Test successful authentication."""
        auth_manager = AuthManager()
        result = auth_manager.authenticate_client("test.bsky.social", "password")
        assert result is True
        assert auth_manager.is_authenticated() is True
```

### Integration Testing
Test component interactions:

```python
class TestDataFlow:
    def test_complete_workflow(self):
        """Test complete data processing workflow."""
        # Setup
        app = InteractiveCARInspector()
        
        # Execute workflow
        app.authenticate("test.bsky.social", "password")
        app.download_data()
        results = app.search_content(filters)
        
        # Verify results
        assert len(results) > 0
```

### Mocking Strategy
- **External APIs**: Mock AT Protocol client
- **File Operations**: Mock file system operations
- **User Input**: Mock Rich prompts
- **Network Calls**: Mock HTTP requests

## Monitoring and Observability

### Logging Strategy
- **Structured Logging**: JSON-formatted logs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context Information**: Include relevant metadata
- **Performance Metrics**: Track operation timing

### Error Handling
- **Graceful Degradation**: Continue operation when possible
- **User-Friendly Messages**: Clear error descriptions
- **Recovery Options**: Suggest solutions to users
- **Error Reporting**: Log detailed error information

### Performance Monitoring
- **Operation Timing**: Track execution time
- **Memory Usage**: Monitor memory consumption
- **API Rate Limits**: Track API usage
- **File I/O Metrics**: Monitor disk operations

## 🔮 Future Architecture Considerations

### Scalability
- **Horizontal Scaling**: Support for multiple instances
- **Database Integration**: Move from file-based to database storage
- **Caching Layer**: Redis for session and data caching
- **Load Balancing**: Distribute operations across instances

### Extensibility
- **Plugin System**: Support for third-party extensions
- **API Layer**: REST API for external integrations
- **Web Interface**: Browser-based UI
- **Mobile Support**: Mobile app integration

### Performance
- **Async Operations**: Full async/await support
- **Parallel Processing**: Multi-threaded operations
- **Streaming**: Real-time data processing
- **Optimization**: Profile and optimize bottlenecks

---

This architecture provides a solid foundation for Skymarshal's current functionality while maintaining flexibility for future enhancements and extensions.
