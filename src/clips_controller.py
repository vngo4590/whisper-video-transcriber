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
from src.models import AspectRatio, ClipMode, ClipResult, ExportFormat
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
    def _build_timestamped_transcript(segments: list) -> str:
        lines = []
        for seg in segments:
            s = seg["start"]
            m, sec = divmod(int(s), 60)
            h, m   = divmod(m, 60)
            lines.append(f"[{h:02d}:{m:02d}:{sec:02d}]  {seg['text'].strip()}")
        return "\n".join(lines)
