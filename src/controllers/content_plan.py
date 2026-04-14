"""
controllers/content_plan.py — Pipeline controller for content plan generation.

GRASP Controller: transcribes the video → optionally detects moments → generates
                  a viral content plan via Claude, all on a daemon thread.
DIP: Depends on service interfaces, not on tkinter or ffmpeg directly.
"""

import threading
from typing import Any, cast

import whisper as _whisper_module
import ffmpeg as _ffmpeg

from src.analysis.content_planner import generate_plan
from src.analysis.detector import detect_moments
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
        2. Generate viral content plan with Claude (uses content_planner.generate_plan)

    Results are delivered via the callbacks supplied at construction time.
    """

    def __init__(
        self,
        on_stage,    # (text: str) -> None
        on_success,  # (plan_text: str) -> None
        on_error,    # (message: str) -> None
        on_done,     # () -> None
    ):
        self._on_stage   = on_stage
        self._on_success = on_success
        self._on_error   = on_error
        self._on_done    = on_done

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
    ) -> None:
        """Start the pipeline in a daemon thread; returns immediately."""
        threading.Thread(
            target=self._worker,
            args=(
                path, model_name, api_key, claude_model,
                focus, max_highlights, context,
                analysis_strategies or set(),
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
    ) -> None:
        try:
            # ── Stage 1: Transcribe ────────────────────────────────────
            self._on_stage("Transcribing video…")
            model        = _whisper_module.load_model(model_name)
            result       = cast(dict[str, Any], model.transcribe(path, verbose=False, word_timestamps=True))
            whisper_segs = result.get("segments", []) or []
            video_dur    = _video_duration(path)

            # ── Stage 1b: Moment analysis (optional) ──────────────────
            moments: list[dict] = []
            if analysis_strategies:
                names = ", ".join(s.value.replace("_", " ") for s in analysis_strategies)
                self._on_stage(f"Analysing moments  ({names})…")
                moments = detect_moments(
                    video_path     = path,
                    whisper_segs   = whisper_segs,
                    strategies     = analysis_strategies,
                    video_duration = video_dur,
                    api_key        = api_key,
                    claude_model   = claude_model,
                )

            # Reuse ClipsController's transcript builder — same format Claude already knows
            transcript = ClipsController._build_timestamped_transcript(whisper_segs, moments)

            # ── Stage 2: Generate content plan ─────────────────────────
            self._on_stage("Generating content plan with Claude…")
            plan_text = generate_plan(
                transcript     = transcript,
                api_key        = api_key,
                claude_model   = claude_model,
                focus          = focus,
                max_highlights = max_highlights,
                context        = context,
            )

            self._on_success(plan_text)

        except Exception as exc:
            self._on_error(str(exc))
        finally:
            self._on_done()
