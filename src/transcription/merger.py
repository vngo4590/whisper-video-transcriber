"""
transcription/merger.py — Merges speech and on-screen text into a unified transcript.

SRP:  Sole responsibility is interleaving Whisper speech segments with OcrEntry
      on-screen text entries and formatting the result as either SRT or plain text.
      No knowledge of Whisper internals, OCR engines, file I/O, or UI widgets.

GRASP Information Expert: owns all knowledge about how the combined transcript
      is structured and labelled.  Callers just hand over the two data sources
      and ask for a string back.
"""

from src.transcription._srt_utils import (
    format_plain_timestamp,
    format_srt_timestamp,
    split_segment,
)
from src.transcription.ocr_extractor import OcrEntry


class TranscriptMerger:
    """
    Combines Whisper speech segments and OCR on-screen entries into one transcript.

    Every entry in the output is labelled so the reader always knows which type
    of transcription produced each line:

    SRT output example::

        1
        00:00:10,000 --> 00:00:12,500
        [SPEECH] Preheat your oven to 350 degrees.

        2
        00:00:11,000 --> 00:00:14,000
        [ON-SCREEN] Step 1: Preheat oven 350°F

    Plain-text output example::

        [SPEECH @ 00:00:10] Preheat your oven to 350 degrees.
        [ON-SCREEN @ 00:00:11] Step 1: Preheat oven 350°F
        [SPEECH @ 00:00:15] Now add two cups of flour.
    """

    # Source labels written into each output entry.
    # Keeping them as class constants makes it easy to change the wording in
    # one place without hunting through string literals.
    SPEECH_LABEL    = "[SPEECH]"
    ON_SCREEN_LABEL = "[ON-SCREEN]"

    def merge_to_srt(
        self,
        speech_segments: list[dict],
        ocr_entries: list[OcrEntry],
        max_words_per_subtitle: int,
    ) -> str:
        """
        Produce an SRT string that interleaves speech and on-screen entries.

        Speech segments follow the same splitting rules as the standard (no-OCR)
        path: each Whisper segment is broken into blocks of at most
        *max_words_per_subtitle* words using DTW word-level timestamps.

        OCR entries are inserted as single SRT blocks — they already represent
        a single coherent piece of on-screen text.

        Entries with the same start time are sorted speech-first so that a spoken
        word and a simultaneously appearing caption do not produce confusing ordering.

        Args:
            speech_segments:       Raw Whisper segment dicts from model.transcribe().
            ocr_entries:           OcrEntry list from OcrExtractor.extract().
            max_words_per_subtitle: Max words per SRT block for speech segments.

        Returns:
            Complete SRT file contents as a string.
        """
        # Build a flat list of (start, end, label, text) for all entries
        items: list[tuple[float, float, str, str]] = []

        # Add speech entries, split by word limit
        for seg in speech_segments:
            for start, end, text in split_segment(seg, max_words_per_subtitle):
                items.append((start, end, self.SPEECH_LABEL, text))

        # Add on-screen entries as-is (already one text block per span)
        for entry in ocr_entries:
            items.append((entry.start, entry.end, self.ON_SCREEN_LABEL, entry.text))

        # Sort chronologically; speech before on-screen when timestamps are equal
        items.sort(key=lambda x: (x[0], 0 if x[2] == self.SPEECH_LABEL else 1))

        blocks = []
        for idx, (start, end, label, text) in enumerate(items, start=1):
            t_start = format_srt_timestamp(start)
            t_end   = format_srt_timestamp(end)
            # SRT block: index, time range, labelled text, blank line separator
            blocks.append(f"{idx}\n{t_start} --> {t_end}\n{label} {text}\n")

        return "\n".join(blocks)

    def merge_to_plain(
        self,
        speech_segments: list[dict],
        ocr_entries: list[OcrEntry],
    ) -> str:
        """
        Produce plain text with inline source labels and timestamps.

        Each line follows one of two patterns:
            [SPEECH @ HH:MM:SS] <spoken text>
            [ON-SCREEN @ HH:MM:SS] <visible text>

        This makes it easy to scan a recipe or instruction transcript and
        distinguish what was said from what was shown on the screen.

        Args:
            speech_segments: Raw Whisper segment dicts.
            ocr_entries:     OcrEntry list from OcrExtractor.

        Returns:
            Plain-text transcript as a multi-line string.
        """
        items: list[tuple[float, str, str]] = []

        # One entry per Whisper segment (we don't sub-split in plain-text mode)
        for seg in speech_segments:
            items.append((seg["start"], self.SPEECH_LABEL, seg["text"].strip()))

        for entry in ocr_entries:
            items.append((entry.start, self.ON_SCREEN_LABEL, entry.text))

        # Sort chronologically; speech first on ties
        items.sort(key=lambda x: (x[0], 0 if x[1] == self.SPEECH_LABEL else 1))

        lines = []
        for start, label, text in items:
            ts = format_plain_timestamp(start)

            # Strip the outer brackets from the label so we can inject the
            # timestamp inside:  "[SPEECH]" → "[SPEECH @ 00:00:10]"
            clean_label = label.strip("[]")
            lines.append(f"[{clean_label} @ {ts}] {text}")

        return "\n".join(lines)
