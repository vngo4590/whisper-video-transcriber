"""
controllers/download.py — Remote media fetch workflow controller.

GRASP Controller: handles the "Fetch URL" system event from the UI. Drives the
                  media downloader on a background thread and pushes the
                  resulting local path back through callbacks.
DIP: Depends on the public interface of src.media.downloader — not on yt-dlp
     itself, and never on widgets.

Unlike the other controllers, cancellation here is checked *during* the long
operation rather than only between stages: the downloader's progress hook polls
the shared event on every invocation, so a fetch stops promptly.
"""

import threading

from src.controllers import OperationCancelledError
from src.media import downloader
from src.media.download_errors import FetchCancelled
from src.models import FetchMode


class DownloadController:
    """
    Mediates between the sidebar's URL input and the media downloader.

    The controller owns no widgets. UI state arrives as arguments; results are
    returned through callbacks supplied by the App.

    Args:
        on_start:   Called on the main thread before the worker starts.
        on_success: Called with the downloaded file's absolute path.
        on_error:   Called with an error message string.
        on_done:    Called after success *or* error.
        on_log:     Called (from the background thread) with ``(message, level)``
                    for the activity log — route through ``root.after()``.
        on_stage:   Called (from the background thread) with a stage string like
                    ``"Step 2/2 — Downloading…"`` — route through ``root.after()``.
    """

    _TOTAL_STEPS = 2

    def __init__(
        self,
        on_start,
        on_success,
        on_error,
        on_done,
        on_log=None,
        on_stage=None,
    ):
        self._on_start   = on_start
        self._on_success = on_success
        self._on_error   = on_error
        self._on_done    = on_done
        self._on_log     = on_log
        self._on_stage   = on_stage

    def run(
        self,
        url: str,
        dest_dir: str,
        fetch_mode: FetchMode,
        cancel_event: threading.Event = None,
    ) -> None:
        """
        Start a background fetch thread.

        Returns immediately; the result is delivered via the registered callbacks.

        Args:
            url:          A validated single-video URL.
            dest_dir:     Destination folder, already resolved on the main thread
                          because Tk dialogs must not be opened from a worker.
            fetch_mode:   FetchMode.VIDEO or FetchMode.AUDIO_ONLY.
            cancel_event: Set this event to request cancellation.
        """
        self._on_start()
        threading.Thread(
            target=self._worker,
            args=(url, dest_dir, fetch_mode, cancel_event or threading.Event()),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _log(self, msg: str, level: str = "info") -> None:
        if self._on_log:
            self._on_log(msg, level)

    def _stage(self, text: str) -> None:
        if self._on_stage:
            self._on_stage(text)

    def _check_cancel(self, cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise OperationCancelledError("Download cancelled by user.")

    def _worker(
        self,
        url: str,
        dest_dir: str,
        fetch_mode: FetchMode,
        cancel_event: threading.Event,
    ) -> None:
        try:
            self._check_cancel(cancel_event)

            # ── Stage 1: Resolve the URL's metadata ───────────────────
            self._stage(f"Step 1/{self._TOTAL_STEPS} — Reading video details…")
            self._log(f"Fetching from URL: {url}", "stage")
            self._log(f"  Destination: {dest_dir}", "detail")

            # ── Stage 2: Transfer ─────────────────────────────────────
            def on_progress(percent: float) -> None:
                self._stage(f"Step 2/{self._TOTAL_STEPS} — Downloading… {percent:.0f}%")

            self._stage(f"Step 2/{self._TOTAL_STEPS} — Downloading media…")
            path = downloader.fetch(
                url,
                dest_dir,
                fetch_mode,
                cancel_event,
                on_log=self._on_log,
                on_progress=on_progress,
            )

            self._check_cancel(cancel_event)
            self._log("Download complete.", "success")
            self._on_success(path)

        except FetchCancelled:
            # Translated at the layer boundary so the domain package never has
            # to import from src.controllers.
            self._log("Download cancelled.", "warn")
            self._on_error("Operation was cancelled.")
        except OperationCancelledError:
            self._log("Download cancelled.", "warn")
            self._on_error("Operation was cancelled.")
        except Exception as exc:
            self._log(f"Error: {exc}", "error")
            self._on_error(str(exc))
        finally:
            self._on_done()
