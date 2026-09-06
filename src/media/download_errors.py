"""
media/download_errors.py — Fetch failure vocabulary and human phrasing.

SRP: Only responsible for the exception types a fetch can raise and for turning
     a yt-dlp failure into a sentence a user can act on. Performs no I/O and
     knows nothing about how a download is carried out.
GRASP Pure Fabrication: extracted from the downloader so the mapping table can
     grow as YouTube's error wording changes without enlarging the module that
     actually moves bytes.
"""


class FetchCancelled(Exception):
    """
    Raised when a fetch is aborted because the shared cancel event was set.

    The controller layer translates this into OperationCancelledError; keeping a
    separate type here preserves the rule that domain packages never import from
    src.controllers.
    """


class FetchError(Exception):
    """Raised with a human-readable explanation when a fetch cannot complete."""


def is_cancellation(exc: BaseException) -> bool:
    """True when *exc* is a FetchCancelled wrapped by yt-dlp's error handling."""
    seen = 0
    current = exc
    while current is not None and seen < 10:
        if isinstance(current, FetchCancelled):
            return True
        current = current.__cause__ or current.__context__
        seen += 1
    return "cancelled by user" in str(exc).lower()


# Ordered most specific first: the first matching fragment wins. Order matters —
# YouTube prefixes several distinct failures with "Video unavailable", so the
# specific causes must be tested before the generic one.
_ERROR_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("not a bot",),
     "YouTube asked for a sign-in to confirm you are not a bot. Try again later, "
     "or update yt-dlp with:\n  pip install -U yt-dlp"),
    (("age-restricted", "age restricted", "confirm your age", "inappropriate for some users"),
     "This video is age-restricted and cannot be downloaded without signing in."),
    (("private video", "is private"),
     "This video is private and cannot be downloaded."),
    (("available in your country", "blocked it in your country", "geo restricted",
      "geo-restricted", "not available from your location"),
     "This video is blocked in your region."),
    (("members-only", "join this channel", "paid content", "purchase"),
     "This video is behind a membership or purchase and cannot be downloaded."),
    (("removed by the uploader", "has been removed", "account associated with this video has been terminated",
      "video unavailable", "video is unavailable", "no longer available"),
     "This video is unavailable. It may have been removed, made private, or never existed."),
    (("is live", "live event will begin", "premieres in"),
     "Live streams and premieres are not supported. Wait until the stream has ended."),
    (("unsupported url", "no suitable extractor", "is not a valid url"),
     "That URL is not supported. Paste a link to a single video."),
    (("http error 404", "http error 410"),
     "Nothing was found at that URL. Check the link and paste a link to a single video."),
    (("requested format is not available", "no video formats"),
     "No downloadable video was found at that URL."),
    (("http error 429", "too many requests"),
     "The server is rate-limiting downloads. Wait a few minutes and try again."),
    (("unable to download webpage", "urlopen error", "timed out", "connection", "network is unreachable",
      "getaddrinfo failed", "temporary failure in name resolution"),
     "The download could not be completed because of a network problem. "
     "Check your connection and try again."),
    (("ffmpeg", "postprocessing"),
     "The download finished but the media could not be converted. "
     "Check that FFmpeg is installed and on your PATH."),
    (("no space left", "not enough space", "disk full"),
     "There is not enough free space in the download folder."),
    (("permission denied", "access is denied"),
     "The download folder cannot be written to. Choose a different folder."),
)


def describe_error(exc: BaseException) -> str:
    """
    Translate a yt-dlp failure into a message a user can act on.

    Never surfaces a traceback; unrecognised failures fall back to the library's
    own message with the most common remedy appended.
    """
    raw = str(exc).strip()
    lowered = raw.lower()
    for fragments, message in _ERROR_HINTS:
        if any(fragment in lowered for fragment in fragments):
            return message
    cleaned = raw.replace("ERROR: ", "").strip() or "the video could not be retrieved"
    return (
        f"The download failed: {cleaned}\n\n"
        "If this keeps happening the downloader may be out of date. Update it with:\n"
        "  pip install -U yt-dlp"
    )
