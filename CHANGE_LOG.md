# CHANGE LOG

## [v3.4.1] - 2026-06-05
### Fixed
- End-to-end pipeline: Worker now correctly delivers processed videos to users.
- FrozenInstanceError: Resolved immutable dataclass mutation in Timeline Service using replace().
- Startup architecture: Single entrypoint (start_system.py) coordinates all services.
- Concurrent job protection: Refined logic to allow uploads while blocking concurrent renders.
- Bot reliability: Fixed unawaited coroutines and missing library imports.
- State integrity: DB is now the absolute source of truth for job status and file counts.

### Added
- Unified Startup: 'bash start.sh' now handles Redis lifecycle, DB init, health checks, and worker startup.
- Multi-process Manager: Python-based process monitor to ensure all system components stay alive.
- Dependency Health Check: Added ImageMagick verification to system startup.
