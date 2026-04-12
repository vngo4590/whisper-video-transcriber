"""
moment_detector.py — Multi-strategy moment orchestrator.

GRASP Controller: coordinates the three analysis strategies (audio energy,
                  visual motion, vision model) and merges their results into
                  a unified, time-sorted list of transcript-ready moment dicts.

Each moment dict has:
    {"start": float, "end": float, "transcript_line": str}

The "transcript_line" is injected verbatim into the timestamped transcript
sent to Claude, so each strategy can use its own marker syntax.
"""

from src.models import AnalysisStrategy
from src.audio_analyzer import build_energy_windows
from src.visual_analyzer import build_motion_windows
from src.vision_analyzer import build_vision_windows


def detect_moments(
    video_path: str,
    whisper_segs: list,
    strategies: set,
    video_duration: float,
    api_key: str = "",
    claude_model: str = "",
) -> list[dict]:
    """
    Run every selected strategy and return merged, time-sorted moment dicts.

    Args:
        video_path:     Path to the source video.
        whisper_segs:   Whisper segment list (used by AUDIO_ENERGY for the
                        speech-overlap filter; ignored by other strategies).
        strategies:     Set of AnalysisStrategy members to run.
        video_duration: Total video length in seconds.
        api_key:        Anthropic API key (required only for VISION_MODEL).
        claude_model:   Claude model ID (required only for VISION_MODEL).

    Returns:
        List of {"start", "end", "transcript_line"} dicts sorted by start.
        Returns [] when strategies is empty or all analyzers return nothing.
    """
    moments: list[dict] = []

    if AnalysisStrategy.AUDIO_ENERGY in strategies:
        for p in build_energy_windows(video_path, whisper_segs):
            moments.append({
                "start": p["start"],
                "end":   p["end"],
                "transcript_line": (
                    f"[PEAK: {p['start']:.1f}s\u2013{p['end']:.1f}s, "
                    f"+{p['above_mean_db']:.1f}dB above mean]"
                ),
            })

    if AnalysisStrategy.VISUAL_MOTION in strategies:
        for m in build_motion_windows(video_path):
            moments.append({
                "start": m["start"],
                "end":   m["end"],
                "transcript_line": (
                    f"[MOTION: {m['start']:.1f}s\u2013{m['end']:.1f}s, "
                    f"+{m['above_mean']:.1f}x mean motion]"
                ),
            })

    if AnalysisStrategy.VISION_MODEL in strategies:
        for v in build_vision_windows(
            video_path, video_duration, api_key, claude_model
        ):
            moments.append({
                "start": v["start"],
                "end":   v["end"],
                "transcript_line": (
                    f"[VISUAL: {v['start']:.1f}s\u2013{v['end']:.1f}s  {v['description']}]"
                ),
            })

    return sorted(moments, key=lambda m: m["start"])
