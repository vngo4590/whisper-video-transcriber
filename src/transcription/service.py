"""
transcription/service.py — Whisper transcription service.

SRP:  Loads a Whisper model, transcribes the media file, and returns the result
      as a formatted string.  Optionally coordinates OcrExtractor/TranscriptMerger
      (on-screen text) and SpeakerDiarizer (speaker labels) — but delegates all
      such work to those classes.

OCP:  Subclass TranscriptionService to swap in a different speech backend
      (e.g. faster-whisper, cloud ASR) without touching the controller or UI.

DIP:  The controller depends on this class's public interface, not on Whisper
      internals, EasyOCR, pyannote, or SRT-building details.
"""

import whisper

from src.models import ExportFormat
from src.transcription._srt_utils import (
    format_plain_timestamp,
    format_srt_timestamp,
    split_segment,
)


class TranscriptionService:
    """
    Loads a Whisper model and transcribes audio/video files.

    Supports three output modes:

    * Speech-only         — standard Whisper transcription, SRT or plain text.
    * With on-screen text — speech interleaved with OCR-extracted on-screen
                            text; each entry is labelled [SPEECH] or [ON-SCREEN].
    * With speaker labels — speaker diarization labels prepended to each block
                            (e.g. ``[Speaker A]``); can be combined with OCR.
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
        diarize: bool = False,
        num_speakers: int = 0,
        on_diarize_stage=None,
        on_log=None,
    ) -> str:
        """
        Return the full transcript for *path* in the requested format.

        Args:
            path:                  Absolute path to the media file.
            model_name:            Whisper model size (tiny/base/small/medium/large).
            export_format:         SRT or PLAIN_TEXT output.
            do_translate:          Translate to English instead of transcribing.
            max_words_per_subtitle: SRT only — max words per subtitle block.
            extract_onscreen:      Run OCR on video frames and interleave results.
            ocr_languages:         EasyOCR language codes, e.g. ``["en", "ja"]``.
            diarize:               Run speaker diarization and label each segment.
            num_speakers:          Hint for expected speaker count. 0 = auto-detect.
            on_diarize_stage:      Zero-arg callback fired just before diarization
                                   starts — lets the controller update the sidebar label.
            on_log:                Optional ``(message, level)`` callback.

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
            word_timestamps=True,
        )
        seg_count = len(result.get("segments", []))
        _log(f"Whisper complete — {seg_count} segment(s) detected", "detail")

        # ── Optional: speaker diarization ────────────────────────────────────
        if diarize:
            if on_diarize_stage:
                on_diarize_stage()
            from src.transcription.diarizer import SpeakerDiarizer, assign_speakers
            diarization = SpeakerDiarizer().diarize(path, num_speakers=num_speakers, on_log=on_log)
            assign_speakers(result["segments"], diarization)

        # ── Optional: on-screen text extraction ──────────────────────────────
        if extract_onscreen:
            return self._transcribe_with_onscreen(
                path, result, export_format, max_words_per_subtitle,
                ocr_languages=ocr_languages, on_log=on_log,
            )

        # ── Standard formatting ───────────────────────────────────────────────
        if export_format is ExportFormat.SRT:
            return self._build_srt(result["segments"], max_words_per_subtitle)
        return self._build_plain(result["segments"])

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
    # Private — formatting helpers
    # ------------------------------------------------------------------

    def _build_srt(self, segments: list[dict], max_words_per_subtitle: int) -> str:
        """
        Produce a valid SRT body from Whisper segments.

        When segments carry a ``"speaker"`` key (from diarization), each block
        is prefixed with ``[Speaker A]`` etc.
        """
        from src.transcription.diarizer import label_to_display
        blocks = []
        index  = 1
        for seg in segments:
            speaker = seg.get("speaker", "")
            prefix  = f"[{label_to_display(speaker)}] " if speaker else ""
            for start, end, text in split_segment(seg, max_words_per_subtitle):
                t_start = format_srt_timestamp(start)
                t_end   = format_srt_timestamp(end)
                blocks.append(f"{index}\n{t_start} --> {t_end}\n{prefix}{text}\n")
                index += 1
        return "\n".join(blocks)

    def _build_plain(self, segments: list[dict]) -> str:
        """
        Produce plain text from Whisper segments.

        Without diarization: returns concatenated segment text (matching the
        original ``str(result['text'])`` behaviour).
        With diarization: each segment line is prefixed ``[Speaker A @ HH:MM:SS]:``.
        """
        from src.transcription.diarizer import label_to_display
        has_speakers = any(seg.get("speaker") for seg in segments)
        if not has_speakers:
            return " ".join(seg["text"].strip() for seg in segments if seg["text"].strip())

        lines = []
        for seg in segments:
            text = seg["text"].strip()
            if not text:
                continue
            speaker = seg.get("speaker", "")
            ts      = format_plain_timestamp(seg["start"])
            label   = label_to_display(speaker) if speaker else "Speaker"
            lines.append(f"[{label} @ {ts}]: {text}")
        return "\n".join(lines)
