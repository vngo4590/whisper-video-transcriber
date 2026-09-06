"""
media/url_utils.py — Remote URL validation and filesystem-safe naming.

SRP: Only responsible for inspecting a user-supplied media URL and deriving a
     name that is legal on the host filesystem. Performs no network I/O and
     knows nothing about yt-dlp, downloading, or the UI.
GRASP Pure Fabrication: a stateless helper module extracted so the downloader
     and the sidebar can both validate input without duplicating the rules.
"""

import re
from urllib.parse import parse_qs, urlparse

# Paths that identify a playlist outright, regardless of query parameters.
_PLAYLIST_PATHS = {"/playlist"}

# Path prefixes that carry the video id in the path rather than in a "v" param.
_VIDEO_PATH_PREFIXES = ("/shorts/", "/live/", "/embed/", "/v/")

# "/embed/videoseries?list=…" is a playlist embed, not a video called
# "videoseries" — the slug is a sentinel, not an id.
_NOT_A_VIDEO_SLUG = "videoseries"

# Characters Windows forbids in a file name, plus the control range.
_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WHITESPACE_RUN = re.compile(r"\s+")

# Legacy DOS device names. Windows rejects these as file stems even with an
# extension appended.
_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


# ---------------------------------------------------------------------------
# URL inspection
# ---------------------------------------------------------------------------

def is_valid_url(text: str) -> bool:
    """
    Return True when *text* is a well-formed http(s) URL.

    Deliberately permissive: the extractor is the real authority on which sites
    are supported, so a strict per-site pattern would reject valid forms while
    adding no safety.
    """
    candidate = (text or "").strip()
    if not candidate:
        return False
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return False
    return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)


def is_playlist_url(text: str) -> bool:
    """
    Return True when *text* identifies a playlist rather than a single video.

    A ``list=`` parameter alone is NOT enough: a normal ``watch?v=…&list=…``
    URL is a single video that happens to sit inside a playlist, which is what
    the user gets when they copy a link from a playlist page.
    """
    if not is_valid_url(text):
        return False
    parsed = urlparse(text.strip())
    path = _normalised_path(parsed)
    query = parse_qs(parsed.query)

    if path.lower() in _PLAYLIST_PATHS:
        return True
    if "list" not in query:
        return False
    return not _has_video_id(parsed, path, query)


def is_video_in_playlist(text: str) -> bool:
    """
    Return True when *text* is a single video that also carries a playlist id.

    Such a URL must be fetched as one video (yt-dlp ``noplaylist=True``) rather
    than rejected or expanded into every entry of the playlist.
    """
    if not is_valid_url(text):
        return False
    parsed = urlparse(text.strip())
    return "list" in parse_qs(parsed.query) and not is_playlist_url(text)


def _normalised_path(parsed) -> str:
    path = parsed.path.rstrip("/")
    return path or "/"


def _has_video_id(parsed, path: str, query: dict) -> bool:
    """Return True when the URL names a specific video."""
    if query.get("v", [""])[0].strip():
        return True

    host = (parsed.hostname or "").lower()
    if host == "youtu.be" or host.endswith(".youtu.be"):
        return bool(path.strip("/"))

    lowered = path.lower()
    for prefix in _VIDEO_PATH_PREFIXES:
        if lowered.startswith(prefix):
            slug = path[len(prefix):].strip("/")
            return bool(slug) and slug.lower() != _NOT_A_VIDEO_SLUG
    return False


# ---------------------------------------------------------------------------
# File naming
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, fallback: str = "video", max_length: int = 120) -> str:
    """
    Return *name* reduced to a file stem that is legal on the host filesystem.

    Removes characters Windows forbids, collapses whitespace runs, strips the
    trailing dots and spaces Windows silently discards, avoids the reserved DOS
    device names, and truncates to *max_length* characters.

    Args:
        name:       Raw title, typically taken from the video's metadata.
        fallback:   Stem returned when *name* sanitises down to nothing.
        max_length: Maximum stem length, leaving room for an extension.

    Returns:
        A non-empty, filesystem-safe stem without a directory or extension.
    """
    cleaned = _ILLEGAL_FILENAME_CHARS.sub(" ", name or "")
    cleaned = _WHITESPACE_RUN.sub(" ", cleaned).strip()
    cleaned = cleaned[:max_length].strip()
    # Windows drops trailing dots and spaces, which would silently rename the file.
    cleaned = cleaned.rstrip(". ")

    if not cleaned or cleaned.strip(".") == "":
        return fallback
    if cleaned.lower() in _RESERVED_STEMS:
        return f"{cleaned}_"
    return cleaned
