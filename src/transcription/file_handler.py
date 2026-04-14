"""
transcription/file_handler.py — File I/O for transcription results.

SRP: Only responsible for persisting transcript text to disk.
     No knowledge of Whisper, UI, or media processing.
"""

import os

from src.models import ExportFormat

_EXTENSION = {
    ExportFormat.SRT: ".srt",
    ExportFormat.PLAIN_TEXT: ".txt",
}


class FileHandler:
    """Saves transcription output next to the source media file."""

    def save_transcription(
        self, source_path: str, text: str, export_format: ExportFormat
    ) -> str:
        """
        Write *text* to a file derived from *source_path*.

        The output file is placed in the same directory as the source.
        The suffix is ``_transcription.srt`` or ``_transcription.txt``
        depending on *export_format*.

        Args:
            source_path: Absolute path to the original media file.
            text: Transcript text to write.
            export_format: Determines the output file extension.

        Returns:
            Absolute path to the saved file.
        """
        ext = _EXTENSION[export_format]
        output_path = os.path.splitext(source_path)[0] + f"_transcription{ext}"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        return output_path
