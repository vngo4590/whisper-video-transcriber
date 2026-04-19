"""
analysis/chapters.py — Claude API chapter / topic segmentation.

SRP: Sole responsibility is sending a transcript to Claude and returning
     a list of chapter dicts with timestamps, titles, summaries, and key
     points.  No UI, no ffmpeg, no file I/O.

Prompts are loaded from prompts/chapter_prompts.md.
"""

import json
import re
from pathlib import Path

import anthropic

from src.models import DEFAULT_CLAUDE_MODEL


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def _load_prompts() -> dict[str, str]:
    md_path = Path(__file__).parent.parent.parent / "prompts" / "chapter_prompts.md"
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

def generate_chapters(
    transcript: str,
    api_key: str,
    claude_model: str = DEFAULT_CLAUDE_MODEL.model_id,
    max_chapters: int = 10,
    on_log=None,
) -> list[dict]:
    """
    Send *transcript* to Claude and return a list of chapter dicts.

    Each dict has: chapter (int), title (str), start_time (float),
    end_time (float), summary (str), key_points (list[str]).

    Args:
        transcript:   The transcript text from the Transcript panel (SRT or plain).
        api_key:      Anthropic API key.
        claude_model: Claude model ID.
        max_chapters: Maximum number of chapters to request.
        on_log:       Optional ``(message, level)`` callback.

    Returns:
        List of chapter dicts sorted by start_time.
    """
    def _log(msg: str, level: str = "info") -> None:
        if on_log:
            on_log(msg, level)

    client = anthropic.Anthropic(api_key=api_key)
    user_message = _USER_TEMPLATE.format(
        max_chapters=max_chapters,
        transcript=transcript,
    )

    _log(f"→ Claude API  model={claude_model}  max_tokens=2048", "api")
    _log(f"  input={len(user_message):,} chars  max_chapters={max_chapters}", "detail")

    response = client.messages.create(
        model=claude_model,
        max_tokens=2048,
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
        raise ValueError("Claude returned no content for chapter generation.")

    _log(f"← Claude responded  ({len(raw):,} chars)", "detail")

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude returned invalid JSON for chapters.\n"
            f"Response: {raw[:400]}\nError: {exc}"
        ) from exc

    chapters = data.get("chapters", [])
    return sorted(chapters, key=lambda c: float(c.get("start_time", 0)))
