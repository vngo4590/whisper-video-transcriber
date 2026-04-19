"""
transcription/service.py — Whisper transcription service.

SRP:  Loads a Whisper model, transcribes the media file, and returns the result
      as a formatted string.  When on-screen text extraction is enabled it also
      coordinates OcrExtractor and TranscriptMerger — but delegates all OCR and
      formatting work to those classes.

OCP:  Subclass TranscriptionService to swap in a different speech backend
      (e.g. faster-whisper, cloud ASR) without touching the controller or UI.

DIP:  The controller depends on this class's public interface, not on Whisper
      internals, EasyOCR, or SRT-building details.
"""

import whisper

from src.models import ExportFormat
from src.transcription._srt_utils import format_srt_timestamp, split_segment


class TranscriptionService:
    """
    Loads a Whisper model and transcribes audio/video files.

    Supports two output modes:

    * Speech-only  — standard Whisper transcription, SRT or plain text.
    * With on-screen text — speech interleaved with OCR-extracted on-screen
      text; each entry is labelled [SPEECH] or [ON-SCREEN] so the source is
      always clear.
    """

    def transcribe(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
        max_words_per_subtitle: int,
        extract_onscreen: bool = False,
        ocr_languages: list[str] | None = None,
        on_log=None,
    ) -> str:
        """
        Return the full transcript for *path* in the requested format.

        When *extract_onscreen* is True the method also samples the video with
        OcrExtractor and merges the results with the speech transcript via
        TranscriptMerger.  Both speech entries and on-screen entries are labelled
        so the caller can always tell which type produced each line.

        Args:
            path:                  Absolute path to the media file.
            model_name:            Whisper model size (tiny/base/small/medium/large).
            export_format:         SRT or PLAIN_TEXT output.
            do_translate:          Translate to English instead of transcribing.
            max_words_per_subtitle: SRT only — max words per subtitle block.
            extract_onscreen:      When True, also run OCR on video frames and
                                   interleave on-screen text into the output.
            ocr_languages:         EasyOCR language codes, e.g. ``["en", "ja"]``.
                                   Only used when *extract_onscreen* is True.
                                   Defaults to ``["en"]``.
            on_log:                Optional ``(message, level)`` callback for
                                   detailed progress reporting.

        Returns:
            Transcript string in the chosen format.
        """
        def _log(msg: str, level: str = "info") -> None:
            if on_log:
                on_log(msg, level)

        import os
        filename = os.path.basename(path)
        task = "translate" if do_translate else "transcribe"

        _log(f"Loading Whisper model: {model_name}", "detail")
        model = whisper.load_model(model_name)

        _log(f"Starting {'translation' if do_translate else 'transcription'}: {filename}", "detail")
        _log(f"  word_timestamps=True  task={task}", "detail")
        result = model.transcribe(
            path,
            verbose=False,
            task=task,
            word_timestamps=True,   # enables DTW-aligned per-word timing for SRT splits
        )
        seg_count = len(result.get("segments", []))
        _log(f"Whisper complete — {seg_count} segment(s) detected", "detail")

        if extract_onscreen:
            return self._transcribe_with_onscreen(
                path, result, export_format, max_words_per_subtitle,
                ocr_languages=ocr_languages, on_log=on_log,
            )

        # Standard speech-only path (unchanged behaviour)
        if export_format is ExportFormat.SRT:
            return self._build_srt(result["segments"], max_words_per_subtitle)
        return str(result["text"])

    # ------------------------------------------------------------------
    # Private — on-screen extraction path
    # ------------------------------------------------------------------

    def _transcribe_with_onscreen(
        self,
        path: str,
        whisper_result: dict,
        export_format: ExportFormat,
        max_words_per_subtitle: int,
        ocr_languages: list[str] | None = None,
        on_log=None,
    ) -> str:
        """
        Run OCR on the video, then merge speech and on-screen text.

        Importing OcrExtractor and TranscriptMerger here (not at module level)
        so that easyocr is only imported when the feature is actually used.
        Users who never enable on-screen extraction are not burdened by the
        easyocr import or its model-loading overhead.
        """
        # Deferred imports keep the module importable even without easyocr installed
        from src.transcription.ocr_extractor import OcrExtractor
        from src.transcription.merger import TranscriptMerger

        ocr_entries = OcrExtractor().extract(path, languages=ocr_languages, on_log=on_log)
        merger      = TranscriptMerger()

        if export_format is ExportFormat.SRT:
            return merger.merge_to_srt(
                whisper_result["segments"], ocr_entries, max_words_per_subtitle
            )
        return merger.merge_to_plain(whisper_result["segments"], ocr_entries)

    # ------------------------------------------------------------------
    # Private — speech-only SRT builder
    # ------------------------------------------------------------------

    def _build_srt(self, segments, max_words_per_subtitle: int) -> str:
        """
        Produce a valid SRT file body from Whisper segments (no OCR).

        Each segment is split into blocks of at most *max_words_per_subtitle*
        words using DTW word-level timestamps for accurate per-block timing.

        Format per block:
            <index>
            HH:MM:SS,mmm --> HH:MM:SS,mmm
            <text>
            <blank line>
        """
        blocks = []
        index  = 1
        for seg in segments:
            for start, end, text in split_segment(seg, max_words_per_subtitle):
                t_start = format_srt_timestamp(start)
                t_end   = format_srt_timestamp(end)
                blocks.append(f"{index}\n{t_start} --> {t_end}\n{text}\n")
                index += 1
        return "\n".join(blocks)
