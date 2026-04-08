"""
clips_controller.py — Async orchestrator for the clip-generation pipeline.

GRASP Controller: coordinates TranscriptionService → ClipAnalyzer → VideoCutter
                  on a background thread, delivering progress updates and results
                  back to the UI via callbacks.
DIP: Depends on service interfaces, not on tkinter or ffmpeg directly.
"""

import threading

import whisper as _whisper_module

from src.clip_analyzer import ClipAnalyzer
from src.models import AspectRatio, ClipMode, ClipResult, ExportFormat, Segment
from src.transcriber import TranscriptionService
from src.video_cutter import VideoCutter


def _get_video_duration(path: str) -> float:
    import ffmpeg
    probe = ffmpeg.probe(path)
    return float(probe["format"]["duration"])


class ClipsController:
    """
    Runs the full clip-generation pipeline in a daemon thread.

    Pipeline stages:
        1. Transcribe with word timestamps
        2. Ask Claude to identify viral moments (mode-aware prompt)
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
        path:                 str,
        model_name:           str,
        max_clips:            int,
        api_key:              str,
        claude_model:         str,
        clip_mode:            ClipMode    = ClipMode.SINGLE_SHOT,
        aspect_ratio:         AspectRatio = AspectRatio.ORIGINAL,
        custom_instructions:  str         = "",
    ) -> None:
        """Start the pipeline in a daemon thread; returns immediately."""
        threading.Thread(
            target=self._worker,
            args=(path, model_name, max_clips, api_key, claude_model, clip_mode, aspect_ratio, custom_instructions),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _worker(
        self,
        path:                str,
        model_name:          str,
        max_clips:           int,
        api_key:             str,
        claude_model:        str,
        clip_mode:           ClipMode,
        aspect_ratio:        AspectRatio,
        custom_instructions: str,
    ) -> None:
        try:
            # ── Stage 1: Transcribe ────────────────────────────────────
            self._on_stage("Transcribing video…")
            model  = _whisper_module.load_model(model_name)
            result = model.transcribe(path, verbose=False, word_timestamps=True)
            segments       = result["segments"]
            all_words      = self._extract_words(segments)
            timestamped    = self._build_timestamped_transcript(segments)
            video_duration = _get_video_duration(path)

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
            )

            if not clips:
                raise ValueError(
                    "Claude returned no clip suggestions. "
                    "Try a different model, mode, or a longer video."
                )

            # ── Stage 2b: Snap boundaries to word edges ───────────────
            # Claude picks timestamps in seconds that may land mid-syllable.
            # Snap every start/end to the nearest Whisper word boundary so
            # VideoCutter never cuts in the middle of a spoken word.
            self._on_stage("Aligning cut points to word boundaries…")
            clips = self._snap_to_word_boundaries(clips, all_words, video_duration)

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

    @staticmethod
    def _extract_words(segments: list) -> list[dict]:
        """
        Flatten all Whisper word-level timestamps into one list sorted by start.

        Each entry: {"start": float, "end": float}
        Returns an empty list when word timestamps are unavailable.
        """
        words: list[dict] = []
        for seg in segments:
            for w in seg.get("words", []):
                if "start" in w and "end" in w:
                    words.append({"start": float(w["start"]), "end": float(w["end"])})
        return words

    @staticmethod
    def _snap_to_word_boundaries(
        clips: list[ClipResult],
        words: list[dict],
        video_duration: float,
    ) -> list[ClipResult]:
        """
        Snap every segment start/end to the nearest word boundary.

        Rules:
          start → beginning of the first word whose END is ≥ requested time,
                  subject to strictly_after: words already covered by the
                  previous segment in the same clip are skipped so no word
                  is ever repeated at a cut boundary (the jitter bug).
          end   → ending of the last word whose START is ≤ requested time.

        Segments that become invalid after snapping (end ≤ start) are dropped.
        Clips that lose all segments keep their original segments as a fallback.
        """
        if not words:
            return clips   # no word data — leave boundaries as-is

        for clip in clips:
            snapped: list[Segment] = []
            # prev_end tracks the snapped end of the previous segment so
            # _snap_start can skip words already included there.
            prev_end: float = -1.0

            for seg in clip.segments:
                s = ClipsController._snap_start(seg.start, words, strictly_after=prev_end)
                e = ClipsController._snap_end(seg.end, words, video_duration)
                if e > s:
                    snapped.append(Segment(s, e))
                    prev_end = e   # update guard for the next segment

            if snapped:
                clip.segments = snapped
            # else: keep original segments (safety fallback)
        return clips

    @staticmethod
    def _snap_start(
        requested: float,
        words: list[dict],
        strictly_after: float = -1.0,
    ) -> float:
        """
        Return the START of the first word that satisfies both:
          1. word.start > strictly_after  (not already in the previous segment)
          2. word.end   >= requested      (the word spans or follows the cut point)

        If no word satisfies both conditions, fall back to the start of the
        first word not yet used (strictly_after guard only), so we never
        return a timestamp that re-enters an already-covered region.
        """
        first_unused: float | None = None
        for w in words:
            if w["start"] <= strictly_after:
                continue                        # already covered — skip
            if first_unused is None:
                first_unused = w["start"]       # earliest available word
            if w["end"] >= requested:
                return w["start"]               # correct snap target found
        # No word satisfied condition 2 — use earliest available as fallback
        return first_unused if first_unused is not None else requested

    @staticmethod
    def _snap_end(requested: float, words: list[dict], video_duration: float) -> float:
        """
        Return the END of the last word whose start is <= *requested*.

        Walking forwards, we keep updating `best` with each word that has
        already started by *requested*. The final value is the end of the
        last word that was at least partially spoken before the cut point —
        either the word we're inside (extend to its end) or the previous word
        (retreat to its end) if we landed in a silence gap.
        """
        best = requested
        for w in words:
            if w["start"] <= requested:
                best = w["end"]
        return min(best, video_duration)

    @staticmethod
    def _build_timestamped_transcript(segments: list) -> str:
        """
        Build a Claude-readable transcript with explicit start→end timestamps
        and [SILENCE: X.Xs] markers between segments so the model knows exactly
        where dead air lives and can avoid including it in clip boundaries.
        """
        def fmt(secs: float) -> str:
            m, s = divmod(int(secs), 60)
            h, m = divmod(m, 60)
            frac = int((secs - int(secs)) * 10)
            return f"{h:02d}:{m:02d}:{s:02d}.{frac}"

        lines = []
        prev_end: float | None = None

        for seg in segments:
            start = seg["start"]
            end   = seg["end"]

            if prev_end is not None:
                gap = start - prev_end
                if gap > 0.3:
                    lines.append(f"[SILENCE: {gap:.1f}s]")

            lines.append(f"[{fmt(start)} → {fmt(end)}]  {seg['text'].strip()}")
            prev_end = end

        return "\n".join(lines)
