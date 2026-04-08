"""
clip_analyzer.py — Claude API integration for viral moment detection.

SRP: Only responsible for sending the transcript to Claude and returning
     a list of ClipResult objects. No ffmpeg, no UI, no file I/O.
"""

import json
import re

import anthropic

from src.models import ClipMode, ClipResult, Segment, DEFAULT_CLAUDE_MODEL


_SYSTEM_PROMPT = """\
You are an expert social media content strategist who specialises in creating \
viral short-form video for TikTok, YouTube Shorts, and Instagram Reels.

Your output must be ONLY a single valid JSON object — no markdown, no explanation, \
no code fences. Any deviation will break the pipeline.
"""

# ── Mode-specific user prompt templates ──────────────────────────────────────

_SINGLE_SHOT_TEMPLATE = """\
Analyse the transcript below and identify the {max_clips} most viral-worthy \
CONTINUOUS moments.

Requirements per clip:
- One uninterrupted segment, 30–90 seconds (ideal: 45–60 s)
- Self-contained: viewer grasps the point without extra context
- Strong hook within the first 3 seconds
- Ends at a natural break (punchline, conclusion, or revelation)
- Emotionally engaging: surprising, funny, inspiring, educational, or controversial

Return this exact JSON shape:
{{
  "clips": [
    {{
      "start_time": <float — seconds from video start>,
      "end_time":   <float — seconds from video start>,
      "title":      "<catchy title, max 10 words>",
      "hook":       "<what happens / is said in the first 3 seconds>",
      "reason":     "<why this will go viral, 1–2 sentences>",
      "category":   "<humor | insight | emotional | shocking | educational>"
    }}
  ]
}}

TRANSCRIPT (timestamps in seconds):
{transcript}
"""

_MULTI_CUT_TEMPLATE = """\
Analyse the transcript below and design {max_clips} highlight-reel short videos. \
Each video is assembled from 2–5 short clips that share a theme or narrative thread.

Requirements per video:
- Total assembled duration: 45–90 seconds
- Each individual clip segment: 5–25 seconds
- Segments should flow naturally when concatenated
- Together they tell a coherent mini-story or build to a satisfying point

Return this exact JSON shape:
{{
  "clips": [
    {{
      "title":    "<catchy title, max 10 words>",
      "hook":     "<what happens in the very first cut>",
      "reason":   "<why this highlight reel will go viral, 1–2 sentences>",
      "category": "<humor | insight | emotional | shocking | educational>",
      "segments": [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT (timestamps in seconds):
{transcript}
"""

_CREATIVE_TEMPLATE = """\
Analyse the transcript below and design {max_clips} creative short-form videos \
with intentional narrative arcs. Think like a skilled video editor — cuts do NOT \
need to be chronological.

Narrative structure to follow for each video:
  1. Hook (0–5 s): Drop into the most attention-grabbing moment first
  2. Context (5–30 s): Cuts that help the viewer understand the stakes
  3. Payoff (30–end): The conclusion, punchline, or revelation

Requirements per video:
- 3–6 segments, total 30–75 seconds
- Non-linear if it serves the story better
- Each segment 5–20 seconds
- Include a "narrative" field describing the editorial arc in 1–2 sentences

Return this exact JSON shape:
{{
  "clips": [
    {{
      "title":     "<catchy title, max 10 words>",
      "hook":      "<what drops in the opening cut>",
      "reason":    "<why this creative edit will resonate, 1–2 sentences>",
      "category":  "<humor | insight | emotional | shocking | educational>",
      "narrative": "<describe the hook → context → payoff arc>",
      "segments":  [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT (timestamps in seconds):
{transcript}
"""

_TEMPLATES: dict[ClipMode, str] = {
    ClipMode.SINGLE_SHOT: _SINGLE_SHOT_TEMPLATE,
    ClipMode.MULTI_CUT:   _MULTI_CUT_TEMPLATE,
    ClipMode.CREATIVE:    _CREATIVE_TEMPLATE,
}


class ClipAnalyzer:
    """Calls the Claude API to find viral-worthy clip windows in a transcript."""

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
            transcript: Timestamped transcript lines.
            video_duration: Total video length in seconds (for validation).
            max_clips: How many clips to request.
            api_key: Anthropic API key.
            clip_mode: Determines the editing strategy and prompt used.
            claude_model: Claude model ID to use.
            custom_instructions: Optional free-text rules from the user that
                are appended to the prompt before the transcript.

        Returns:
            List of ClipResult objects sorted by first segment start time.
        """
        client = anthropic.Anthropic(api_key=api_key)
        template = _TEMPLATES[clip_mode]

        user_message = template.format(max_clips=max_clips, transcript=transcript)
        if custom_instructions.strip():
            user_message += (
                f"\n\nADDITIONAL INSTRUCTIONS FROM THE USER:\n{custom_instructions.strip()}"
                "\n\nApply these instructions when selecting and shaping the clips. "
                "They take priority over the default requirements above."
            )

        response = client.messages.create(
            model=claude_model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text.strip()
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
            ))
        return results

    def _extract_segments(
        self, item: dict, video_duration: float, clip_mode: ClipMode
    ) -> list[Segment]:
        """Parse segment timestamps from a raw clip dict."""
        # Single-shot uses top-level start_time / end_time
        if clip_mode is ClipMode.SINGLE_SHOT:
            try:
                start = float(item["start_time"])
                end   = float(item["end_time"])
                start, end = self._clamp(start, end, video_duration)
                return [Segment(start, end)] if end > start else []
            except (KeyError, TypeError, ValueError):
                return []

        # Multi-cut and Creative use a "segments" array
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
