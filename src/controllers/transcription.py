"""
controllers/transcription.py — Transcription workflow controller.

GRASP Controller: handles the "Transcribe" system event from the UI.
                  Orchestrates TranscriptionService and FileHandler,
                  then pushes results back to the UI via callbacks.
DIP: Depends on the public interfaces of TranscriptionService and
     FileHandler — not on their internals or on tkinter directly.
"""

import os
import threading

from src.controllers import OperationCancelledError
from src.transcription.file_handler import FileHandler
from src.models import ExportFormat
from src.transcription.service import TranscriptionService


class TranscriptionController:
    """
    Mediates between the left-panel UI and the transcription services.

    The controller owns no widgets.  UI state is received as arguments;
    results are returned through callbacks supplied by the App.

    Cancellation is cooperative: the worker checks *cancel_event* between
    pipeline stages.  The current Whisper or OCR call runs to completion
    before the cancellation is noticed — this keeps files uncorrupted.

    Args:
        transcription_service: Provides the transcribe() operation.
        file_handler:          Provides the save_transcription() operation.
        on_start:    Called on the main thread before the worker starts.
        on_success:  Called on the main thread with ``(text, output_path)``.
        on_error:    Called on the main thread with an error message string.
        on_done:     Called on the main thread after success *or* error.
        on_log:      Called (from background thread) with ``(message, level)``
                     for the activity log — route through ``root.after()``.
    """

    def __init__(
        self,
        transcription_service: TranscriptionService,
        file_handler: FileHandler,
        on_start,
        on_success,
        on_error,
        on_done,
        on_log=None,
    ):
        self._svc      = transcription_service
        self._file     = file_handler
        self._on_start = on_start
        self._on_success = on_success
        self._on_error   = on_error
        self._on_done    = on_done
        self._on_log     = on_log

    def run(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
        max_words_per_line: int,
        extract_onscreen: bool = False,
        ocr_languages: list[str] | None = None,
        cancel_event: threading.Event = None,
    ) -> None:
        """
        Start a background transcription thread.

        Returns immediately; results are delivered via the registered callbacks.

        Args:
            path:              Absolute path to the media file.
            model_name:        Whisper model size.
            export_format:     SRT or plain text.
            do_translate:      Translate to English.
            max_words_per_line: SRT word limit per block.
            extract_onscreen:  Run OCR and interleave on-screen text.
            ocr_languages:     EasyOCR language codes (only used when extract_onscreen=True).
            cancel_event:      Set this event to request cancellation.
        """
        self._on_start()
        threading.Thread(
            target=self._worker,
            args=(
                path, model_name, export_format, do_translate,
                max_words_per_line, extract_onscreen, ocr_languages,
                cancel_event or threading.Event(),
            ),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _log(self, msg: str, level: str = "info") -> None:
        """Forward to the on_log callback if one was registered."""
        if self._on_log:
            self._on_log(msg, level)

    def _check_cancel(self, cancel_event: threading.Event) -> None:
        """Raise OperationCancelledError if the user has requested a cancel."""
        if cancel_event.is_set():
            raise OperationCancelledError("Transcription cancelled by user.")

    def _worker(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
        max_words_per_line: int,
        extract_onscreen: bool,
        ocr_languages: list[str] | None,
        cancel_event: threading.Event,
    ) -> None:
        try:
            filename = os.path.basename(path)

            # ── Stage 1: Transcribe with Whisper ──────────────────────
            self._log(f"Transcribing: {filename}", "stage")
            self._log(f"  model={model_name}  format={export_format.value}  translate={do_translate}", "detail")
            if extract_onscreen and ocr_languages:
                self._log(f"  OCR languages: {ocr_languages}", "detail")

            text = self._svc.transcribe(
                path, model_name, export_format, do_translate, max_words_per_line,
                extract_onscreen=extract_onscreen,
                ocr_languages=ocr_languages,
                on_log=self._on_log,
            )

            # Check cancellation after the (potentially long) Whisper pass
            self._check_cancel(cancel_event)

            # ── Stage 2: Save to disk ─────────────────────────────────
            self._log("Saving transcript to disk…", "detail")
            output_path = self._file.save_transcription(path, text, export_format)
            self._log(f"Saved → {output_path}", "detail")

            self._log("Transcription complete.", "success")
            self._on_success(text, output_path)

        except OperationCancelledError:
            self._log("Transcription cancelled.", "warn")
            self._on_error("Operation was cancelled.")
        except Exception as exc:
            self._log(f"Error: {exc}", "error")
            self._on_error(str(exc))
        finally:
            self._on_done()
