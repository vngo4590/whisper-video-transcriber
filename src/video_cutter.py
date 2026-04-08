"""
video_cutter.py — ffmpeg-based clip extraction and 9:16 conversion.

SRP: Only responsible for cutting video segments and reformatting them
     for vertical (TikTok) output. No LLM, no UI, no transcription.
"""

import os
import re

import ffmpeg

from src.models import CLIP_ASPECT_H, CLIP_ASPECT_W, CLIP_BITRATE, CLIP_FPS


def _safe_filename(text: str) -> str:
    """Convert arbitrary text to a safe filename fragment."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:40]


class VideoCutter:
    """
    Cuts a clip from a source video and pads it to 9:16 (1080×1920).

    The original 16:9 frame is scaled to fit within 1080 pixels wide,
    then centred vertically with black bars above and below so the output
    is always exactly CLIP_ASPECT_W × CLIP_ASPECT_H pixels.
    """

    def cut_clip(
        self,
        source_path: str,
        start: float,
        end: float,
        index: int,
        title: str,
    ) -> str:
        """
        Extract [start, end] from *source_path*, pad to 9:16, and save.

        The output file is placed in the same directory as the source.
        Filename: ``clip_01_<slug>.mp4``

        Args:
            source_path: Absolute path to the original video.
            start: Clip start time in seconds.
            end: Clip end time in seconds.
            index: 1-based clip number (for filename ordering).
            title: Human-readable clip title (used in filename slug).

        Returns:
            Absolute path to the saved clip file.
        """
        duration = end - start
        slug = _safe_filename(title)
        out_dir = os.path.dirname(source_path)
        output_path = os.path.join(out_dir, f"clip_{index:02d}_{slug}.mp4")

        (
            ffmpeg
            .input(source_path, ss=start, t=duration)
            .filter("scale", CLIP_ASPECT_W, -2)           # fit width to 1080, keep ratio
            .filter(                                        # pad height to 1920
                "pad",
                CLIP_ASPECT_W,
                CLIP_ASPECT_H,
                "(ow-iw)/2",                               # centre horizontally (already 0)
                "(oh-ih)/2",                               # centre vertically
                color="black",
            )
            .output(
                output_path,
                vcodec="libx264",
                acodec="aac",
                video_bitrate=CLIP_BITRATE,
                r=CLIP_FPS,
                movflags="+faststart",                     # optimise for streaming
            )
            .overwrite_output()
            .run(quiet=True)
        )

        return output_path
