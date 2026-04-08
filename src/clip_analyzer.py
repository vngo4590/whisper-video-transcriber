"""
clip_analyzer.py — Claude API integration for viral moment detection.

SRP: Only responsible for sending the transcript to Claude and returning
     a list of ClipResult objects. No ffmpeg, no UI, no file I/O.
"""

import json
import re

import anthropic

from src.models import ClipResult, DEFAULT_CLAUDE_MODEL


_SYSTEM_PROMPT = """\
You are an expert social media content strategist who specialises in identifying \
viral-worthy moments for TikTok and YouTube Shorts.

Your output must be ONLY a single valid JSON object — no markdown, no explanation, \
no code fences. Any deviation will break the pipeline.
"""

_USER_TEMPLATE = """\
Analyse the transcript below and identify the {max_clips} most viral-worthy moments.

Requirements for each clip:
- Duration: 30–90 seconds (ideal: 45–60 s)
- Self-contained: the viewer grasps the point without extra context
- Strong hook within the first 3 seconds
- Ends at a natural break (punchline, conclusion, or revelation)
- Emotionally engaging: surprising, funny, inspiring, educational, or controversial

Return a JSON object with this exact shape:
{{
  "clips": [
    {{
      "start_time": <float, seconds from start of video>,
      "end_time":   <float, seconds from start of video>,
      "title":      "<catchy TikTok title, max 10 words>",
      "hook":       "<what happens / is said in the first 3 seconds>",
      "reason":     "<why this moment will go viral, 1-2 sentences>",
      "category":   "<one of: humor | insight | emotional | shocking | educational>"
    }}
  ]
}}

TRANSCRIPT (with timestamps in seconds):
{transcript}
"""


class ClipAnalyzer:
    """Calls the Claude API to find viral-worthy clip windows in a transcript."""

    def find_viral_moments(
        self,
        transcript: str,
        video_duration: float,
        max_clips: int,
        api_key: str,
        claude_model: str = DEFAULT_CLAUDE_MODEL.model_id,
    ) -> list[ClipResult]:
        """
        Send the transcript to Claude and return validated ClipResult objects.

        Args:
            transcript: Full plain-text transcript with timestamp context.
            video_duration: Total video length in seconds (used for validation).
            max_clips: How many clips to request.
            api_key: Anthropic API key.

        Returns:
            List of ClipResult objects, sorted by start time.

        Raises:
            ValueError: If Claude returns unparseable JSON.
            anthropic.APIError: On API failure.
        """
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=claude_model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _USER_TEMPLATE.format(
                        max_clips=max_clips,
                        transcript=transcript,
                    ),
                }
            ],
        )

        raw = response.content[0].text.strip()
        data = self._parse_json(raw)
        clips = self._validate_clips(data.get("clips", []), video_duration)
        return sorted(clips, key=lambda c: c.start)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str) -> dict:
        """Extract and parse the JSON object from Claude's response."""
        # Strip any accidental markdown fences
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Claude returned invalid JSON.\n"
                f"Response: {raw[:500]}\n"
                f"Error: {exc}"
            ) from exc

    def _validate_clips(self, raw_clips: list, video_duration: float) -> list[ClipResult]:
        """Convert raw dicts to ClipResult, skipping malformed or out-of-range entries."""
        results = []
        for item in raw_clips:
            try:
                start = float(item["start_time"])
                end   = float(item["end_time"])
            except (KeyError, TypeError, ValueError):
                continue

            # Clamp to video bounds
            start = max(0.0, min(start, video_duration))
            end   = max(0.0, min(end,   video_duration))

            if end <= start:
                continue

            results.append(ClipResult(
                start    = start,
                end      = end,
                title    = str(item.get("title",    "Untitled clip")),
                hook     = str(item.get("hook",     "")),
                reason   = str(item.get("reason",   "")),
                category = str(item.get("category", "insight")),
            ))
        return results
