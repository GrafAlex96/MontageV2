# CHANGE LOG

## [v3.4.4] - 2026-06-10
### Fixed
- **Worker Startup**: Switched to a dedicated python entrypoint `app/workers/rq_worker.py` using `python` to launch the worker. This resolved the "No module named rq.__main__" and "rq is a package" errors in cloud environments.
- **Environment Validation**: Implemented strict fail-fast validation for `BOT_TOKEN`. Startup now aborts if the token is missing or set to the default placeholder.
- **Startup Reliability**: Fixed process management in `start_system.py` to accurately detect and log the status of sub-processes (Redis, Worker, Bot, API).

### Added
- **Formatted Boot Log**: Implemented a highly readable startup sequence with dot-filled status indicators for all core components.
- **Auto-Environment Setup**: Automated the creation of `.env` from `.env.example` and necessary runtime directories (logs, uploads, tmp).
- **Process Verification**: Added a 5-second verification window after launch to confirm sub-processes remained stable.

### Stabilization
- Standardized end-to-end pipeline verification (Upload -> Process -> Deliver) with mandatory trace logs and delivery confirmation.
