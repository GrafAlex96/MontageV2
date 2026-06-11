import asyncio
import logging
import os
import gc
from typing import List, Dict
from sqlalchemy import select, update
from aiogram import Bot, types
from app.db.session import get_db
from app.db.models import Job, JobStatus, User, UploadedFile, RenderHistory
from app.services.analysis import VideoAnalyzer
from app.services.timeline import TimelineManager, VideoClip
from app.services.subtitle import SubtitleService
from app.services.audio import AudioService
from app.services.renderer import Renderer
from app.services.notifications import NotificationService
from app.services.quality_gate import QualityGate
from app.services.resource_manager import ResourceManager
from app.services.validator import FinalValidator
from app.core.orchestrator import PipelineOrchestrator
from app.core.retry_engine import RetryEngine
from app.agents.story_intelligence import StoryIntelligence
from app.agents.director_agent import DirectorAgent
from app.core.config import settings
from app.core.exceptions import VideoEditorError, ErrorCategory

logger = logging.getLogger(__name__)

class VideoWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.subtitle_service = SubtitleService()
        self.audio_service = AudioService()
        self.renderer = Renderer()
        self.notifier = NotificationService(bot)
        self.quality_gate = QualityGate()
        self.orchestrator = PipelineOrchestrator()
        self.retry_engine = RetryEngine()
        self.story_intel = StoryIntelligence()
        self.director = DirectorAgent()

    async def process_job(self, job_id: int):
        import time
        start_time = time.time()

        ResourceManager.cleanup_zombie_processes()
        ResourceManager.limit_resources()

        # Performance check
        cpu_usage = ResourceManager.get_cpu_usage()
        if cpu_usage > settings.MAX_CPU_PERCENT:
             logger.warning(f"CPU usage too high ({cpu_usage}%), delaying job {job_id}")
             # In production with RQ, we might re-queue. Here we just log.

        mem_usage = ResourceManager.get_memory_usage()
        if mem_usage > 85.0: # Hard memory guard
             logger.error(f"Memory usage critical ({mem_usage}%), aborting job {job_id}")
             return

        with get_db() as session:
            job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()

            if not job or job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                return

            logger.info(
                "TRACE_WORKER_STARTED",
                extra={
                    "job_id": job_id,
                    "user_id": job.user_id,
                    "trace_id": job.trace_id,
                    "stage": "processing",
                    "status": "STARTED"
                }
            )

            # Update status to analyzing
            session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.ANALYZING, progress=0.1))
            session.commit()

            try:
                # 1. Fetch files
                files = session.execute(select(UploadedFile).where(UploadedFile.job_id == job_id)).scalars().all()
                video_paths = [f.file_path for f in files]

                # 2. Analyze
                mem_before = ResourceManager.get_memory_used_mb()

                # Check budget but don't fail immediately
                analysis_ok = ResourceManager.check_stage_budget("ANALYSIS", settings.MAX_RAM_MB)

                clips = []
                for i, file in enumerate(files):
                    try:
                        analyze_start = time.time()

                        # Adaptive safety: check RAM usage
                        mem_usage_pct = ResourceManager.get_memory_usage()
                        mem_status = ResourceManager.get_memory_status(settings.MAX_RAM_MB)

                        # Aggressive Safe Mode
                        is_aggressive = settings.SAFE_MODE or mem_status == "SOFT_LIMIT" or not analysis_ok
                        frame_skip = 15 if is_aggressive else 5
                        max_width = 480 if is_aggressive else 720
                        skip_movement = (mem_usage_pct > 75) or (not analysis_ok)

                        logger.info(
                            "TRACE_ANALYSIS_STARTED",
                            extra={
                                "job_id": job_id,
                                "trace_id": job.trace_id,
                                "file_path": file.file_path,
                                "stage": "processing",
                                "status": "STARTED",
                                "memory_before_MB": ResourceManager.get_memory_used_mb(),
                                "adaptive_mode": "AGGRESSIVE" if is_aggressive else "NORMAL",
                                "skip_movement": skip_movement
                            }
                        )

                        analyzer = VideoAnalyzer(file.file_path, policy={
                            "frame_skip": frame_skip,
                            "max_width": max_width,
                            "cap_frames": 300 if is_aggressive else 1000,
                            "analyze_movement": not skip_movement,
                            "analyze_audio": True
                        })

                        frame_count = analyzer.get_frame_count()
                        scenes = analyzer.detect_scenes()
                        scenes = analyzer.analyze_movement(scenes, skip_movement=skip_movement)
                        silences = analyzer.detect_silence()

                        # --- CONSOLIDATED MASTER EDITOR PIPELINE ---
                        # STEP 1: Story Intelligence
                        story_data = self.story_intel.analyze_content(scenes)

                        # STEP 2: Director Agent (Suggestions only)
                        # director_suggestions = self.director.suggest_strategy(story_data)

                        # Integration note: Master Editor needs ALL clips for global hook
                        scored_scenes = analyzer.generate_quality_scores(scenes, silences)
                        clips.append(VideoClip(path=file.file_path, scenes=scored_scenes))

                        duration_ms = int((time.time() - analyze_start) * 1000)
                        logger.info(
                            "TRACE_ANALYSIS_SUCCESS",
                            extra={
                                "job_id": job_id,
                                "trace_id": job.trace_id,
                                "file_path": file.file_path,
                                "stage": "processing",
                                "status": "SUCCESS",
                                "duration_ms": duration_ms,
                                "memory_after_MB": ResourceManager.get_memory_used_mb()
                            }
                        )
                    except Exception as e:
                        logger.error(f"Analysis failed for file {file.file_path}: {e}", extra={"trace_id": job.trace_id})
                        # Don't raise, we might have other clips or fallback

                    progress = 0.1 + (0.4 * (i + 1) / len(files))
                    await self._update_progress(job_id, progress)

                # 3. Consolidated Unified Pipeline
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING))
                session.commit()

                timeline = None

                # TRY SMART PIPELINE
                if clips:
                    try:
                        # STEP 1: Orchestrate
                        master_plan = self.orchestrator.create_master_plan(clips, job.target_duration)
                        strategy = master_plan["strategy"]
                        base_rules = master_plan["rules"]

                        # STEP 2: Detect beats
                        clip_beats = {}
                        for clip in clips:
                            try:
                                beat_data = self.audio_service.detect_beats(clip.path)
                                if beat_data["confidence"] > 0.4:
                                    clip_beats[clip.path] = beat_data["beats"]
                            except: pass

                        # STEP 3: Quality Retries Loop
                        best_timeline = None
                        best_score = -1.0
                        current_rules = base_rules
                        master_mode = master_plan["beat_sync_mode"]

                        for attempt in range(settings.MAX_RETRIES + 1):
                            tm = TimelineManager(target_duration=job.target_duration, editing_rules=current_rules)
                            final_mode = "VISUAL" if current_rules.get('disable_sync') else master_mode

                            current_timeline = tm.build_combined_timeline_from_items(
                                strategy["final_timeline"],
                                clip_beats=clip_beats,
                                mode=final_mode
                            )

                            current_scores = self.quality_gate.calculate_scores(current_timeline)
                            current_total = sum(current_scores.values())

                            if current_total > best_score:
                                best_score = current_total
                                best_timeline = current_timeline

                            if self.quality_gate.is_production_ready(current_scores):
                                break
                            current_rules = self.retry_engine.execute(attempt + 1, base_rules)

                        timeline = best_timeline
                    except Exception as e:
                        logger.error(f"Smart pipeline failed, falling back: {e}", extra={"trace_id": job.trace_id})

                # FALLBACK PIPELINE GUARANTEE
                if not timeline:
                    logger.warning("PIPELINE_GUARANTEE: Activating Fallback Timeline", extra={"trace_id": job.trace_id})
                    tm = TimelineManager(target_duration=job.target_duration)
                    timeline = tm.build_fallback_timeline(video_paths)

                if not timeline:
                    raise VideoEditorError("Failed to create even a fallback timeline. Aborting.")

                # 4. Transcription (Multi-video support)
                all_subtitles = []
                current_timeline_offset = 0.0
                transcription_cache = {}

                try:
                    # Collect and offset subtitles for all clips in the final timeline
                    for item in timeline:
                        path = item['path']
                        scene = item['scene']

                        # Optimization: cache transcriptions per path during this job
                        if path not in transcription_cache:
                            transcription_cache[path] = self.subtitle_service.transcribe(path)
                            # Partial memory release after each transcription
                            gc.collect()

                        clip_subs = transcription_cache[path]

                        # Filter subtitles that fall within the scene range and offset them
                        for sub in clip_subs:
                            if sub['start'] >= scene.start_time and sub['end'] <= scene.end_time:
                                sub_copy = sub.copy()
                                sub_copy['start'] = sub['start'] - scene.start_time + current_timeline_offset
                                sub_copy['end'] = sub['end'] - scene.start_time + current_timeline_offset
                                all_subtitles.append(sub_copy)

                        current_timeline_offset += (scene.end_time - scene.start_time)

                except Exception as e:
                    logger.error(f"Multi-video transcription failed: {e}", extra={"trace_id": job.trace_id})
                    # Fallback: continue with empty or partial subtitles

                # Full memory release for Whisper model
                self.subtitle_service.unload_model()
                transcription_cache.clear()
                gc.collect() # Cleanup after transcription
                await self._update_progress(job_id, 0.6)

                # 5. Rendering
                # Memory cleanup before heavy render
                ResourceManager.check_stage_budget("RENDERING", settings.MAX_RAM_MB)

                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.RENDERING))
                session.commit()

                output_filename = f"final_{job_id}.mp4"
                output_path = os.path.abspath(os.path.join(settings.TEMP_STORAGE_PATH, output_filename))

                render_start = time.time()
                logger.info(
                    "TRACE_RENDER_STARTED",
                    extra={
                        "job_id": job_id,
                        "user_id": job.user_id,
                        "trace_id": job.trace_id,
                        "stage": "render",
                        "status": "STARTED"
                    }
                )

                try:
                    self.renderer.render_final_video(timeline, all_subtitles, output_path)
                except Exception as e:
                    logger.error(f"Primary render failed: {e}. Attempting SIMPLE SAFE RENDER.", extra={"trace_id": job.trace_id})
                    # Attempt render without subtitles and without effects
                    self.renderer.render_final_video(timeline, [], output_path, simple_mode=True)
                render_dur = int((time.time() - render_start) * 1000)
                logger.info(
                    "TRACE_RENDER_SUCCESS",
                    extra={
                        "job_id": job_id,
                        "user_id": job.user_id,
                        "trace_id": job.trace_id,
                        "file_path": output_path,
                        "stage": "render",
                        "status": "SUCCESS",
                        "duration_ms": render_dur,
                        "details": {
                            "file_size": os.path.getsize(output_path) if os.path.exists(output_path) else 0
                        }
                    }
                )

                await self._update_progress(job_id, 0.8)
                gc.collect()

                # 6. Audio Optimization
                ResourceManager.check_stage_budget("POST_PROCESSING", settings.MAX_RAM_MB)
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.POST_PROCESSING))
                session.commit()

                final_output_path = os.path.join(settings.TEMP_STORAGE_PATH, f"optimized_{output_filename}")
                try:
                    self.audio_service.improve_clarity(output_path, final_output_path)
                except Exception as e:
                    logger.error(f"Audio optimization failed: {e}. Using original render.")
                    import shutil
                    shutil.copy2(output_path, final_output_path)

                # 7. Final Validation
                validation = FinalValidator.validate_output(final_output_path, job.target_duration)
                if not validation['valid']:
                    logger.error(f"Final validation failed for job {job_id}: {validation['error']}", extra={"trace_id": job.trace_id})
                    raise VideoEditorError(f"Validation failed: {validation['error']}")

                # --- Quality Degradation Check (Simplified) ---
                # Compare final frame count and stream count with expected
                if validation.get('degraded'):
                     logger.warning(f"Output partially degraded for job {job_id}", extra={"trace_id": job.trace_id})

                # 7. Deliver
                user = session.execute(select(User).where(User.id == job.user_id)).scalar_one()

                if not os.path.exists(final_output_path):
                     raise FileNotFoundError(f"Final output video missing: {final_output_path}")

                delivery_start = time.time()
                logger.info(
                    "TRACE_DELIVERY_STARTED",
                    extra={
                        "job_id": job_id,
                        "user_id": user.telegram_id,
                        "trace_id": job.trace_id,
                        "file_path": final_output_path,
                        "file_size": os.path.getsize(final_output_path),
                        "stage": "delivery",
                        "status": "STARTED"
                    }
                )

                video_file = types.FSInputFile(final_output_path)
                file_size = os.path.getsize(final_output_path)

                # Delivery pipeline with retry
                sent = False
                for attempt in range(3):
                    try:
                        # Telegram Bot API limit for sendVideo is 50MB
                        # For larger files, we MUST send as Document
                        if file_size > 48 * 1024 * 1024:
                            logger.info(f"File size {file_size} exceeds 50MB, switching to sendDocument")
                            response = await self.bot.send_document(
                                user.telegram_id,
                                video_file,
                                caption="🎬 Your video is ready (Sent as document due to size)."
                            )
                        else:
                            response = await self.bot.send_video(
                                user.telegram_id,
                                video_file,
                                caption="🎬 Your AI edited video is ready! Done."
                            )
                        sent = True
                        duration_ms = int((time.time() - delivery_start) * 1000)
                        logger.info(
                            "TRACE_DELIVERY_SUCCESS",
                            extra={
                                "job_id": job_id,
                                "user_id": user.telegram_id,
                                "trace_id": job.trace_id,
                                "status": "SUCCESS",
                                "duration_ms": duration_ms,
                                "details": {
                                    "response": str(response),
                                    "message_id": response.message_id if hasattr(response, 'message_id') else None
                                },
                                "stage": "delivery"
                            }
                        )
                        break
                    except Exception as e:
                        logger.warning(f"Telegram send attempt {attempt+1} failed: {e}", extra={"trace_id": job.trace_id})
                        await asyncio.sleep(2)

                if not sent:
                    logger.error(
                        "TRACE_DELIVERY_FAILED",
                        extra={
                            "job_id": job_id,
                            "user_id": user.telegram_id,
                            "trace_id": job.trace_id,
                            "status": "FAILED",
                            "stage": "delivery",
                            "error": "Failed to deliver video after 3 attempts"
                        }
                    )
                    raise RuntimeError("Failed to deliver video after 3 attempts")

                # 8. Record History and Update Status
                render = RenderHistory(
                    job_id=job_id,
                    output_path=final_output_path,
                    file_size=os.path.getsize(final_output_path),
                    duration=float(job.target_duration)
                )
                session.add(render)
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.COMPLETED, progress=1.0))
                session.commit()

                logger.info(
                    "TRACE_JOB_COMPLETED",
                    extra={
                        "job_id": job_id,
                        "trace_id": job.trace_id,
                        "stage": "final",
                        "status": "success"
                    }
                )

            except Exception as e:
                logger.error(
                    "TRACE_JOB_FAILED",
                    extra={
                        "job_id": job_id,
                        "trace_id": job.trace_id,
                        "error": str(e),
                        "stage": "final",
                        "status": "fail"
                    },
                    exc_info=True
                )
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.FAILED, error_message=str(e)))
                session.commit()

                # Notify user
                user = session.execute(select(User).where(User.id == job.user_id)).scalar_one()
                await self.bot.send_message(user.telegram_id, f"Sorry, there was an error processing your video: {e}")
            finally:
                # Forced cleanup at end of job
                gc.collect()

    async def _update_progress(self, job_id: int, progress: float):
        with get_db() as session:
            session.execute(update(Job).where(Job.id == job_id).values(progress=progress))
            session.commit()

        await self.notifier.send_progress_update(job_id, progress)

# Task for RQ
def process_job_task(job_id: int):
    import asyncio
    from aiogram import Bot
    from app.core.config import settings

    async def _run():
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            worker = VideoWorker(bot)
            await worker.process_job(job_id)
        finally:
            # Explicitly close session and connector to prevent unclosed connection warnings
            await bot.session.close()

    asyncio.run(_run())
