"""
media/downloader.py — Remote media fetching via yt-dlp.

SRP: Only responsible for resolving a remote media URL to a local media file.
     Owns no widgets, performs no UI work, and reports progress solely through
     the injected on_log / on_progress callables.
GRASP Pure Fabrication: an adapter around yt-dlp that hides the library's
     option dictionary, progress-hook protocol, and error vocabulary behind a
     single fetch() call the DownloadController can drive.

yt-dlp is optional. When it is absent is_available() returns False and the app
runs exactly as it did before, matching the graceful degradation used for
drag-and-drop support and speaker diarization.
"""

import glob
import os

from src.media.download_errors import (
    FetchCancelled,
    FetchError,
    describe_error,
    is_cancellation,
)
from src.media.url_utils import sanitize_filename
from src.models import (
    DOWNLOAD_AUDIO_CODEC,
    DOWNLOAD_AUDIO_FORMAT,
    DOWNLOAD_PROGRESS_LOG_STEP,
    DOWNLOAD_VIDEO_CONTAINER,
    DOWNLOAD_VIDEO_FORMAT,
    FetchMode,
)

try:
    import yt_dlp
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False


def is_available() -> bool:
    """Return True when yt-dlp is installed and remote fetching is possible."""
    return _YTDLP_AVAILABLE


def fetch(
    url: str,
    dest_dir: str,
    fetch_mode: FetchMode,
    cancel_event,
    on_log=None,
    on_progress=None,
) -> str:
    """
    Download *url* into *dest_dir* and return the resulting local file path.

    Args:
        url:          A single-video URL. Playlist URLs must be rejected by the
                      caller before reaching this function.
        dest_dir:     Existing, writable destination folder. Because transcripts
                      are written alongside their source media, this also
                      determines where every later output for this media lands.
        fetch_mode:   FetchMode.VIDEO for a merged mp4, FetchMode.AUDIO_ONLY for
                      an m4a audio stream.
        cancel_event: threading.Event; setting it aborts the transfer promptly.
        on_log:       Optional ``(message, level)`` activity-log callback.
        on_progress:  Optional ``(percent)`` callback, throttled like the log.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        FetchCancelled: the cancel event was set mid-transfer.
        FetchError:     any failure, already phrased for a human reader.
    """
    if not _YTDLP_AVAILABLE:
        raise FetchError(
            "Downloading from a URL requires yt-dlp.\n\nInstall it with:\n  pip install -U yt-dlp"
        )

    def _log(message: str, level: str = "detail") -> None:
        if on_log:
            on_log(message, level)

    _check_cancel(cancel_event)
    _verify_destination(dest_dir)

    audio_only = fetch_mode is FetchMode.AUDIO_ONLY
    extension = f".{DOWNLOAD_AUDIO_CODEC}" if audio_only else f".{DOWNLOAD_VIDEO_CONTAINER}"

    _log("Reading video details…")
    info = _extract_info(url, cancel_event)
    title = info.get("title") or "video"
    _reject_live(info, title)

    # A unique stem means the download can never clobber an existing file, and
    # makes it safe to delete everything sharing the stem during cleanup.
    stem = _unique_stem(dest_dir, sanitize_filename(title))
    final_path = os.path.join(dest_dir, stem + extension)

    duration = info.get("duration")
    if duration:
        _log(f"  {title}  ·  {_format_duration(duration)}")
    else:
        _log(f"  {title}")
    _log(f"  Mode: {'audio only' if audio_only else 'video + audio'}  →  {extension}")

    reporter = _ProgressReporter(cancel_event, _log, on_progress)
    options = _build_options(dest_dir, stem, audio_only, reporter)

    completed = False
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(url, download=True)
        produced = _resolve_output(result, dest_dir, stem, final_path)
        completed = True
        _log(f"Downloaded → {produced}", "success")
        return produced
    except FetchCancelled:
        raise
    except Exception as exc:
        if is_cancellation(exc):
            raise FetchCancelled("Download cancelled by user.") from exc
        raise FetchError(describe_error(exc)) from exc
    finally:
        if not completed:
            _cleanup_partials(dest_dir, stem)


# ---------------------------------------------------------------------------
# Private — yt-dlp configuration
# ---------------------------------------------------------------------------

def _build_options(dest_dir: str, stem: str, audio_only: bool, reporter) -> dict:
    """Return the yt-dlp option dictionary for one fetch."""
    # "%" is the template's escape character, so a title containing one must be
    # doubled or yt-dlp would interpret it as a field placeholder.
    outtmpl = os.path.join(dest_dir, stem.replace("%", "%%") + ".%(ext)s")

    options = {
        "outtmpl": outtmpl,
        "noplaylist": True,       # a "watch?v=…&list=…" URL is one video, not 200
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "consoletitle": False,
        "logger": _SilentLogger(),
        "progress_hooks": [reporter],
        "retries": 3,
        "ignoreerrors": False,
    }

    if audio_only:
        options["format"] = DOWNLOAD_AUDIO_FORMAT
        options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": DOWNLOAD_AUDIO_CODEC,
        }]
    else:
        options["format"] = DOWNLOAD_VIDEO_FORMAT
        options["merge_output_format"] = DOWNLOAD_VIDEO_CONTAINER
        # SUPPORTED_VIDEO_EXTENSIONS holds only ".mp4"; remuxing guarantees the
        # result is recognised as video even when no merge step was needed.
        options["postprocessors"] = [{
            "key": "FFmpegVideoRemuxer",
            "preferedformat": DOWNLOAD_VIDEO_CONTAINER,
        }]
    return options


class _SilentLogger:
    """Swallow yt-dlp's own console output; this app logs through callbacks."""

    def debug(self, msg):   pass
    def info(self, msg):    pass
    def warning(self, msg): pass
    def error(self, msg):   pass


class _ProgressReporter:
    """
    yt-dlp progress hook: enforces cancellation and throttles progress reporting.

    The hook fires many times per second and every log line is marshalled onto
    the Tk main thread, so unthrottled reporting would stall the UI. Progress is
    therefore announced only once per DOWNLOAD_PROGRESS_LOG_STEP percent.
    """

    def __init__(self, cancel_event, log, on_progress):
        self._cancel_event = cancel_event
        self._log = log
        self._on_progress = on_progress
        self._next_threshold = DOWNLOAD_PROGRESS_LOG_STEP

    def __call__(self, status: dict) -> None:
        # Checked on every invocation, before any throttling, so cancellation
        # takes effect promptly rather than at the next reporting boundary.
        _check_cancel(self._cancel_event)

        state = status.get("status")
        if state == "finished":
            self._next_threshold = DOWNLOAD_PROGRESS_LOG_STEP
            return
        if state != "downloading":
            return

        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        done = status.get("downloaded_bytes")
        if not total or done is None:
            return

        percent = min(100.0, done * 100.0 / total)
        if percent < self._next_threshold:
            return
        while self._next_threshold <= percent:
            self._next_threshold += DOWNLOAD_PROGRESS_LOG_STEP

        self._log(f"  Downloading… {percent:.0f}%  of {_format_size(total)}")
        if self._on_progress:
            self._on_progress(percent)


# ---------------------------------------------------------------------------
# Private — metadata, paths, cleanup
# ---------------------------------------------------------------------------

def _extract_info(url: str, cancel_event) -> dict:
    """Fetch metadata without downloading, so the file name is known up front."""
    probe = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": _SilentLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(probe) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise FetchError(describe_error(exc)) from exc

    _check_cancel(cancel_event)
    if not info:
        raise FetchError("No video was found at that URL.")
    # A single-video URL carrying a playlist id still resolves to one entry.
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise FetchError("No video was found at that URL.")
        info = entries[0]
    return info


def _reject_live(info: dict, title: str) -> None:
    """Refuse an ongoing live stream, which would otherwise download forever."""
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise FetchError(
            f"'{title}' is a live stream. Live streams are not supported — "
            "wait until the stream has ended and been published."
        )


def _verify_destination(dest_dir: str) -> None:
    if not dest_dir:
        raise FetchError("No download folder has been chosen.")
    if not os.path.isdir(dest_dir):
        raise FetchError(f"The download folder no longer exists:\n{dest_dir}")
    if not os.access(dest_dir, os.W_OK):
        raise FetchError(f"The download folder cannot be written to:\n{dest_dir}")


def _unique_stem(dest_dir: str, stem: str) -> str:
    """Return a stem that no existing file in *dest_dir* already uses."""
    candidate = stem
    counter = 2
    while glob.glob(os.path.join(dest_dir, glob.escape(candidate) + ".*")):
        candidate = f"{stem} ({counter})"
        counter += 1
    return candidate


def _resolve_output(result, dest_dir: str, stem: str, expected: str) -> str:
    """Return the path yt-dlp actually produced, preferring its own report."""
    downloads = (result or {}).get("requested_downloads") or []
    for entry in downloads:
        path = entry.get("filepath")
        if path and os.path.exists(path):
            return os.path.abspath(path)
    if os.path.exists(expected):
        return os.path.abspath(expected)
    produced = glob.glob(os.path.join(dest_dir, glob.escape(stem) + ".*"))
    produced = [p for p in produced if not p.endswith((".part", ".ytdl"))]
    if produced:
        return os.path.abspath(max(produced, key=os.path.getmtime))
    raise FetchError("The download finished but no output file was produced.")


def _cleanup_partials(dest_dir: str, stem: str) -> None:
    """
    Delete every file sharing *stem* after a cancelled or failed fetch.

    Safe because _unique_stem() guaranteed no pre-existing file used this stem,
    so nothing here belongs to the user. Fragment and ".part" files are covered
    by the same prefix.
    """
    try:
        leftovers = glob.glob(os.path.join(dest_dir, glob.escape(stem) + "*"))
    except OSError:
        return
    for path in leftovers:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass  # best-effort — never mask the original failure


# ---------------------------------------------------------------------------
# Private — cancellation
# ---------------------------------------------------------------------------

def _check_cancel(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise FetchCancelled("Download cancelled by user.")


# ---------------------------------------------------------------------------
# Private — formatting
# ---------------------------------------------------------------------------

def _format_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def _format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
