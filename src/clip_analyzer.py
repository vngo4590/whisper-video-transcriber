"""
clip_analyzer.py — Claude API integration for viral moment detection.

SRP: Only responsible for sending the transcript to Claude and returning
     a list of ClipResult objects. No ffmpeg, no UI, no file I/O.

Prompts are loaded from prompts/clip_prompts.md — edit that file to tune
Claude's behaviour without touching this code.
"""

import json
import re
from pathlib import Path
from typing import Any

import anthropic

from src.models import ClipMode, ClipResult, Segment, DEFAULT_CLAUDE_MODEL


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def _load_prompts() -> dict[str, str]:
    """Parse prompts/clip_prompts.md and return a dict keyed by ## heading."""
    md_path = Path(__file__).parent.parent / "prompts" / "clip_prompts.md"
    text = md_path.read_text(encoding="utf-8")

    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


_PROMPTS = _load_prompts()

_SYSTEM_PROMPT   = _PROMPTS["SYSTEM_PROMPT"]
_EDITING_RULES   = "\n" + _PROMPTS["EDITING_RULES"] + "\n"

_TEMPLATES: dict[ClipMode, str] = {
    ClipMode.SINGLE_SHOT: _PROMPTS["SINGLE_SHOT_TEMPLATE"],
    ClipMode.MULTI_CUT:   _PROMPTS["MULTI_CUT_TEMPLATE"],
    ClipMode.CREATIVE:    _PROMPTS["CREATIVE_TEMPLATE"],
    ClipMode.REELS:       _PROMPTS["REELS_TEMPLATE"],
}


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class ClipAnalyzer:
    """Calls the Claude API to find viral-worthy clip windows in a transcript."""

    @staticmethod
    def _extract_text_response(content_blocks: list[Any]) -> str:
        text_parts: list[str] = []
        for block in content_blocks:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
        return "\n".join(text_parts)

    def find_viral_moments(
        self,
        transcript: str,
        video_duration: float,
        max_clips: int,
        api_key: str,
        clip_mode: ClipMode = ClipMode.SINGLE_SHOT,
        claude_model: str = DEFAULT_CLAUDE_MODEL.model_id,
        custom_instructions: str = "",
    ) -> list[ClipResult]:
        """
        Send the transcript to Claude and return validated ClipResult objects.

        Args:
            transcript: Timestamped transcript lines (with silence markers).
            video_duration: Total video length in seconds (for validation).
            max_clips: How many clips to request.
            api_key: Anthropic API key.
            clip_mode: Determines the editing strategy and prompt used.
            claude_model: Claude model ID to use.
            custom_instructions: Optional free-text rules from the user.

        Returns:
            List of ClipResult objects sorted by first segment start time.
        """
        client = anthropic.Anthropic(api_key=api_key)
        template = _TEMPLATES[clip_mode]

        user_message = template.format(
            max_clips=max_clips,
            transcript=transcript,
            editing_rules=_EDITING_RULES,
        )

        if custom_instructions.strip():
            user_message += (
                f"\n\nADDITIONAL INSTRUCTIONS FROM THE USER:\n{custom_instructions.strip()}"
                "\n\nApply these on top of all rules above. They take priority where they conflict."
            )

        response = client.messages.create(
            model=claude_model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = self._extract_text_response(response.content)
        if not raw:
            raise ValueError("Claude returned no text content.")
        data = self._parse_json(raw)
        clips = self._validate_clips(data.get("clips", []), video_duration, clip_mode)
        return sorted(clips, key=lambda c: c.start)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Claude returned invalid JSON.\nResponse: {raw[:500]}\nError: {exc}"
            ) from exc

    def _validate_clips(
        self, raw_clips: list, video_duration: float, clip_mode: ClipMode
    ) -> list[ClipResult]:
        results = []
        for item in raw_clips:
            segments = self._extract_segments(item, video_duration, clip_mode)
            if not segments:
                continue
            results.append(ClipResult(
                segments  = segments,
                title     = str(item.get("title",     "Untitled clip")),
                hook      = str(item.get("hook",      "")),
                reason    = str(item.get("reason",    "")),
                category  = str(item.get("category",  "insight")),
                narrative = str(item.get("narrative", "")),
                strategy  = str(item.get("strategy",  "")),
                cta_hint  = str(item.get("cta_hint",  "")),
            ))
        return results

    def _extract_segments(
        self, item: dict, video_duration: float, clip_mode: ClipMode
    ) -> list[Segment]:
        """Parse segment timestamps from a raw clip dict."""
        if clip_mode is ClipMode.SINGLE_SHOT:
            try:
                start = float(item["start_time"])
                end   = float(item["end_time"])
                start, end = self._clamp(start, end, video_duration)
                return [Segment(start, end)] if end > start else []
            except (KeyError, TypeError, ValueError):
                return []

        # MULTI_CUT, CREATIVE, and REELS all use a "segments" array
        raw_segs = item.get("segments", [])
        if not raw_segs:
            return []

        segments = []
        for s in raw_segs:
            try:
                start = float(s["start"])
                end   = float(s["end"])
                start, end = self._clamp(start, end, video_duration)
                if end > start:
                    segments.append(Segment(start, end))
            except (KeyError, TypeError, ValueError):
                continue
        return segments

    @staticmethod
    def _clamp(start: float, end: float, duration: float) -> tuple[float, float]:
        start = max(0.0, min(start, duration))
        end   = max(0.0, min(end,   duration))
        return start, end
