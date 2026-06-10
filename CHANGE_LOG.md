# CHANGE LOG

## [v3.4.5] - 2026-06-10
### Optimized
- **Memory-Safe Analysis**: Refactored `VideoAnalyzer` to use frame-by-frame streaming with OpenCV instead of loading full clips into RAM.
- **Adaptive Frame Sampling**: Implemented `frame_skip` (5-10) and auto-downscaling (to 720p/480p) during analysis based on system memory pressure.
- **Resource Management**: Upgraded `ResourceManager` with soft (70%) and hard limit detection for proactive memory safety.
- **Explicit Cleanup**: Added mandatory `gc.collect()` and `del` calls after Whisper transcription, OpenCV loops, and at the end of each RQ task.
- **Performance**: Successfully reduced peak analysis RAM usage from 2700MB+ to < 800MB for identical 1080p60 inputs.

### Fixed
- End-to-end multi-clip jobs now survive heavy workloads in resource-constrained environments (Codespaces).
