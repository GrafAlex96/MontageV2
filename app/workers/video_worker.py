import asyncio
import logging
import os
from sqlalchemy import select, update
from app.db.session import async_session
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
from aiogram import Bot

logger = logging.getLogger(__name__)

from app.core.exceptions import VideoEditorError, ErrorCategory

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
        async with async_session() as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job or job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                return
            logger.info(f"Processing job {job_id}")

            # Update status to analyzing
            await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.ANALYZING, progress=0.1))
            await session.commit()

            try:
                # 1. Fetch files
                stmt = select(UploadedFile).where(UploadedFile.job_id == job_id)
                res = await session.execute(stmt)
                files = res.scalars().all()

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
                    await self._update_progress(job_id, progress)

                # 3. Consolidated Master Pipeline
                await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING))
                await session.commit()

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

                # Detect beats for beat-sync (on first clip)
                beats = []
                if clips:
                    beats = self.audio_service.detect_beats(clips[0].path)

                # Get candidates from Master Editor decision
                timeline = timeline_manager.build_combined_timeline_from_items(final_strategy["final_timeline"], beats=beats)

                # Quality Gate Check with Automatic Re-edit Loop
                max_retries = 3
                for attempt in range(max_retries):
                    scores = self.quality_gate.calculate_scores(timeline)
                    logger.info(f"Quality scores for job {job_id} (Attempt {attempt+1}): {scores}", extra={"trace_id": job.trace_id})

                    if self.quality_gate.is_production_ready(scores):
                        break

                    if attempt < max_retries - 1:
                        logger.warning(f"Quality scores too low, attempting re-edit...", extra={"trace_id": job.trace_id})
                        timeline = timeline_manager.build_combined_timeline_from_items(final_strategy["final_timeline"], beats=beats)
                    else:
                        logger.error(f"Failed to reach quality targets after {max_retries} attempts. Proceeding.", extra={"trace_id": job.trace_id})

                # 4. Transcription
                subtitles = []
                if clips:
                    try:
                        subtitles = self.subtitle_service.transcribe(clips[0].path)
                    except Exception as e:
                        logger.error(f"Transcription failed: {e}", extra={"trace_id": job.trace_id})
                        # Fallback: continue without subtitles

                await self._update_progress(job_id, 0.6)

                # 5. Rendering
                await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.RENDERING))
                await session.commit()

                output_filename = f"final_{job_id}.mp4"
                output_path = os.path.join(settings.TEMP_STORAGE_PATH, output_filename)

                self.renderer.render_final_video(timeline, subtitles, output_path)

                await self._update_progress(job_id, 0.8)

                # 6. Audio Optimization
                await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.POST_PROCESSING))
                await session.commit()

                final_output_path = os.path.join(settings.TEMP_STORAGE_PATH, f"optimized_{output_filename}")
                self.audio_service.improve_clarity(output_path, final_output_path)

                # 7. Final Validation
                validation = FinalValidator.validate_output(final_output_path, job.target_duration)
                if not validation['valid']:
                    logger.error(f"Final validation failed for job {job_id}: {validation['error']}", extra={"trace_id": job.trace_id})
                    raise VideoEditorError(f"Validation failed: {validation['error']}")

                # 7. Deliver
                stmt = select(User).where(User.id == job.user_id)
                res = await session.execute(stmt)
                user = res.scalar_one()

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
                await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.COMPLETED, progress=1.0))
                await session.commit()

                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
                await session.execute(update(Job).where(Job.id == job_id).values(status=JobStatus.FAILED, error_message=str(e)))
                await session.commit()

                # Notify user
                stmt = select(User).where(User.id == job.user_id)
                res = await session.execute(stmt)
                user = res.scalar_one()
                await self.bot.send_message(user.telegram_id, f"Sorry, there was an error processing your video: {e}")

    async def _update_progress(self, job_id: int, progress: float):
        async with async_session() as session:
            await session.execute(update(Job).where(Job.id == job_id).values(progress=progress))
            await session.commit()
        await self.notifier.send_progress_update(job_id, progress)

from aiogram import types

# Task for RQ
def process_job_task(job_id: int):
    import asyncio
    from aiogram import Bot
    from app.core.config import settings

    bot = Bot(token=settings.BOT_TOKEN)
    worker = VideoWorker(bot)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(worker.process_job(job_id))
