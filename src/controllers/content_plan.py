"""
controllers/content_plan.py — Pipeline controller for content plan generation.

GRASP Controller: transcribes the video → optionally detects moments → generates
                  a viral content plan via Claude, all on a daemon thread.
DIP: Depends on service interfaces, not on tkinter or ffmpeg directly.
"""

import os
import threading
from typing import Any, cast

import whisper as _whisper_module
import ffmpeg as _ffmpeg

from src.analysis.content_planner import generate_plan
from src.analysis.detector import detect_moments
from src.controllers import OperationCancelledError
from src.controllers.clips import ClipsController
from src.models import AnalysisStrategy


def _video_duration(path: str) -> float:
    probe = _ffmpeg.probe(path)
    return float(probe["format"]["duration"])


class ContentPlanController:
    """
    Runs the content-plan pipeline in a daemon thread.

    Pipeline stages:
        1. Transcribe with Whisper (word timestamps)
        1b. Optional moment analysis (audio / visual / vision strategies)
        2. Generate viral content plan with Claude

    Cancellation is checked between every stage.  The current long operation
    (Whisper or Claude) finishes before the cancellation takes effect.

    Args:
        on_stage:    ``(text: str) → None`` — shown in the sidebar status label.
        on_success:  ``(plan_text: str) → None``
        on_error:    ``(message: str) → None``
        on_done:     ``() → None``
        on_log:      ``(message: str, level: str) → None`` — activity log entries.
    """

    def __init__(
        self,
        on_stage,
        on_success,
        on_error,
        on_done,
        on_log=None,
    ):
        self._on_stage   = on_stage
        self._on_success = on_success
        self._on_error   = on_error
        self._on_done    = on_done
        self._on_log     = on_log

    def run(
        self,
        path:                str,
        model_name:          str,
        api_key:             str,
        claude_model:        str,
        focus:               str  = "All highlights",
        max_highlights:      int  = 5,
        context:             str  = "",
        analysis_strategies: set  = None,
        cancel_event:        threading.Event = None,
    ) -> None:
        """Start the pipeline in a daemon thread; returns immediately."""
        threading.Thread(
            target=self._worker,
            args=(
                path, model_name, api_key, claude_model,
                focus, max_highlights, context,
                analysis_strategies or set(),
                cancel_event or threading.Event(),
            ),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private — pipeline
    # ------------------------------------------------------------------

    def _worker(
        self,
        path:                str,
        model_name:          str,
        api_key:             str,
        claude_model:        str,
        focus:               str,
        max_highlights:      int,
        context:             str,
        analysis_strategies: set,
        cancel_event:        threading.Event,
    ) -> None:
        def _log(msg: str, level: str = "info") -> None:
            if self._on_log:
                self._on_log(msg, level)

        def _check_cancel() -> None:
            if cancel_event.is_set():
                raise OperationCancelledError("Content plan generation cancelled by user.")

        try:
            filename = os.path.basename(path)

            # ── Stage 1: Transcribe ────────────────────────────────────
            self._on_stage("Transcribing video…")
            _log(f"Transcribing: {filename}  model={model_name}", "stage")
            _log("  word_timestamps=True  task=transcribe", "detail")

            model        = _whisper_module.load_model(model_name)
            result       = cast(dict[str, Any], model.transcribe(path, verbose=False, word_timestamps=True))
            whisper_segs = result.get("segments", []) or []
            video_dur    = _video_duration(path)

            _log(f"Whisper complete — {len(whisper_segs)} segment(s)  duration={video_dur:.1f}s", "detail")
            _check_cancel()

            # ── Stage 1b: Moment analysis (optional) ──────────────────
            moments: list[dict] = []
            if analysis_strategies:
                names = ", ".join(s.value.replace("_", " ") for s in analysis_strategies)
                self._on_stage(f"Analysing moments  ({names})…")
                _log(f"Moment analysis: {names}", "stage")
                moments = detect_moments(
                    video_path     = path,
                    whisper_segs   = whisper_segs,
                    strategies     = analysis_strategies,
                    video_duration = video_dur,
                    api_key        = api_key,
                    claude_model   = claude_model,
                )
                _log(f"  {len(moments)} moment(s) detected", "detail")
                _check_cancel()

            transcript = ClipsController._build_timestamped_transcript(whisper_segs, moments)

            # ── Stage 2: Generate content plan ─────────────────────────
            self._on_stage("Generating content plan with Claude…")
            _log("Generating content plan…", "stage")
            plan_text = generate_plan(
                transcript     = transcript,
                api_key        = api_key,
                claude_model   = claude_model,
                focus          = focus,
                max_highlights = max_highlights,
                context        = context,
                on_log         = self._on_log,
            )
            _check_cancel()

            _log("Content plan ready.", "success")
            self._on_success(plan_text)

        except OperationCancelledError:
            _log("Content plan generation cancelled.", "warn")
            self._on_error("Operation was cancelled.")
        except Exception as exc:
            _log(f"Error: {exc}", "error")
            self._on_error(str(exc))
        finally:
            self._on_done()
