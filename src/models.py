"""
models.py — Shared configuration constants.

GRASP Information Expert: single authoritative source for app-wide config values.
Changes to window size, model list, or thumbnail dimensions happen only here.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


class ExportFormat(Enum):
    SRT = "srt"
    PLAIN_TEXT = "plain_text"


@dataclass
class ClipResult:
    start: float
    end: float
    title: str
    hook: str
    reason: str
    category: str
    output_path: str = field(default="")

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def timestamp_label(self) -> str:
        def fmt(s: float) -> str:
            m, sec = divmod(int(s), 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{fmt(self.start)} → {fmt(self.end)}"


DEFAULT_EXPORT_FORMAT = ExportFormat.SRT
DEFAULT_MAX_WORDS_PER_LINE = 5

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
DEFAULT_MODEL = "base"

THUMBNAIL_SIZE = (180, 180)

# ---------------------------------------------------------------------------
# Claude model catalogue — ordered cheapest → most expensive
# ---------------------------------------------------------------------------

class ClaudeModel(NamedTuple):
    model_id: str     # API identifier
    label: str        # short name shown in the UI
    cost_tier: str    # dollar-sign cost indicator shown in the dropdown


CLAUDE_MODELS: list[ClaudeModel] = [
    ClaudeModel("claude-haiku-4-5-20251001", "Haiku 4.5",  "$    fastest & cheapest"),
    ClaudeModel("claude-sonnet-4-6",          "Sonnet 4.6", "$$   balanced  ★ recommended"),
    ClaudeModel("claude-opus-4-6",            "Opus 4.6",   "$$$  most capable"),
]
DEFAULT_CLAUDE_MODEL = CLAUDE_MODELS[1]   # Sonnet

DEFAULT_MAX_CLIPS = 5
CLIP_ASPECT_W = 1080
CLIP_ASPECT_H = 1920
CLIP_BITRATE = "8M"
CLIP_FPS = 30

WINDOW_TITLE = "Whisper Video Transcriber"
WINDOW_SIZE = "980x640"

SUPPORTED_VIDEO_EXTENSIONS = {".mp4"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

MEDIA_FILE_TYPES = [
    ("Media files", "*.mp4 *.mp3 *.wav *.m4a *.flac *.ogg"),
    ("Video files", "*.mp4"),
    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
    ("All files", "*.*"),
]
