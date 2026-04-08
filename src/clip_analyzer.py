"""
clip_analyzer.py — Claude API integration for viral moment detection.

SRP: Only responsible for sending the transcript to Claude and returning
     a list of ClipResult objects. No ffmpeg, no UI, no file I/O.
"""

import json
import re

import anthropic

from src.models import ClipMode, ClipResult, Segment, DEFAULT_CLAUDE_MODEL


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert social-media video editor and viral content strategist \
for Instagram, TikTok, and YouTube Shorts. You think like a top influencer \
editor: every second must earn its place, dead air is cut on sight, filler \
words are removed, and repeated ideas are distilled to their sharpest form.

ABSOLUTE RULES — apply to every clip in every mode:
1. SILENCE  — Never let a [SILENCE] gap fall inside your segment windows.
   A segment must START at the first word after silence and END at the last
   word before silence. Never straddle a [SILENCE] marker.
2. REPETITION — If the speaker says the same thing twice, keep only the
   clearest, most energetic delivery. Drop stumbles and self-corrections.
3. FILLER OPENINGS — Never open a clip on "um", "uh", "so", "like",
   "you know", "basically", "anyway", "right", or similar filler.
   Start on a strong, meaningful word.
4. ENERGY — Prefer segments from high-confidence, fast-paced speech.
   Avoid monotone or trailing-off sections.
5. BOUNDARY ALIGNMENT — Your start times must equal a [start] timestamp
   and your end times must equal an [end] timestamp from the transcript.
   Never place a boundary in the middle of a speech segment line — doing
   so cuts a sentence in half and breaks the narrative.
6. COMPLETE THOUGHTS — Every segment must begin and end on a complete
   sentence or self-contained idea. If a speaker is mid-explanation,
   include the full explanation rather than cutting it off. A viewer who
   feels a point was interrupted will stop watching.

TRANSCRIPT FORMAT:
- Each line: [HH:MM:SS.f -> HH:MM:SS.f]  spoken text
- [SILENCE: X.Xs] = dead air between speech lines
- Use the exact start/end float values from the timestamps as your JSON values.

Your output must be ONLY a single valid JSON object — no markdown fences, \
no explanation, no extra keys. Any deviation will break the pipeline.
"""


# ---------------------------------------------------------------------------
# Universal editing rules appended to every template
# ---------------------------------------------------------------------------

_EDITING_RULES = """
EDITING RULES (mandatory for all clips):
- BOUNDARIES: Start times must match a [start] value and end times must match
  an [end] value from the transcript. Never cut inside a speech segment line.
- COMPLETE THOUGHTS: Each segment must end on a complete sentence or idea.
  If a speaker is mid-point, include the rest of that point before cutting.
- SILENCE: Never straddle a [SILENCE] marker — end before it, start after it.
- REPETITION: Keep only the clearest delivery when an idea is repeated.
- FILLERS: Never open on "um", "uh", "so", "like", "you know", "basically".
- ENERGY: Prefer high-confidence, fast-paced delivery windows.
- REPETITIVE PHRASES: If a point is made multiple times or the speaker repeats themselves, pick the most energetic delivery and cut the rest.
- FLOW: The segments you choose should flow together naturally when stitched, even if they are non-chronological. The combined narrative should be clear and compelling on its own.
"""


# ---------------------------------------------------------------------------
# Per-mode prompt templates
# ---------------------------------------------------------------------------

_SINGLE_SHOT_TEMPLATE = """\
Analyse the transcript and identify the {max_clips} most viral-worthy \
CONTINUOUS moments. Each clip must be one uninterrupted speech window — \
no silence gaps inside.

Requirements per clip:
- Duration: 30–90 seconds (ideal 45–60 s)
- Self-contained: viewer grasps the point without extra context
- Strong hook in the first 3 seconds
- Ends at a natural break (punchline, conclusion, or revelation)
- Emotionally engaging: surprising, funny, inspiring, educational, or controversial
{editing_rules}
Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "start_time": <float — seconds from video start, matching a speech segment start>,
      "end_time":   <float — seconds from video start, matching a speech segment end>,
      "title":      "<catchy title, max 10 words>",
      "hook":       "<what is said in the first 3 seconds>",
      "reason":     "<why this will go viral, 1–2 sentences>",
      "category":   "<humor | insight | emotional | shocking | educational>"
    }}
  ]
}}

TRANSCRIPT:
{transcript}
"""

_MULTI_CUT_TEMPLATE = """\
Analyse the transcript and design {max_clips} highlight-reel videos. \
Each video is assembled from 2–5 short speech windows that share a theme. \
No window may contain or straddle a [SILENCE] marker.

Requirements per video:
- Total assembled duration: 45–90 seconds
- Each individual segment: 5–20 seconds of speech (trim at speech boundaries)
- Segments flow naturally when concatenated
- Together they tell a coherent mini-story or build to a satisfying point
{editing_rules}
Return ONLY this exact JSON shape:
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

TRANSCRIPT:
{transcript}
"""

_CREATIVE_TEMPLATE = """\
Analyse the transcript and design {max_clips} creative short-form videos \
with intentional narrative arcs. Think like a skilled editor — cuts do NOT \
need to be chronological, but every segment must begin and end on speech \
boundaries (never inside a [SILENCE] gap).

Narrative structure for each video:
  1. Hook (0–5 s): Drop into the most attention-grabbing moment first
  2. Context (5–30 s): Cuts that build stakes or context
  3. Payoff (30–end): The conclusion, punchline, or revelation
{editing_rules}
Requirements per video:
- 3–6 segments, total 30–75 seconds
- Each segment 5–20 seconds of clean speech
- Non-linear if it serves the story better
- Include a "narrative" field describing the hook → context → payoff arc

Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "title":     "<catchy title, max 10 words>",
      "hook":      "<what drops in the opening cut>",
      "reason":    "<why this creative edit will resonate, 1–2 sentences>",
      "category":  "<humor | insight | emotional | shocking | educational>",
      "narrative": "<hook → context → payoff arc in 1–2 sentences>",
      "segments":  [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT:
{transcript}
"""

_REELS_TEMPLATE = """\
You are cutting an Instagram Reel. Edit like a top influencer creator: \
keep only the sharpest phrases, jump-cut across every pause, kill every \
filler word, and make the viewer feel immediate energy from frame one.

Design {max_clips} Reels assembled from micro-cuts stitched together.

REELS-SPECIFIC RULES (on top of the absolute rules):
- Each cut must be one COMPLETE punchy phrase — 0.5–3 seconds per segment
- Minimum segment duration: 0.5 seconds — no ghost cuts or sentence fragments
- Maximum segment duration: 3 seconds — keep energy high, never linger
- Segment boundaries must align to the speech segment timestamps in the transcript
- Never split a sentence across two segments — finish the thought, then cut
- Skip every [SILENCE] marker — cut boundary ends before it, starts after it
- Never open a Reel on filler; the first word must be a hook word
- Total assembled duration per Reel: 15–60 seconds (15–30 s is ideal)
- End on a high note: strong claim, punchline, or open loop that demands a save
- Do not include repetitive phrases — if a point is made multiple times, pick the most energetic delivery and cut the rest
- The segments you choose should flow together naturally when stitched, even if they are non-chronical. The combined narrative should be clear and compelling on its own.

INFLUENCER STRATEGIES — apply at least one per Reel and name it in "strategy":
- "pattern_of_3": find where speaker lists or repeats a concept 3 times — great rhythm
- "contrast_moment": where opinion flips or an unexpected claim appears
- "open_loop": cut just before the payoff is revealed — drives saves and follows
- "relatability": moments the audience has personally felt or experienced
- "authority_signal": surprising expertise, data point, or counterintuitive fact
- "transformation_tease": before/after or problem/solution structure

Return ONLY this exact JSON shape:
{{
  "clips": [
    {{
      "title":    "<punchy Reel title, max 8 words, no period>",
      "hook":     "<exact first words spoken in the Reel>",
      "strategy": "<one of the six strategy keys above>",
      "reason":   "<why this will perform on Instagram, 1 sentence>",
      "cta_hint": "<suggested caption line or on-screen text, e.g. 'Save this! 👇'>",
      "category": "<humor | insight | emotional | shocking | educational>",
      "segments": [
        {{"start": <float>, "end": <float>}},
        {{"start": <float>, "end": <float>}}
      ]
    }}
  ]
}}

TRANSCRIPT:
{transcript}
"""

_TEMPLATES: dict[ClipMode, str] = {
    ClipMode.SINGLE_SHOT: _SINGLE_SHOT_TEMPLATE,
    ClipMode.MULTI_CUT:   _MULTI_CUT_TEMPLATE,
    ClipMode.CREATIVE:    _CREATIVE_TEMPLATE,
    ClipMode.REELS:       _REELS_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

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

        raw  = response.content[0].text.strip()
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
