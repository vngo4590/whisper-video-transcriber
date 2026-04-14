"""
config/settings.py — Persistent local settings store.

Saves user preferences (API key, model selections) to a JSON file in the
OS-appropriate config directory so they survive between sessions.

Storage locations:
  Windows  — %APPDATA%\\WhisperTranscriber\\settings.json
  macOS    — ~/Library/Application Support/WhisperTranscriber/settings.json
  Linux    — ~/.config/WhisperTranscriber/settings.json
"""

import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal path resolution
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "WhisperTranscriber"


_CONFIG_FILE = _config_dir() / "settings.json"


def _read() -> dict:
    """Read the settings file from disk. Returns {} on any failure."""
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    """Write *data* to the settings file, creating directories as needed."""
    try:
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # best-effort — never crash the app over a settings write


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get(key: str, default=None):
    """Return the stored value for *key*, or *default* if absent."""
    return _read().get(key, default)


def save(**kwargs) -> None:
    """
    Persist one or more key=value pairs, merging with existing settings.

    Usage::

        settings.save(api_key="sk-ant-...", whisper_model="base")
    """
    current = _read()
    current.update(kwargs)
    _write(current)


def clear() -> None:
    """Delete all cached settings (wipes the file)."""
    try:
        _CONFIG_FILE.unlink(missing_ok=True)
    except OSError:
        pass
