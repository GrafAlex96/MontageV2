# CHANGE LOG

## [v3.4.1] - 2026-06-04
### Fixed
- UnboundLocalError in upload handler; user object is now strictly fetched first.
- FSM file_count sync with DB source of truth.
- storage_bytes persistence with explicit session commit.
- Missing sys import and logger definitions across services.
- Unawaited coroutine warnings in VideoWorker.

### Added
- Automated One-Command Startup (bash start.sh) for Codespaces.
- Auto-Redis management in startup script.
- Background worker integration (RQ) in startup.
- Multi-video processing pipeline with automated bot delivery.
- Comprehensive Health Check and Job Recovery systems.
- Concurrent job protection for users.

### Security
- Reinforced path traversal protection using UUIDs and absolute path validation.
- File format and size validation.
- User storage quota enforcement.
