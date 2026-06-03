from moviepy import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip
from typing import List, Dict
import os
from app.core.config import settings

class Renderer:
    def __init__(self):
        self.target_size = (settings.TARGET_WIDTH, settings.TARGET_HEIGHT)
        self.fps = settings.TARGET_FPS

    def render_final_video(self, timeline: List[Dict], subtitles: List[Dict], output_path: str):
        """Assemble segments, apply subtitles, and render final video."""
        clips = []

        for i, item in enumerate(timeline):
            path = item['path']
            scene = item['scene']

            clip = VideoFileClip(path).subclipped(scene.start_time, scene.end_time)

            # Resize and crop to 9:16 vertical
            clip = self._prepare_for_social(clip)

            # Apply Pattern Interrupts (Zoom, Speed shifts)
            if i % 2 == 0:
                clip = self._apply_zoom_interrupt(clip)

            clips.append(clip)

        final_clip = concatenate_videoclips(clips, method="compose")

        # Add subtitles if provided
        if subtitles:
            final_clip = self._add_subtitles(final_clip, subtitles)

        final_clip.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True
        )

        # Close all clips
        for clip in clips:
            clip.close()
        final_clip.close()

    def _apply_zoom_interrupt(self, clip: VideoFileClip) -> VideoFileClip:
        """Apply a slight zoom pattern interrupt."""
        # Zoom in 10%
        return clip.resized(1.1).cropped(
            x1=clip.w*0.05, y1=clip.h*0.05,
            x2=clip.w*1.05, y2=clip.h*1.05
        ).resized(self.target_size)

    def _prepare_for_social(self, clip: VideoFileClip) -> VideoFileClip:
        """Resize and crop clip to 1080x1920."""
        target_ratio = self.target_size[0] / self.target_size[1] # 9/16
        current_ratio = clip.w / clip.h

        if current_ratio > target_ratio:
            # Clip is wider than target, resize based on height then crop width
            clip = clip.resized(height=self.target_size[1])
            center_x = clip.w / 2
            clip = clip.cropped(
                x1=center_x - self.target_size[0]/2,
                y1=0,
                x2=center_x + self.target_size[0]/2,
                y2=self.target_size[1]
            )
        else:
            # Clip is narrower than target, resize based on width then crop height
            clip = clip.resized(width=self.target_size[0])
            center_y = clip.h / 2
            clip = clip.cropped(
                x1=0,
                y1=center_y - self.target_size[1]/2,
                x2=self.target_size[0],
                y2=center_y + self.target_size[1]/2
            )

        return clip.resized(self.target_size)

    def _add_subtitles(self, video: VideoFileClip, subtitles: List[Dict]) -> CompositeVideoClip:
        """Add burned-in subtitles to the video."""
        subtitle_clips = [video]

        for sub in subtitles:
            # Social media style: Bold, centered, safe area
            txt_clip = TextClip(
                text=sub['word'].upper(),
                font_size=70,
                color='yellow',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(video.w * 0.8, None)
            ).with_start(sub['start']).with_duration(sub['end'] - sub['start']).with_position(('center', video.h * 0.75))

            subtitle_clips.append(txt_clip)

        return CompositeVideoClip(subtitle_clips)
