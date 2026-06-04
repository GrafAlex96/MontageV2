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
from app.agents.story_intelligence import StoryIntelligence
from app.agents.director_agent import DirectorAgent
from app.agents.master_editor import MasterEditor
from app.agents.editing_presets import EditingPresets
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
        self.story_intel = StoryIntelligence()
        self.director = DirectorAgent()
        self.master_editor = MasterEditor()
        self.presets = EditingPresets()

    async def process_job(self, job_id: int):
        ResourceManager.cleanup_zombie_processes()
        ResourceManager.limit_resources()
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
                    # Explicit cleanup for large files
                    gc.collect()

                # 3. Consolidated Master Pipeline
                session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING))
                session.commit()

                # --- NEW MASTER EDITOR PIPELINE (GLOBAL) ---
                # Combine all scenes from all clips into items for Master Editor
                all_items = []
                for clip in clips:
                    for scene in clip.scenes:
                        all_items.append({'path': clip.path, 'scene': scene})

                # Story intel from the first clip for overall theme
                story_data = self.story_intel.analyze_content(clips[0].scenes if clips else [])
                director_suggestions = self.director.suggest_strategy(story_data)

                final_strategy = self.master_editor.decide_final_strategy(
                    story_data, director_suggestions, all_items
                )

                editing_rules = self.presets.get_rules(final_strategy["final_preset"])
                logger.info(f"Master Decision: {final_strategy['final_preset']}", extra={"trace_id": job.trace_id})
                # --- END MASTER EDITOR PIPELINE ---

                timeline_manager = TimelineManager(target_duration=job.target_duration, editing_rules=editing_rules)

                # Detect beats for beat-sync (Per source file)
                clip_beats = {}
                for clip in clips:
                    logger.info(f"Detecting beats for {clip.path}", extra={"trace_id": job.trace_id})
                    clip_beats[clip.path] = self.audio_service.detect_beats(clip.path)

                # Get candidates from Master Editor decision
                timeline = timeline_manager.build_combined_timeline_from_items(
                    final_strategy["final_timeline"],
                    clip_beats=clip_beats
                )

                # Quality Gate Check with Automatic Re-edit Loop
                max_retries = 3
                for attempt in range(max_retries):
                    scores = self.quality_gate.calculate_scores(timeline)
                    logger.info(f"Quality scores for job {job_id} (Attempt {attempt+1}): {scores}", extra={"trace_id": job.trace_id})

                    if self.quality_gate.is_production_ready(scores):
                        break

                    if attempt < max_retries - 1:
                        logger.warning(f"Quality scores too low, attempting re-edit...", extra={"trace_id": job.trace_id})
                        # Re-initialize timeline manager with current attempt for variation
                        timeline_manager = TimelineManager(
                            target_duration=job.target_duration,
                            editing_rules=editing_rules,
                            attempt=attempt + 1
                        )
                        timeline = timeline_manager.build_combined_timeline_from_items(
                            final_strategy["final_timeline"],
                            clip_beats=clip_beats
                        )
                    else:
                        logger.error(f"Failed to reach quality targets after {max_retries} attempts. Proceeding.", extra={"trace_id": job.trace_id})

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

                await self._update_progress(job_id, 0.6)

                # 5. Rendering
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
