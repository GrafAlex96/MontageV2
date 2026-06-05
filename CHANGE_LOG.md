# CHANGE LOG

## [v3.4.2] - 2026-06-05
### Fixed
- End-to-end pipeline: Worker now correctly delivers processed videos to users with explicit verification.
- Startup architecture: Single entrypoint (start_system.py) coordinates all services and monitors health.
- Worker stability: Fixed RQ worker entrypoint issues and improved process management.
- Logging: Implemented structured logging at every stage (received, queued, started, rendered, delivered).
- Delivery: Added retry logic (3 attempts) for Telegram video delivery to ensure results reach the user.

### Added
- Fully Automated Startup: 'bash start.sh' now installs system dependencies (FFmpeg, Redis) automatically.
- Multi-process Manager: Real-time log streaming from worker and bot sub-processes.
- System Readiness: Auto-creation of necessary directories (logs, uploads, tmp) and environment files.

### Security & Stability
- UUID isolation and absolute path verification for all file operations.
- Explicit session management for bot instances in background tasks.
