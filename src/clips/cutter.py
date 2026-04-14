"""
clips/cutter.py — ffmpeg-based clip extraction with flexible aspect ratio support.

SRP: Only responsible for cutting video segments and formatting the output.
     No LLM, no UI, no transcription.

Multi-segment workflow:
    Each segment is encoded individually (with aspect ratio applied), written to
    a temp file, then all temp files are joined via the ffmpeg concat demuxer.
    Temp files are deleted on completion.
"""

import os
import re
import tempfile

import ffmpeg

from src.models import ASPECT_RATIO_SIZES, CLIP_BITRATE, CLIP_FPS, AspectRatio, Segment


def _safe_filename(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:40]


class VideoCutter:
    """
    Assembles one output clip from one or more source segments.

    For a single segment: trim + optionally reformat, done.
    For multiple segments: encode each to a temp file, then concatenate.
    """

    def cut_clip(
        self,
        source_path: str,
        segments:    list[Segment],
        index:       int,
        title:       str,
        aspect_ratio: AspectRatio = AspectRatio.ORIGINAL,
    ) -> str:
        """
        Extract *segments* from *source_path*, apply *aspect_ratio*, and save.

        Output file: ``clip_01_<slug>.mp4`` placed next to the source.

        Args:
            source_path: Absolute path to the original video.
            segments: One or more (start, end) windows to include.
            index: 1-based clip number for filename ordering.
            title: Human-readable clip title (used in filename slug).
            aspect_ratio: Target output aspect ratio.

        Returns:
            Absolute path to the saved clip file.
        """
        slug       = _safe_filename(title)
        out_dir    = os.path.dirname(source_path)
        output_path = os.path.join(out_dir, f"clip_{index:02d}_{slug}.mp4")

        if len(segments) == 1:
            self._encode_segment(source_path, segments[0], output_path, aspect_ratio)
        else:
            self._encode_and_concat(source_path, segments, output_path, aspect_ratio)

        return output_path

    # ------------------------------------------------------------------
    # Private — encoding
    # ------------------------------------------------------------------

    def _encode_segment(
        self,
        source_path:  str,
        seg:          Segment,
        output_path:  str,
        aspect_ratio: AspectRatio,
    ) -> None:
        """Encode a single segment with optional aspect ratio conversion."""
        stream = ffmpeg.input(source_path, ss=seg.start, t=seg.duration)
        video  = self._apply_aspect_ratio(stream.video, aspect_ratio)
        audio  = stream.audio

        (
            ffmpeg
            .output(
                video,
                audio,
                output_path,
                vcodec="libx264",
                acodec="aac",
                video_bitrate=CLIP_BITRATE,
                r=CLIP_FPS,
                movflags="+faststart",
            )
            .overwrite_output()
            .run(quiet=True)
        )

    def _encode_and_concat(
        self,
        source_path:  str,
        segments:     list[Segment],
        output_path:  str,
        aspect_ratio: AspectRatio,
    ) -> None:
        """Encode each segment individually, then concatenate into one file."""
        tmp_paths: list[str] = []
        tmp_dir = tempfile.gettempdir()

        try:
            # Step 1: encode each segment to a temp file
            for i, seg in enumerate(segments):
                tmp = os.path.join(tmp_dir, f"_whisperui_tmp_{i}.mp4")
                self._encode_segment(source_path, seg, tmp, aspect_ratio)
                tmp_paths.append(tmp)

            # Step 2: write ffmpeg concat list
            list_file = os.path.join(tmp_dir, "_whisperui_concat.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for p in tmp_paths:
                    # Use forward slashes and quote the path for safety
                    f.write(f"file '{p.replace(chr(92), '/')}'\n")

            # Step 3: concatenate (stream copy — no re-encoding needed)
            (
                ffmpeg
                .input(list_file, format="concat", safe=0)
                .output(output_path, c="copy", movflags="+faststart")
                .overwrite_output()
                .run(quiet=True)
            )

        finally:
            # Step 4: clean up temp files
            for p in tmp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass
            try:
                os.unlink(list_file)
            except (OSError, UnboundLocalError):
                pass

    # ------------------------------------------------------------------
    # Private — aspect ratio filter
    # ------------------------------------------------------------------

    def _apply_aspect_ratio(self, video_stream, aspect_ratio: AspectRatio):
        """
        Apply scale + pad to fit *video_stream* into the target aspect ratio.

        Uses ``force_original_aspect_ratio=decrease`` so the source frame is
        scaled down to fit inside the target box without cropping, then padded
        with black bars to reach the exact target dimensions.

        For ``AspectRatio.ORIGINAL`` the stream is returned unchanged.
        """
        dims = ASPECT_RATIO_SIZES[aspect_ratio]
        if dims is None:
            return video_stream   # ORIGINAL — no spatial change

        w, h = dims
        return (
            video_stream
            .filter("scale", w, h, force_original_aspect_ratio="decrease")
            .filter("pad", w, h, "(ow-iw)/2", "(oh-ih)/2", color="black")
        )
