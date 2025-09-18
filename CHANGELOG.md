# Changelog

All notable changes to Skymarshal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation suite (README, ARCHITECTURE, API, DEVELOPMENT, CONTRIBUTING)
- Enhanced project structure with modular architecture
- Improved development workflow with Makefile commands
- Complete CLI command reference documentation
- Enhanced user feedback with progress indicators:
  - JSON load shows a status spinner while reading data
  - Engagement hydration displays live progress for posts/replies and repost subjects
  - CAR decoding and record extraction display progress with counts

### Changed
- Updated README with comprehensive feature overview
- Restructured documentation for better discoverability
- Enhanced development setup instructions
 - Documentation aligned with interactive-only CLI (subcommands marked as planned)
 - License updated to CC0 1.0 Universal (public domain dedication)

## [0.1.0] - 2024-01-15

### Added
- **Core Application**: Complete CLI-based Bluesky content management tool
- **Authentication System**: Secure Bluesky authentication with session management
- **Data Management**: 
  - CAR file download and processing
  - JSON import/export capabilities
  - Multiple data source support
- **Search & Analysis**:
  - Advanced content filtering
  - Engagement scoring algorithm
  - Dead thread detection
  - Temporal analysis
- **Content Operations**:
  - Safe deletion workflows
  - Multiple approval modes (all-at-once, individual, batch)
  - Dry-run capabilities
  - Progress tracking
- **User Interface**:
  - Rich terminal interface
  - Interactive menu system
  - Progress bars and visual feedback
  - Contextual help system
- **Safety Features**:
  - Multiple confirmation prompts
  - User data isolation
  - Undo capabilities
  - Comprehensive error handling

### Technical Features
- **Modular Architecture**: Manager pattern with clear separation of concerns
- **AT Protocol Integration**: Full compatibility with Bluesky API
- **File Management**: Smart file discovery and processing
- **Performance**: Optimized for large datasets
- **Cross-platform**: Works on macOS, Linux, and Windows

### Core Capabilities (Interactive UI)
The v0.1.0 release provides these capabilities via the interactive menus. A direct subcommand interface is on the roadmap.
- Authenticate with Bluesky
- Download content via API and create backups (CAR)
- Import existing CAR files and export to JSON
- Delete specific content with safety checks
- Remove likes and reposts
- Review content statistics and analytics
- Search and filter content, including dead thread detection

### Bug Fixes
- **Authentication**: Fixed login message formatting with proper f-string interpolation
- **Data Processing**: Resolved reposts pagination bug ('list' object not callable)
- **CAR Import**: Fixed processing of CAR files without commit records
- **CBOR Decoding**: Updated to handle atproto library changes (>= 0.0.26)
- **Security**: Implemented proper user data isolation
- **Deletion**: Fixed list access syntax causing deletion failures
- **Subject URI Parsing**: Hardened parsing for self-repost detection

### Documentation
- Comprehensive README with feature overview
- User flow diagram with complete navigation
- Development setup guide
- Troubleshooting section
- Command reference

### Dependencies
- `atproto>=0.0.46` - AT Protocol client library
- `rich>=13.0.0` - Terminal UI framework
- `click>=8.0.0` - CLI framework

### Development Tools
- `pytest>=7.0.0` - Testing framework
- `black>=23.0.0` - Code formatting
- `isort>=5.12.0` - Import sorting
- `flake8>=6.0.0` - Linting
- `mypy>=1.0.0` - Type checking

## [0.0.1] - 2024-01-01

### Added
- Initial project setup
- Basic package structure
- Core dependencies
- Development environment configuration

---

## Version History Summary

### Major Milestones

**v0.1.0 - First Stable Release**
- Complete CLI application with all core features
- Modular architecture with manager pattern
- Comprehensive safety features
- Rich terminal interface
- Full AT Protocol integration

**v0.0.1 - Initial Setup**
- Project foundation
- Development environment
- Basic package structure

### Future Roadmap

**v0.2.0 - Enhanced Features**
- Web interface (Flask-based)
- Advanced analytics dashboard
- Batch operations improvements
- Plugin system architecture

**v0.3.0 - Performance & Scale**
- Async operations support
- Database integration
- Caching layer
- Performance optimizations

**v1.0.0 - Production Ready**
- Full web application
- API endpoints
- Multi-user support
- Enterprise features

---

## Breaking Changes

### v0.1.0
- Initial release - no breaking changes from previous versions

### Future Breaking Changes
- **v0.2.0**: CLI command structure may change for web interface compatibility
- **v1.0.0**: Configuration file format may change for multi-user support

---

## Migration Guide

### Upgrading to v0.1.0
- No migration required - this is the first stable release
- Install with: `pip install -e .`

### Future Upgrades
- **v0.2.0**: Configuration files will be automatically migrated
- **v1.0.0**: Database migration scripts will be provided

---

## Deprecation Notices

### Current Version (v0.1.0)
- No deprecations

### Future Deprecations
- **v0.2.0**: Some CLI-only features may be deprecated in favor of web interface
- **v1.0.0**: File-based storage may be deprecated in favor of database storage

---

## Security Updates

### v0.1.0
- **User Data Isolation**: Implemented proper file access controls
- **Authentication Security**: Secure session management
- **Input Validation**: Comprehensive input sanitization
- **Error Handling**: No sensitive data in error messages

### Future Security Enhancements
- **v0.2.0**: HTTPS enforcement, CSRF protection
- **v1.0.0**: Multi-factor authentication, audit logging

---

## Performance Improvements

### v0.1.0
- **CAR File Processing**: Optimized for large datasets
- **Memory Management**: Efficient data processing
- **API Rate Limiting**: Respects Bluesky API limits
- **Progress Tracking**: Real-time feedback for long operations

### Future Performance Enhancements
- **v0.2.0**: Caching layer, database optimization
- **v1.0.0**: Async operations, horizontal scaling

---

## Contributors

### v0.1.0
- **Luke Steuber** - Project creator and maintainer
  - Complete application architecture
  - All core features implementation
  - Documentation and testing
  - Community management

### Future Contributors
- We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Acknowledgments

### v0.1.0
- **AT Protocol Team** - Excellent `atproto` Python library
- **Rich Library** - Beautiful terminal interfaces
- **Bluesky Team** - Building the decentralized social web
- **Open Source Community** - Inspiration and collaboration

---

*This changelog is maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) principles.*
