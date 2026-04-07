"""
transcriber.py — Whisper transcription service.

SRP: Only responsible for loading a Whisper model and producing transcript text.
OCP: Subclass TranscriptionService to swap in a different backend without
     touching the controller or UI.
DIP: The controller depends on this class through its public interface, not on
     whisper internals directly.
"""

import whisper

from src.models import ExportFormat


def _format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class TranscriptionService:
    """Loads a Whisper model and transcribes audio/video files."""

    def transcribe(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
    ) -> str:
        """
        Return the full transcript for *path* in the requested format.

        Args:
            path: Absolute path to the media file.
            model_name: Whisper model size (tiny/base/small/medium/large).
            export_format: ``ExportFormat.SRT`` or ``ExportFormat.PLAIN_TEXT``.
            do_translate: Translate to English instead of transcribing.

        Returns:
            Transcript string in the chosen format.
        """
        model = whisper.load_model(model_name)
        task = "translate" if do_translate else "transcribe"
        result = model.transcribe(path, verbose=False, task=task)

        if export_format is ExportFormat.SRT:
            return self._build_srt(result["segments"])
        return result["text"]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_srt(self, segments) -> str:
        """
        Produce a valid SRT file body.

        Format per block:
            <index>
            HH:MM:SS,mmm --> HH:MM:SS,mmm
            <text>
            <blank line>
        """
        blocks = []
        for i, seg in enumerate(segments, start=1):
            start = _format_srt_timestamp(seg["start"])
            end = _format_srt_timestamp(seg["end"])
            text = seg["text"].strip()
            blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
        return "\n".join(blocks)
