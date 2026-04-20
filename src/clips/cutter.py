"""
clips/cutter.py — ffmpeg-based clip extraction with flexible aspect ratio support.

SRP: Only responsible for cutting video segments and formatting the output.
     No LLM, no UI, no transcription.

Multi-segment workflow:
    Each segment is encoded individually (with aspect ratio applied), written to
    a temp file, then all temp files are joined via the ffmpeg concat demuxer.
    Temp files are deleted on completion.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import ffmpeg

from src.models import ASPECT_RATIO_SIZES, CLIP_BITRATE, CLIP_FPS, AspectRatio, ClipResult, Segment

# ---------------------------------------------------------------------------
# SRT helpers used by burn_captions
# ---------------------------------------------------------------------------

_SRT_BLOCK = re.compile(
    r"\d+\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)",
    re.DOTALL,
)


def _srt_to_secs(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _secs_to_srt(secs: float) -> str:
    secs = max(0.0, secs)
    ms = int(round(secs * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


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

    def cut_raw_segments(
        self,
        source_path:    str,
        clips:          list[ClipResult],
        padding:        float,
        video_duration: float,
        aspect_ratio:   AspectRatio = AspectRatio.ORIGINAL,
        on_progress=None,
    ) -> str:
        """
        Cut each segment of every clip individually (with padding) and save
        them into an organised folder next to the source video.

        Folder layout::

            <source_dir>/
              <video_stem>/
                metadata.json
                clip_01_<title>/
                  seg_01.mp4
                  seg_02.mp4
                clip_02_<title>/
                  seg_01.mp4

        Args:
            source_path:    Path to the original video.
            clips:          ClipResult list from the analyzer.
            padding:        Seconds added to each end of every segment.
            video_duration: Total video length (used to clamp padded end).
            aspect_ratio:   Applied to each output segment.
            on_progress:    Optional ``(clip_idx, seg_idx, total_segs, out_path)``
                            callback fired after each segment is written.

        Returns:
            Absolute path to the output folder (``<source_dir>/<video_stem>/``).

        Side-effect:
            Sets ``clip.output_path`` to the clip's subfolder for every clip
            so the UI "Open folder" button works without extra wiring.
        """
        video_stem = Path(source_path).stem
        out_root   = Path(source_path).parent / _safe_filename(video_stem)
        out_root.mkdir(exist_ok=True)

        total_segs = sum(len(c.segments) for c in clips)

        for clip_idx, clip in enumerate(clips, start=1):
            clip_dir = out_root / f"clip_{clip_idx:02d}_{_safe_filename(clip.title)}"
            clip_dir.mkdir(exist_ok=True)
            clip.output_path = str(clip_dir)

            for seg_idx, seg in enumerate(clip.segments, start=1):
                padded = Segment(
                    start = max(0.0, seg.start - padding),
                    end   = min(video_duration, seg.end + padding),
                )
                out_path = str(clip_dir / f"seg_{seg_idx:02d}.mp4")
                self._encode_segment(source_path, padded, out_path, aspect_ratio)
                if on_progress:
                    on_progress(clip_idx, seg_idx, total_segs, out_path)

        self._write_metadata(out_root, source_path, clips, padding)
        return str(out_root)

    def _write_metadata(
        self,
        out_root:    Path,
        source_path: str,
        clips:       list[ClipResult],
        padding:     float,
    ) -> None:
        """Write metadata.json describing all clips and their padded segments."""
        def seg_dict(s: Segment, pad: float, dur: float) -> dict:
            return {
                "original_start": s.start,
                "original_end":   s.end,
                "padded_start":   max(0.0, s.start - pad),
                "padded_end":     min(dur, s.end + pad),
            }

        # Infer video duration from the last segment end (already clamped upstream)
        video_duration = max(
            (c.segments[-1].end for c in clips if c.segments),
            default=0.0,
        )

        payload = {
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "source_video":   os.path.basename(source_path),
            "padding_seconds": padding,
            "clips": [
                {
                    "index":       i,
                    "title":       c.title,
                    "hook":        c.hook,
                    "reason":      c.reason,
                    "category":    c.category,
                    "tags":        c.tags,
                    "description": c.description,
                    "hashtags":    c.hashtags,
                    "narrative":   c.narrative,
                    "strategy":    c.strategy,
                    "cta_hint":    c.cta_hint,
                    "peak":        c.peak,
                    "folder":      os.path.basename(c.output_path),
                    "segments":    [seg_dict(s, padding, video_duration) for s in c.segments],
                }
                for i, c in enumerate(clips, start=1)
            ],
        }
        with open(out_root / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

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
    # Public — caption burn-in
    # ------------------------------------------------------------------

    def burn_captions(
        self,
        clip_path: str,
        srt_path: str,
        clip_start: float,
        clip_end: float,
    ) -> str:
        """
        Burn SRT captions into an existing single-segment clip.

        Parses *srt_path*, filters entries that fall within [clip_start, clip_end],
        shifts all timestamps by -clip_start so they align with the clip timeline,
        writes a temporary SRT, then re-encodes via ffmpeg with the subtitles filter.

        Args:
            clip_path:  Path to the existing clip file.
            srt_path:   Path to the full-video SRT file.
            clip_start: Start time (seconds) of the clip in the source video.
            clip_end:   End time (seconds) of the clip in the source video.

        Returns:
            Path to the new captioned clip (``clip_path`` with ``_captioned`` suffix).

        Raises:
            FileNotFoundError: If *srt_path* does not exist.
            ValueError:        If no SRT entries fall within the clip range.
        """
        if not os.path.exists(srt_path):
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        srt_text = open(srt_path, encoding="utf-8").read()
        entries: list[tuple[float, float, str]] = []
        for m in _SRT_BLOCK.finditer(srt_text):
            ts_start = _srt_to_secs(m.group(1))
            ts_end   = _srt_to_secs(m.group(2))
            body     = m.group(3).strip()
            # Include entry if it overlaps with the clip range at all
            if ts_start < clip_end and ts_end > clip_start:
                new_start = max(0.0, ts_start - clip_start)
                new_end   = max(0.0, ts_end   - clip_start)
                entries.append((new_start, new_end, body))

        if not entries:
            raise ValueError("No SRT entries found in the clip's time range.")

        # Write adjusted SRT to a temp file in the same directory as the clip
        tmp_srt = os.path.join(tempfile.gettempdir(), "_whisperui_burn.srt")
        with open(tmp_srt, "w", encoding="utf-8") as f:
            for i, (s, e, body) in enumerate(entries, start=1):
                f.write(f"{i}\n{_secs_to_srt(s)} --> {_secs_to_srt(e)}\n{body}\n\n")

        base, ext = os.path.splitext(clip_path)
        out_path = base + "_captioned" + ext

        # Escape the SRT path for ffmpeg's subtitles filter (Windows: \ → /, : → \:)
        srt_escaped = tmp_srt.replace("\\", "/").replace(":", "\\:")

        try:
            (
                ffmpeg
                .input(clip_path)
                .output(
                    out_path,
                    vf=f"subtitles='{srt_escaped}'",
                    acodec="aac",
                    vcodec="libx264",
                    video_bitrate=CLIP_BITRATE,
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(quiet=True)
            )
        finally:
            try:
                os.unlink(tmp_srt)
            except OSError:
                pass

        return out_path

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
