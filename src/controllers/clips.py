"""
controllers/clips.py — Async orchestrator for the clip-generation pipeline.

GRASP Controller: coordinates TranscriptionService → ClipAnalyzer → VideoCutter
                  on a background thread, delivering progress updates and results
                  back to the UI via callbacks.
DIP: Depends on service interfaces, not on tkinter or ffmpeg directly.
"""

import threading
from typing import Any, cast

import whisper as _whisper_module

from src.clips.analyzer import ClipAnalyzer
from src.models import AnalysisStrategy, AspectRatio, ClipMode, ClipResult, ExportFormat, Segment
from src.analysis.detector import detect_moments
from src.transcription.service import TranscriptionService
from src.clips.cutter import VideoCutter
from src.clips.word_refiner import build_word_index, snap_to_word_boundary, refine_all_clips


def _get_video_duration(path: str) -> float:
    import ffmpeg
    probe = ffmpeg.probe(path)
    return float(probe["format"]["duration"])


DEFAULT_MIN_SEGMENT_DURATION = 0.5   # seconds; user can override via the UI


class ClipsController:
    """
    Runs the full clip-generation pipeline in a daemon thread.

    Pipeline stages:
        1. Transcribe with word timestamps → seg_boundaries, word_index
        1b. (HIGHLIGHTS mode) Audio RMS scan → energy_windows injected into transcript
        2. Ask Claude to identify viral moments (mode-aware prompt)
        2b. Snap boundaries — segment-level (default) or word-level (allow_cut_anywhere)
        2c. Drop segments that are too short to be coherent
        2d. Word-level refinement — trim fillers, remove stutters
        3. Cut + format each clip (segment-aware, aspect-ratio-aware)
    """

    def __init__(
        self,
        transcription_service: TranscriptionService,
        clip_analyzer: ClipAnalyzer,
        video_cutter: VideoCutter,
        on_stage,
        on_clip_done,
        on_success,
        on_error,
        on_done,
    ):
        self._svc      = transcription_service
        self._analyzer = clip_analyzer
        self._cutter   = video_cutter

        self._on_stage     = on_stage
        self._on_clip_done = on_clip_done
        self._on_success   = on_success
        self._on_error     = on_error
        self._on_done      = on_done

    def run(
        self,
        path:                  str,
        model_name:            str,
        max_clips:             int,
        api_key:               str,
        claude_model:          str,
        clip_mode:             ClipMode    = ClipMode.SINGLE_SHOT,
        aspect_ratio:          AspectRatio = AspectRatio.ORIGINAL,
        custom_instructions:   str         = "",
        allow_cut_anywhere:    bool        = False,
        min_segment_duration:  float       = DEFAULT_MIN_SEGMENT_DURATION,
        prompt_override:       str         = "",
        analysis_strategies:   set         = None,
    ) -> None:
        """Start the pipeline in a daemon thread; returns immediately."""
        threading.Thread(
            target=self._worker,
            args=(
                path, model_name, max_clips, api_key, claude_model,
                clip_mode, aspect_ratio, custom_instructions,
                allow_cut_anywhere, min_segment_duration, prompt_override,
                analysis_strategies or set(),
            ),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private — pipeline
    # ------------------------------------------------------------------

    def _worker(
        self,
        path:                 str,
        model_name:           str,
        max_clips:            int,
        api_key:              str,
        claude_model:         str,
        clip_mode:            ClipMode,
        aspect_ratio:         AspectRatio,
        custom_instructions:  str,
        allow_cut_anywhere:   bool,
        min_segment_duration: float,
        prompt_override:      str,
        analysis_strategies:  set,
    ) -> None:
        try:
            # ── Stage 1: Transcribe ────────────────────────────────────
            self._on_stage("Transcribing video…")
            model  = _whisper_module.load_model(model_name)
            result = cast(dict[str, Any], model.transcribe(path, verbose=False, word_timestamps=True))
            raw_segments = result.get("segments", [])
            whisper_segs = raw_segments if isinstance(raw_segments, list) else []
            seg_boundaries = self._build_seg_boundaries(whisper_segs)
            word_index     = build_word_index(whisper_segs)
            video_duration = _get_video_duration(path)

            # ── Stage 1b: Moment analysis (strategy-driven) ───────────
            moments: list[dict] = []
            if analysis_strategies:
                strategy_names = ", ".join(
                    s.value.replace("_", " ") for s in analysis_strategies
                )
                self._on_stage(f"Analysing moments  ({strategy_names})…")
                moments = detect_moments(
                    video_path       = path,
                    whisper_segs     = whisper_segs,
                    strategies       = analysis_strategies,
                    video_duration   = video_duration,
                    api_key          = api_key,
                    claude_model     = claude_model,
                )

            timestamped = self._build_timestamped_transcript(whisper_segs, moments)

            # ── Stage 2: Analyse with Claude ──────────────────────────
            self._on_stage("Analysing transcript with Claude…")
            clips = self._analyzer.find_viral_moments(
                transcript           = timestamped,
                video_duration       = video_duration,
                max_clips            = max_clips,
                api_key              = api_key,
                clip_mode            = clip_mode,
                claude_model         = claude_model,
                custom_instructions  = custom_instructions,
                prompt_override      = prompt_override,
            )

            if not clips:
                raise ValueError(
                    "Claude returned no clip suggestions. "
                    "Try a different model, mode, or a longer video."
                )

            # ── Stage 2b: Snap to speech-segment or word boundaries ───
            if not allow_cut_anywhere:
                self._on_stage("Aligning cuts to speech boundaries…")
                clips = self._snap_boundaries(clips, seg_boundaries, video_duration)
            elif word_index:
                # Free-cut mode: still snap to word edges — never mid-phoneme
                self._on_stage("Snapping cuts to word boundaries…")
                clips = snap_to_word_boundary(clips, word_index, video_duration)

            # ── Stage 2c: Drop segments too short to be coherent ──────
            clips = self._filter_short_segments(clips, min_segment_duration)

            if not clips:
                raise ValueError(
                    "All clip segments were too short after boundary alignment. "
                    "Try a longer video or a different clip mode."
                )

            # ── Stage 2d: Word-level refinement ───────────────────────
            # Trim leading/trailing filler words and remove stutter runs.
            # Skipped gracefully when Whisper returned no word timestamps.
            if word_index:
                self._on_stage("Removing fillers and stutters…")
                clips = refine_all_clips(clips, word_index, min_segment_duration)

            if not clips:
                raise ValueError(
                    "All segments were removed during word-level refinement. "
                    "Try a longer video or a different clip mode."
                )

            # ── Stage 3: Cut each clip ────────────────────────────────
            for i, clip in enumerate(clips, start=1):
                n_segs = len(clip.segments)
                seg_label = "1 segment" if n_segs == 1 else f"{n_segs} segments"
                self._on_stage(f"Cutting clip {i}/{len(clips)}  ({seg_label}):  {clip.title}")

                clip.output_path = self._cutter.cut_clip(
                    source_path  = path,
                    segments     = clip.segments,
                    index        = i,
                    title        = clip.title,
                    aspect_ratio = aspect_ratio,
                )
                self._on_clip_done(clip)

            self._on_success(clips)

        except Exception as exc:
            self._on_error(str(exc))
        finally:
            self._on_done()

    # ------------------------------------------------------------------
    # Private — boundary helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_seg_boundaries(whisper_segments: list) -> list[dict]:
        """
        Extract start/end timestamps from every Whisper speech segment.

        Whisper segments are the primary semantic unit — each represents a
        natural spoken phrase separated by a pause. Using these as snap targets
        ensures cuts land in silence between complete thoughts rather than mid-word.
        """
        return [
            {"start": float(s["start"]), "end": float(s["end"])}
            for s in whisper_segments
        ]

    @staticmethod
    def _snap_boundaries(
        clips: list[ClipResult],
        boundaries: list[dict],
        video_duration: float,
    ) -> list[ClipResult]:
        """
        Snap every segment start/end to the nearest speech-segment boundary.

        start → beginning of the first speech segment whose END >= requested
                (snaps back into a segment we're inside, or forward to the next)
        end   → end of the last speech segment whose START <= requested
                (extends to complete a segment we're inside, or retreats to previous)

        The strictly_after guard on start prevents any speech segment from being
        included twice in consecutive cuts (eliminates the repeated-word jitter bug).

        Segments where end <= start after snapping are dropped as invalid fragments.
        Clips that lose all segments retain their original segments as a fallback.
        """
        if not boundaries:
            return clips

        for clip in clips:
            snapped: list[Segment] = []
            prev_end: float = -1.0

            for seg in clip.segments:
                s = ClipsController._snap_start(seg.start, boundaries, strictly_after=prev_end)
                e = ClipsController._snap_end(seg.end, boundaries, video_duration)
                if e > s:
                    snapped.append(Segment(s, e))
                    prev_end = e

            if snapped:
                clip.segments = snapped
        return clips

    @staticmethod
    def _snap_start(
        requested: float,
        boundaries: list[dict],
        strictly_after: float = -1.0,
    ) -> float:
        """
        Return the START of the first boundary entry that:
          1. has not already been covered  (entry.start > strictly_after)
          2. spans or follows the cut point (entry.end >= requested)

        Falls back to the first uncovered entry so we never regress into an
        already-included region.
        """
        first_unused: float | None = None
        for b in boundaries:
            if b["start"] <= strictly_after:
                continue
            if first_unused is None:
                first_unused = b["start"]
            if b["end"] >= requested:
                return b["start"]
        return first_unused if first_unused is not None else requested

    @staticmethod
    def _snap_end(
        requested: float,
        boundaries: list[dict],
        video_duration: float,
    ) -> float:
        """
        Return the END of the last boundary entry whose START <= requested.

        Extends through any entry we're inside (so a word/segment started
        before the cut point is always finished), or retreats to the previous
        entry's end when the cut falls in silence.
        """
        best = requested
        for b in boundaries:
            if b["start"] <= requested:
                best = b["end"]
        return min(best, video_duration)

    @staticmethod
    def _filter_short_segments(
        clips: list[ClipResult],
        min_duration: float,
    ) -> list[ClipResult]:
        """
        Drop segments shorter than *min_duration* seconds.

        Short segments after snapping are noise — fragments of a sentence that
        don't convey a complete thought and make edits feel choppy.
        Clips that lose all segments after filtering are removed entirely.
        """
        valid_clips: list[ClipResult] = []
        for clip in clips:
            clip.segments = [s for s in clip.segments if s.duration >= min_duration]
            if clip.segments:
                valid_clips.append(clip)
        return valid_clips

    # ------------------------------------------------------------------
    # Private — transcript builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_timestamped_transcript(
        segments: list,
        moments: list[dict] | None = None,
    ) -> str:
        """
        Build a Claude-readable transcript with explicit start/end timestamps,
        [SILENCE] markers, and optional moment markers from analysis strategies.

        Moment markers (PEAK, MOTION, VISUAL, …) are injected inline at the
        correct chronological position so Claude can correlate high-interest
        windows with the surrounding speech.  Each moment dict must supply a
        pre-formatted "transcript_line" string (produced by moment_detector).
        """
        def fmt(secs: float) -> str:
            m, s = divmod(int(secs), 60)
            h, m = divmod(m, 60)
            frac = int((secs - int(secs)) * 10)
            return f"{h:02d}:{m:02d}:{s:02d}.{frac}"

        sorted_moments = sorted(moments or [], key=lambda p: p["start"])
        moment_idx = 0
        lines: list[str] = []
        prev_end: float | None = None

        for seg in segments:
            start = float(seg["start"])
            end   = float(seg["end"])

            if prev_end is not None:
                gap = start - prev_end
                if gap > 0.3:
                    lines.append(f"[SILENCE: {gap:.1f}s]")

            # Inject any moment markers that begin before this speech segment
            while (
                moment_idx < len(sorted_moments)
                and sorted_moments[moment_idx]["start"] <= start
            ):
                lines.append(sorted_moments[moment_idx]["transcript_line"])
                moment_idx += 1

            lines.append(f"[{fmt(start)} -> {fmt(end)}]  {seg['text'].strip()}")
            prev_end = end

        # Flush any moments that fall after the last speech segment
        while moment_idx < len(sorted_moments):
            lines.append(sorted_moments[moment_idx]["transcript_line"])
            moment_idx += 1

        return "\n".join(lines)
