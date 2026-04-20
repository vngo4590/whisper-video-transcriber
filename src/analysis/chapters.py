"""
analysis/chapters.py — Claude API chapter / topic segmentation.

SRP: Sole responsibility is sending a transcript to Claude and returning
     a list of chapter dicts with timestamps, titles, summaries, and key
     points.  No UI, no ffmpeg, no file I/O.

Prompts are loaded from prompts/chapters/ — edit those files to tune
Claude's behaviour without touching this code.
"""

import json
import re
from pathlib import Path

import anthropic

from src.models import DEFAULT_CLAUDE_MODEL


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def _p(name: str) -> str:
    """Read a single prompt file from prompts/chapters/."""
    return (Path(__file__).parent.parent.parent / "prompts" / "chapters" / name).read_text(encoding="utf-8").strip()


_SYSTEM_PROMPT = _p("system.md")
_USER_TEMPLATE = _p("user_template.md")


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

    client = anthropic.Anthropic(
        api_key=api_key,
        max_retries=3,
        timeout=anthropic.Timeout(600.0, connect=30.0),
    )
    user_message = _USER_TEMPLATE.format(
        max_chapters=max_chapters,
        transcript=transcript,
    )

    _log(f"→ Claude API  model={claude_model}  max_tokens=2048", "api")
    _log(f"  input={len(user_message):,} chars  max_chapters={max_chapters}", "detail")

    try:
        response = client.messages.create(
            model=claude_model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.AuthenticationError as exc:
        raise ValueError("Invalid Anthropic API key — check the key in the settings.") from exc
    except anthropic.RateLimitError as exc:
        raise ValueError("Anthropic rate limit reached — wait a moment and try again.") from exc
    except anthropic.APIConnectionError as exc:
        raise ValueError(
            "Could not reach the Anthropic API. Check your internet connection and try again.\n"
            f"Detail: {exc}"
        ) from exc
    except anthropic.APITimeoutError as exc:
        raise ValueError(
            "The Anthropic API request timed out. Try again or use a faster model.\n"
            f"Detail: {exc}"
        ) from exc
    except anthropic.APIStatusError as exc:
        raise ValueError(
            f"Anthropic API error {exc.status_code}: {exc.message}"
        ) from exc

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
