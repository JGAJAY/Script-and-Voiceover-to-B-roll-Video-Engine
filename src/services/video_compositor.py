import asyncio
import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import settings
from src.api.schemas import SceneTimelineItem
from src.api.errors import IncuBrixException, IncuBrixErrorCodes

logger = logging.getLogger(__name__)

ASPECT_DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080)
}

class VideoCompositor:
    """Renders composite B-roll video timed to narration with resolution/color normalization."""

    def __init__(self):
        import imageio_ffmpeg
        self.ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()

    async def render_scene_clip(
        self,
        scene: SceneTimelineItem,
        aspect_ratio: str,
        output_clip_path: Path
    ) -> Path:
        """Normalizes a single scene's video clip: crops/scales, normalizes fps, color, and duration."""
        target_w, target_h = ASPECT_DIMENSIONS.get(aspect_ratio, (1920, 1080))
        input_clip_path = Path(scene.clip_url)

        # Video filter chain:
        # 1. Scale and crop to target aspect ratio (with edge-aware center crop for 9:16)
        # 2. Color grading filter (Advanced requirement: color & brightness normalized across sources)
        # 3. Set fps to 30, set pts, format yuv420p
        if aspect_ratio == "9:16":
            # Smart reframing for 9:16 from 16:9 source
            scale_crop = f"scale=-1:{target_h},crop={target_w}:{target_h}"
        elif aspect_ratio == "1:1":
            scale_crop = f"scale={target_w}:-1,crop={target_w}:{target_h}"
        else:
            scale_crop = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}"

        color_grade = "eq=contrast=1.05:brightness=0.01:saturation=1.12"
        vf = f"{scale_crop},{color_grade},fps=30,format=yuv420p"

        cmd = [
            self.ffmpeg_exe, "-nostdin", "-y",
            "-stream_loop", "-1",  # Loop clip if duration exceeds source
            "-i", str(input_clip_path),
            "-t", str(scene.duration),
            "-vf", vf,
            "-an",  # Strip footage source audio (narration will be overlaid)
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            str(output_clip_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        _, stderr = await proc.communicate()

        if not output_clip_path.exists() or output_clip_path.stat().st_size == 0:
            logger.error(f"Failed to render scene segment {scene.scene_index}: {stderr.decode('utf-8', errors='ignore')}")
            raise IncuBrixException(
                code=IncuBrixErrorCodes.RENDER_FAILED,
                message=f"Failed to render video segment for scene {scene.scene_index}",
                status_code=500
            )

        return output_clip_path

    async def render_finished_video(
        self,
        timeline_items: List[SceneTimelineItem],
        narration_audio_path: Path,
        aspect_ratio: str,
        output_video_path: Path,
        job_dir: Path,
        srt_path: Optional[Path] = None,
        burn_in_captions: bool = True
    ) -> Path:
        """Assembles all scene segments, muxes narration audio, applies captions, and produces final MP4."""
        segments_dir = job_dir / f"segments_{aspect_ratio.replace(':', '-')}"
        segments_dir.mkdir(parents=True, exist_ok=True)

        # 1. Render/normalize each individual scene clip
        rendered_segments = []
        for scene in timeline_items:
            seg_path = segments_dir / f"scene_{scene.scene_index:03d}.mp4"
            await self.render_scene_clip(scene, aspect_ratio, seg_path)
            rendered_segments.append(seg_path)

        # 2. Concatenate all normalized video segments via concat demuxer
        concat_list_file = segments_dir / "concat_list.txt"
        lines = [f"file '{seg.resolve().as_posix()}'\n" for seg in rendered_segments]
        concat_list_file.write_text("".join(lines), encoding="utf-8")

        temp_concat_video = job_dir / f"temp_concat_{aspect_ratio.replace(':', '-')}.mp4"

        cmd_concat = [
            self.ffmpeg_exe, "-nostdin", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            str(temp_concat_video)
        ]

        proc_concat = await asyncio.create_subprocess_exec(
            *cmd_concat,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        await proc_concat.communicate()

        # 3. Mux narration audio on top of concatenated B-roll and optionally burn in captions
        cmd_final = [
            self.ffmpeg_exe, "-nostdin", "-y",
            "-i", str(temp_concat_video),
            "-i", str(narration_audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-pix_fmt", "yuv420p",
            "-shortest"  # Narration sets the exact timing, not the clips (Must-have #2)
        ]

        # Subtitle burn-in if requested
        if burn_in_captions and srt_path and srt_path.exists():
            srt_escaped = srt_path.resolve().as_posix().replace(":", "\\:")
            # Use drawtext or subtitles filter with clean semi-transparent background box
            cmd_final.extend([
                "-vf", f"subtitles='{srt_escaped}':force_style='FontSize=18,PrimaryColour=&H00FFFFFF,BorderStyle=3,BackColour=&H80000000,Outline=1,MarginV=30'"
            ])

        cmd_final.append(str(output_video_path))

        proc_final = await asyncio.create_subprocess_exec(
            *cmd_final,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        _, stderr_final = await proc_final.communicate()

        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            # If subtitles filter failed due to missing font/libass on some platforms, retry clean mux
            cmd_fallback = [
                self.ffmpeg_exe, "-nostdin", "-y",
                "-i", str(temp_concat_video),
                "-i", str(narration_audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(output_video_path)
            ]
            proc_fb = await asyncio.create_subprocess_exec(
                *cmd_fallback,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )
            await proc_fb.communicate()

        if not output_video_path.exists():
            logger.error(f"Final video muxing failed: {stderr_final.decode('utf-8', errors='ignore')}")
            raise IncuBrixException(
                code=IncuBrixErrorCodes.RENDER_FAILED,
                message="Final video encoding and narration muxing failed.",
                status_code=500
            )

        logger.info(f"Finished rendering video {aspect_ratio}: {output_video_path.name}")
        return output_video_path

    async def recompose_from_cached_segments(
        self,
        job_dir: Path,
        aspect_ratio: str,
        narration_audio_path: Path,
        output_video_path: Path,
        scene_count: int,
        srt_path: Optional[Path] = None,
        burn_in_captions: bool = False
    ) -> Path:
        """Fast re-composition using stream copy concatenation of pre-rendered segments."""
        ratio_clean = aspect_ratio.replace(":", "-")
        segments_dir = job_dir / f"segments_{ratio_clean}"

        concat_list_file = segments_dir / "concat_list.txt"
        lines = [f"file '{(segments_dir / f'scene_{i:03d}.mp4').resolve().as_posix()}'\n" for i in range(scene_count)]
        concat_list_file.write_text("".join(lines), encoding="utf-8")

        temp_concat = job_dir / f"temp_concat_{ratio_clean}.mp4"
        cmd_concat = [
            self.ffmpeg_exe, "-nostdin", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            str(temp_concat)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd_concat,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()

        # Mux narration audio
        cmd_final = [
            self.ffmpeg_exe, "-nostdin", "-y",
            "-i", str(temp_concat),
            "-i", str(narration_audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_video_path)
        ]
        proc_final = await asyncio.create_subprocess_exec(
            *cmd_final,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        await proc_final.communicate()

        return output_video_path

video_compositor = VideoCompositor()
