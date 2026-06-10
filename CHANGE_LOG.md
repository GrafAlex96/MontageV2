# CHANGE LOG

## [v3.4.5] - 2026-06-10
### Optimized
- **Memory-Safe Analysis**: Refactored `VideoAnalyzer` to use frame-by-frame streaming with OpenCV instead of loading full clips into RAM.
- **Adaptive Frame Sampling**: Implemented `frame_skip` (5-10) and auto-downscaling (to 720p/480p) during analysis based on system memory pressure.
- **Resource Management**: Upgraded `ResourceManager` with soft (70%) and hard limit detection for proactive memory safety.
- **Explicit Cleanup**: Added mandatory `gc.collect()` and `del` calls after Whisper transcription, OpenCV loops, and at the end of each RQ task.
- **Performance**: Successfully reduced peak analysis RAM usage from 2700MB+ to < 800MB for identical 1080p60 inputs.

### Fixed
- **Zero-Setup Startup**: `start.sh` now automatically installs python dependencies and creates necessary directories (`logs`, `uploads`, `tmp`).
- **Auto-Environment**: Implemented automatic `.env` creation from `.env.example` with strict validation for the Telegram `BOT_TOKEN`.
- **System Dependencies**: `start_system.py` now attempts to auto-install `ffmpeg`, `redis-server`, and `imagemagick` using `apt-get` where available.
- **Worker Stability**: Standardized RQ worker entrypoint and added a monitored supervisor loop with auto-restart capabilities.
