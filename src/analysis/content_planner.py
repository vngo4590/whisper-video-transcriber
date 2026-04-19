"""
analysis/content_planner.py — Claude API content plan generator + text formatter.

SRP: Responsible for sending a timestamped transcript to Claude and returning
     a formatted, human-readable content plan string.  No ffmpeg, no UI, no
     file I/O.

Prompts are loaded from prompts/content_plan_prompts.md — edit that file to tune
Claude's behaviour without touching this code.
"""

import json
import re
import textwrap
from pathlib import Path

import anthropic

from src.models import DEFAULT_CLAUDE_MODEL


# ---------------------------------------------------------------------------
# Focus options (single source of truth; imported by the UI tab)
# ---------------------------------------------------------------------------

FOCUS_OPTIONS: list[str] = [
    "All highlights",
    "Key insights & takeaways",
    "Step-by-step instructions",
    "Funny & entertaining moments",
    "Emotional & story moments",
    "Debate & controversial opinions",
    "Demonstrations & reveals",
    "Gaming & live event highlights",
    "Custom",
]


# ---------------------------------------------------------------------------
# Prompt loader (same pattern as clips/analyzer.py)
# ---------------------------------------------------------------------------

def _load_prompts() -> dict[str, str]:
    md_path = Path(__file__).parent.parent.parent / "prompts" / "content_plan_prompts.md"
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
_SYSTEM_PROMPT = _PROMPTS["SYSTEM_PROMPT"]
_USER_TEMPLATE = _PROMPTS["USER_TEMPLATE"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_plan(
    transcript: str,
    api_key: str,
    claude_model: str = DEFAULT_CLAUDE_MODEL.model_id,
    focus: str = "All highlights",
    max_highlights: int = 5,
    context: str = "",
    on_log=None,
) -> str:
    """
    Send *transcript* to Claude and return a formatted content plan string.

    Args:
        transcript: Timestamped transcript produced by ContentPlanController.
        api_key: Anthropic API key.
        claude_model: Claude model ID.
        focus: Selected focus label (one of FOCUS_OPTIONS or custom text).
        max_highlights: Maximum number of highlights to request.
        context: Optional free-text context / additional instructions.

    Returns:
        Human-readable, copy-ready content plan as a plain-text string.
    """
    def _log(msg: str, level: str = "info") -> None:
        if on_log:
            on_log(msg, level)

    client = anthropic.Anthropic(api_key=api_key)

    context_block = ""
    if context.strip():
        context_block = f"ADDITIONAL CONTEXT FROM CREATOR:\n{context.strip()}\n\n"

    user_message = _USER_TEMPLATE.format(
        focus=focus,
        max_highlights=max_highlights,
        context_block=context_block,
        transcript=transcript,
    )

    _log(f"→ Claude API  model={claude_model}  max_tokens=4096", "api")
    _log(f"  focus={focus!r}  max_highlights={max_highlights}  input={len(user_message):,} chars", "detail")

    response = client.messages.create(
        model=claude_model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = ""
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            raw = text.strip()
            break

    if not raw:
        raise ValueError("Claude returned no content.")

    _log(f"← Claude responded  ({len(raw):,} chars)", "detail")

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude returned invalid JSON — try again or use a more capable model.\n"
            f"Response: {raw[:400]}\nError: {exc}"
        ) from exc

    return format_plan(data)


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

_W = 66  # output line width


def _ts(secs: float) -> str:
    """Format seconds as HH:MM:SS."""
    secs = max(0.0, float(secs))
    total = int(secs)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _wrap(text: str, indent: int = 4) -> list[str]:
    """Wrap *text* and prefix every line with *indent* spaces."""
    prefix = " " * indent
    return [prefix + l for l in textwrap.wrap(text, width=_W - indent)]


def format_plan(data: dict) -> str:
    """
    Convert a parsed Claude JSON response into a nicely formatted plain-text
    content plan suitable for display in a monospace Text widget and for saving.
    """
    lines: list[str] = []

    # ── Header ─────────────────────────────────────────────────────────────
    lines.append("═" * _W)
    lines.append("  CONTENT PLAN  —  AI-Generated Edit Guide")
    lines.append("═" * _W)
    lines.append("")

    # ── Overview ───────────────────────────────────────────────────────────
    lines.append("OVERVIEW")
    lines.append("─" * 40)
    summary = data.get("video_summary", "")
    if summary:
        lines.extend(_wrap(summary, indent=0))
    highlights = data.get("highlights", [])
    lines.append(f"Highlights found:  {len(highlights)}")
    lines.append("")

    # ── Highlights ─────────────────────────────────────────────────────────
    for h in highlights:
        rank       = h.get("rank", "?")
        title      = str(h.get("title", "Untitled"))
        score      = h.get("viral_score", "?")
        start      = float(h.get("start_time", 0.0))
        end        = float(h.get("end_time", 0.0))
        duration   = max(0.0, end - start)
        clip_type  = str(h.get("type", "")).title()
        platforms  = " · ".join(h.get("platform_fit", []))
        hook       = str(h.get("hook", ""))
        why        = str(h.get("why_it_works", ""))
        notes      = str(h.get("edit_notes", ""))
        cta        = str(h.get("cta_suggestion", ""))

        score_str  = f"[SCORE: {score}/10]"
        rank_str   = f"#{rank}  "
        max_title  = _W - len(rank_str) - len(score_str) - 2
        title_col  = title[:max_title].ljust(max_title)

        lines.append("━" * _W)
        lines.append(f"{rank_str}{title_col}  {score_str}")
        lines.append("─" * _W)
        lines.append(f"  Time      {_ts(start)} → {_ts(end)}  ({duration:.0f}s)")
        lines.append(f"  Type      {clip_type}")
        lines.append(f"  Platforms {platforms}")
        lines.append("")

        if hook:
            lines.append("  HOOK")
            lines.extend(_wrap(f'"{hook}"', indent=4))
            lines.append("")

        if why:
            lines.append("  WHY IT WORKS")
            lines.extend(_wrap(why, indent=4))
            lines.append("")

        if notes:
            lines.append("  EDIT NOTES")
            for note in notes.splitlines():
                note = note.strip().lstrip("•*-– ")
                if note:
                    # Hard-wrap long notes
                    wrapped = textwrap.wrap(note, width=_W - 8)
                    if wrapped:
                        lines.append(f"    • {wrapped[0]}")
                        for cont in wrapped[1:]:
                            lines.append(f"      {cont}")
            lines.append("")

        if cta:
            lines.append("  CTA")
            lines.extend(_wrap(cta, indent=4))
            lines.append("")

    # ── Posting Calendar ───────────────────────────────────────────────────
    calendar = data.get("posting_calendar", [])
    if calendar:
        lines.append("━" * _W)
        lines.append("POSTING CALENDAR")
        lines.append("─" * 40)
        for entry in calendar:
            day      = entry.get("day", "?")
            hl_rank  = entry.get("highlight_rank", "?")
            platform = entry.get("platform", "")
            rationale = entry.get("rationale", "")
            lines.append(f"  Day {day:<3}  Clip #{hl_rank}  ({platform})")
            if rationale:
                for l in textwrap.wrap(rationale, width=_W - 11):
                    lines.append(f"           {l}")
        lines.append("")

    # ── Overall Notes ──────────────────────────────────────────────────────
    overall = data.get("overall_notes", "")
    if overall:
        lines.append("━" * _W)
        lines.append("OVERALL NOTES")
        lines.append("─" * 40)
        lines.extend(_wrap(overall, indent=0))
        lines.append("")

    lines.append("═" * _W)
    return "\n".join(lines)
