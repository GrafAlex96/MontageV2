# CHANGE LOG

## [v3.4.3] - 2026-06-05
### Added
- **End-to-End Traceability:** Implemented `trace_id` (UUID4) across all layers (Telegram -> DB -> RQ -> Worker -> FFmpeg -> Delivery).
- **Structured Logging:** Switched to comprehensive JSON logging with mandatory metadata (trace_id, job_id, stage, status).
- **Delivery Guarantee:** Implemented a robust delivery pipeline with 3 retries and explicit Telegram API response verification.
- **Worker Supervisor:** `start_system.py` now monitors the RQ worker PID and auto-restarts it up to 3 times on failure.

### Fixed
- **Fail-Fast Startup:** System now strictly refuses to start if core components (Redis, DB, FFmpeg) fail health checks.
- **Silent Failures:** Every pipeline exception is now caught, logged with trace_id and stacktrace, and marked as FAILED in DB.
- **UnboundLocalError:** Reinforced user object retrieval in bot handlers to prevent race conditions.

### Security
- Reinforced path traversal protection with absolute path containment and UUID isolation.
