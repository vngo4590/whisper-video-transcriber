"""
controllers/transcription.py — Transcription workflow controller.

GRASP Controller: handles the "Transcribe" system event from the UI.
                  Orchestrates TranscriptionService and FileHandler,
                  then pushes results back to the UI via callbacks.
DIP: Depends on the public interfaces of TranscriptionService and
     FileHandler — not on their internals or on tkinter directly.
"""

import threading

from src.transcription.file_handler import FileHandler
from src.models import ExportFormat
from src.transcription.service import TranscriptionService


class TranscriptionController:
    """
    Mediates between the left-panel UI and the transcription services.

    The controller owns no widgets.  UI state is received as arguments;
    results are returned through the *on_success* / *on_error* / *on_done*
    callbacks supplied by the caller (the App).

    Args:
        transcription_service: Provides the transcribe() operation.
        file_handler: Provides the save_transcription() operation.
        on_start: Called on the main thread before the worker starts.
        on_success: Called on the main thread with ``(text, output_path)``.
        on_error: Called on the main thread with an error message string.
        on_done: Called on the main thread after success *or* error.
    """

    def __init__(
        self,
        transcription_service: TranscriptionService,
        file_handler: FileHandler,
        on_start,
        on_success,
        on_error,
        on_done,
    ):
        self._svc = transcription_service
        self._file = file_handler
        self._on_start = on_start
        self._on_success = on_success
        self._on_error = on_error
        self._on_done = on_done

    def run(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
        max_words_per_line: int,
        extract_onscreen: bool = False,
    ) -> None:
        """
        Start a background transcription thread.

        Returns immediately; results are delivered via the callbacks
        registered at construction time.

        Args:
            path:              Absolute path to the media file.
            model_name:        Whisper model size.
            export_format:     SRT or plain text.
            do_translate:      Translate to English.
            max_words_per_line: SRT word limit per block.
            extract_onscreen:  When True, OCR is run on video frames and
                               on-screen text is interleaved into the output,
                               labelled [SPEECH] or [ON-SCREEN].
        """
        self._on_start()
        threading.Thread(
            target=self._worker,
            args=(path, model_name, export_format, do_translate, max_words_per_line, extract_onscreen),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _worker(self, path, model_name, export_format, do_translate, max_words_per_line, extract_onscreen):
        try:
            text = self._svc.transcribe(
                path, model_name, export_format, do_translate, max_words_per_line,
                extract_onscreen=extract_onscreen,
            )
            output_path = self._file.save_transcription(path, text, export_format)
            self._on_success(text, output_path)
        except Exception as exc:
            self._on_error(str(exc))
        finally:
            self._on_done()
