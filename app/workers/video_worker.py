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

    async def process_job(self, job_id: int):
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
            logger.info(f"Processing job {job_id}")

            # Update status to analyzing
            session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.ANALYZING, progress=0.1))
            session.commit()

            try:
                # 1. Fetch files
                files = session.execute(select(UploadedFile).where(UploadedFile.job_id == job_id)).scalars().all()

                # 2. Analyze
                clips = []
                for i, file in enumerate(files):
                    logger.info(f"Analyzing file {file.file_path}", extra={"trace_id": job.trace_id})
                    analyzer = VideoAnalyzer(file.file_path)
                    scenes = analyzer.detect_scenes()
                    scenes = analyzer.analyze_movement(scenes)
                    silences = analyzer.detect_silence()

                    # --- CONSOLIDATED MASTER EDITOR PIPELINE ---
                    # STEP 1: Story Intelligence
                    story_data = self.story_intel.analyze_content(scenes)

                    # STEP 2: Director Agent (Suggestions only)
                    director_suggestions = self.director.suggest_strategy(story_data)

                    # Integration note: Master Editor needs ALL clips for global hook
                    scored_scenes = analyzer.generate_quality_scores(scenes, silences)
                    clips.append(VideoClip(path=file.file_path, scenes=scored_scenes))

                    progress = 0.1 + (0.4 * (i + 1) / len(files))
                    self._update_progress(job_id, progress)
                    # Explicit cleanup for large files after analysis
                    gc.collect()

                # 3. Consolidated Master Pipeline
                # Memory cleanup before Master Editor
                gc.collect()

                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING))
                session.commit()

                # 3. Consolidated Unified Pipeline
                # Memory cleanup before heavy processing
                gc.collect()

                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING))
                session.commit()

                # STEP 1: Orchestrate
                master_plan = self.orchestrator.create_master_plan(clips, job.target_duration)
                strategy = master_plan["strategy"]
                base_rules = master_plan["rules"]

                # STEP 2: Detect beats
                clip_beats = {}
                for clip in clips:
                    beat_data = self.audio_service.detect_beats(clip.path)
                    if beat_data["confidence"] > 0.4:
                        clip_beats[clip.path] = beat_data["beats"]

                # STEP 3: Quality Retries Loop (Unified via RetryEngine)
                best_timeline = None
                best_score = -1.0
                current_rules = base_rules

                for attempt in range(settings.MAX_RETRIES + 1):
                    tm = TimelineManager(target_duration=job.target_duration, editing_rules=current_rules)
                    # Note: RetryEngine handles strategy shifts, MasterEditor provides candidates
                    current_timeline = tm.build_combined_timeline_from_items(
                        strategy["final_timeline"],
                        clip_beats=clip_beats if not current_rules.get('disable_sync') else None
                    )

                    current_scores = self.quality_gate.calculate_scores(current_timeline)
                    current_total = sum(current_scores.values())

                    if current_total > best_score:
                        best_score = current_total
                        best_timeline = current_timeline

                    if self.quality_gate.is_production_ready(current_scores):
                        break

                    if not self.retry_engine.should_continue(attempt + 1, current_total, best_score):
                        break

                    current_rules = self.retry_engine.get_retry_strategy(attempt + 1, base_rules)

                timeline = best_timeline

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

                gc.collect() # Cleanup after transcription
                await self._update_progress(job_id, 0.6)

                # 5. Rendering
                # Memory cleanup before heavy render
                gc.collect()

                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.RENDERING))
                session.commit()

                output_filename = f"final_{job_id}.mp4"
                output_path = os.path.join(settings.TEMP_STORAGE_PATH, output_filename)

                self.renderer.render_final_video(timeline, all_subtitles, output_path)

                self._update_progress(job_id, 0.8)
                gc.collect()

                # 6. Audio Optimization
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.POST_PROCESSING))
                session.commit()

                final_output_path = os.path.join(settings.TEMP_STORAGE_PATH, f"optimized_{output_filename}")
                self.audio_service.improve_clarity(output_path, final_output_path)

                # 7. Final Validation
                validation = FinalValidator.validate_output(final_output_path, job.target_duration)
                if not validation['valid']:
                    logger.error(f"Final validation failed for job {job_id}: {validation['error']}", extra={"trace_id": job.trace_id})
                    raise VideoEditorError(f"Validation failed: {validation['error']}")

                # --- Quality Regression Check ---
                # Re-score rendered video for visual quality
                post_analyzer = VideoAnalyzer(final_output_path)
                post_scenes = post_analyzer.detect_scenes()
                post_scenes = post_analyzer.analyze_movement(post_scenes)
                post_scores = self.quality_gate.calculate_scores([{'scene': s} for s in post_scenes])

                regression = self.quality_gate.calculate_regression(scores, post_scores)
                if regression['is_degraded']:
                    logger.warning(f"Quality degradation detected for job {job_id}: {regression['drops']}", extra={"trace_id": job.trace_id})
                    # In production, we might trigger a re-render or re-edit here
                # --- End Regression Check ---

                # 7. Deliver
                user = session.execute(select(User).where(User.id == job.user_id)).scalar_one()

                video_file = types.FSInputFile(final_output_path)
                await self.bot.send_video(user.telegram_id, video_file, caption="Here is your edited video! 🎬")

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

                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.FAILED, error_message=str(e)))
                session.commit()

                # Notify user
                user = session.execute(select(User).where(User.id == job.user_id)).scalar_one()
                await self.bot.send_message(user.telegram_id, f"Sorry, there was an error processing your video: {e}")

    def _update_progress(self, job_id: int, progress: float):
        with get_db() as session:
            session.execute(update(Job).where(Job.id == job_id).values(progress=progress))
            session.commit()

        # This is an async call from a sync context or we need to wrap it?
        # VideoWorker is already async, so this is fine.
        import asyncio
        asyncio.create_task(self.notifier.send_progress_update(job_id, progress))

# Task for RQ
def process_job_task(job_id: int):
    import asyncio
    from aiogram import Bot
    from app.core.config import settings

    bot = Bot(token=settings.BOT_TOKEN)
    worker = VideoWorker(bot)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(worker.process_job(job_id))
