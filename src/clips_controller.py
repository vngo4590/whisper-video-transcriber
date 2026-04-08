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
from src.models import ClipResult, ExportFormat
from src.transcriber import TranscriptionService
from src.video_cutter import VideoCutter


def _get_video_duration(path: str) -> float:
    """Return video duration in seconds using ffmpeg probe."""
    import ffmpeg
    probe = ffmpeg.probe(path)
    return float(probe["format"]["duration"])


class ClipsController:
    """
    Runs the full clip-generation pipeline in a daemon thread.

    Pipeline stages:
        1. Transcribe the video (reuses TranscriptionService)
        2. Ask Claude to identify viral moments (ClipAnalyzer)
        3. Cut + convert each clip (VideoCutter)

    All results and errors are delivered via callbacks on the calling thread
    (tkinter's ``after`` is NOT used here — callers wire their own scheduling).

    Args:
        transcription_service: Provides transcription.
        clip_analyzer: Provides LLM-based moment detection.
        video_cutter: Provides ffmpeg clip extraction.
        on_stage: Called with a status string at each pipeline stage.
        on_clip_done: Called with a ClipResult after each clip is cut.
        on_success: Called with the full list of ClipResults on completion.
        on_error: Called with an error message string on failure.
        on_done: Always called after success or error (for UI cleanup).
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
        path: str,
        model_name: str,
        max_clips: int,
        api_key: str,
        claude_model: str,
    ) -> None:
        """Start the pipeline in a daemon thread; returns immediately."""
        threading.Thread(
            target=self._worker,
            args=(path, model_name, max_clips, api_key, claude_model),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _worker(self, path: str, model_name: str, max_clips: int, api_key: str, claude_model: str) -> None:
        try:
            # ── Stage 1: Transcribe ────────────────────────────────────
            self._on_stage("Transcribing video…")
            plain_text = self._svc.transcribe(
                path=path,
                model_name=model_name,
                export_format=ExportFormat.PLAIN_TEXT,
                do_translate=False,
                max_words_per_subtitle=5,   # unused for plain text, ignored
            )

            # Build timestamped transcript for Claude context
            # Re-run to get segments (cheap: model already cached by whisper)
            model = _whisper_module.load_model(model_name)
            result = model.transcribe(path, verbose=False, word_timestamps=True)
            segments = result["segments"]
            timestamped = self._build_timestamped_transcript(segments)

            video_duration = _get_video_duration(path)

            # ── Stage 2: Analyse with Claude ──────────────────────────
            self._on_stage("Analysing transcript with Claude…")
            clips = self._analyzer.find_viral_moments(
                transcript=timestamped,
                video_duration=video_duration,
                max_clips=max_clips,
                api_key=api_key,
                claude_model=claude_model,
            )

            if not clips:
                raise ValueError("Claude returned no clip suggestions. Try a different model or longer video.")

            # ── Stage 3: Cut each clip ────────────────────────────────
            for i, clip in enumerate(clips, start=1):
                self._on_stage(f"Cutting clip {i} of {len(clips)}:  {clip.title}")
                clip.output_path = self._cutter.cut_clip(
                    source_path=path,
                    start=clip.start,
                    end=clip.end,
                    index=i,
                    title=clip.title,
                )
                self._on_clip_done(clip)

            self._on_success(clips)

        except Exception as exc:
            self._on_error(str(exc))
        finally:
            self._on_done()

    @staticmethod
    def _build_timestamped_transcript(segments: list) -> str:
        """Format segments as 'HH:MM:SS  text' lines for the LLM prompt."""
        lines = []
        for seg in segments:
            start = seg["start"]
            m, s = divmod(int(start), 60)
            h, m = divmod(m, 60)
            lines.append(f"[{h:02d}:{m:02d}:{s:02d}]  {seg['text'].strip()}")
        return "\n".join(lines)
