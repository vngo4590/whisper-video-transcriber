"""
models.py — Shared configuration constants.

GRASP Information Expert: single authoritative source for app-wide config values.
Changes to window size, model list, or thumbnail dimensions happen only here.
"""

from enum import Enum


class ExportFormat(Enum):
    SRT = "srt"
    PLAIN_TEXT = "plain_text"


DEFAULT_EXPORT_FORMAT = ExportFormat.SRT

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
DEFAULT_MODEL = "base"

THUMBNAIL_SIZE = (180, 180)

WINDOW_TITLE = "Whisper Video Transcriber"
WINDOW_SIZE = "900x550"

SUPPORTED_VIDEO_EXTENSIONS = {".mp4"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

MEDIA_FILE_TYPES = [
    ("Media files", "*.mp4 *.mp3 *.wav *.m4a *.flac *.ogg"),
    ("Video files", "*.mp4"),
    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
    ("All files", "*.*"),
]
