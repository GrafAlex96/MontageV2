# CHANGE LOG

## [v3.4.3-STABLE] - 2026-06-08
### Stabilization & Observability
- **Structured JSON Logging**: Implemented a mandatory JSON log format for all pipeline stages with trace_id, stage, status, and duration_ms.
- **End-to-End Tracing**: Integrated UUID4 trace_id across Telegram handlers, database, RQ jobs, and workers.
- **Guaranteed Delivery**: Implemented a 3-attempt retry loop for Telegram video delivery with explicit API response validation.
- **One-Command Startup**: Fully automated start.sh that handles system dependency installation, Redis server lifecycle, and process supervision.
- **Worker Reliability**: start_system.py now monitors worker PID and performs auto-restarts on failure.
- **Artifact Traceability**: Added detailed artifact logging (file paths, sizes, ffprobe metadata) for every pipeline step.
