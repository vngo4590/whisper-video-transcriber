"""
transcriber.py — Whisper transcription service.

SRP: Only responsible for loading a Whisper model and producing transcript text.
OCP: Subclass TranscriptionService to swap in a different backend without
     touching the controller or UI.
DIP: The controller depends on this class through its public interface, not on
     whisper internals directly.
"""

import math

import whisper

from src.models import ExportFormat


def _format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_segment(seg: dict, max_words: int):
    """
    Yield ``(start_sec, end_sec, text)`` tuples for one Whisper segment.

    Strategy (most-accurate first):

    1. Word-level timestamps — when ``word_timestamps=True`` was passed to
       Whisper, each word carries its own ``start`` / ``end``.  Groups of
       words are formed and the group's span uses the first word's ``start``
       and the last word's ``end``.

    2. Equal-duration fallback — if word-level data is unavailable the
       segment duration is divided evenly across chunks.  Less accurate but
       still better than one giant subtitle.
    """
    word_data = seg.get("words") or []

    if word_data:
        yield from _split_by_word_timestamps(word_data, max_words)
    else:
        yield from _split_by_equal_duration(seg, max_words)


def _split_by_word_timestamps(word_data: list, max_words: int):
    """Use per-word timestamps produced by Whisper's DTW alignment."""
    num_chunks = math.ceil(len(word_data) / max_words)
    for i in range(num_chunks):
        chunk = word_data[i * max_words : (i + 1) * max_words]
        start = chunk[0]["start"]
        end   = chunk[-1]["end"]
        text  = " ".join(w["word"].strip() for w in chunk)
        yield start, end, text


def _split_by_equal_duration(seg: dict, max_words: int):
    """Fallback: divide segment duration evenly across word chunks."""
    words = seg["text"].strip().split()
    if not words:
        return

    total_duration = seg["end"] - seg["start"]
    num_chunks = math.ceil(len(words) / max_words)

    if num_chunks == 1:
        yield seg["start"], seg["end"], " ".join(words)
        return

    chunk_duration = total_duration / num_chunks
    for i in range(num_chunks):
        chunk_words = words[i * max_words : (i + 1) * max_words]
        chunk_start = seg["start"] + i * chunk_duration
        chunk_end   = seg["start"] + (i + 1) * chunk_duration
        yield chunk_start, chunk_end, " ".join(chunk_words)


class TranscriptionService:
    """Loads a Whisper model and transcribes audio/video files."""

    def transcribe(
        self,
        path: str,
        model_name: str,
        export_format: ExportFormat,
        do_translate: bool,
        max_words_per_subtitle: int,
    ) -> str:
        """
        Return the full transcript for *path* in the requested format.

        ``word_timestamps=True`` is always requested so that SRT splits
        use Whisper's DTW-aligned per-word timings instead of guessing.

        Args:
            path: Absolute path to the media file.
            model_name: Whisper model size (tiny/base/small/medium/large).
            export_format: ``ExportFormat.SRT`` or ``ExportFormat.PLAIN_TEXT``.
            do_translate: Translate to English instead of transcribing.
            max_words_per_subtitle: SRT only — maximum words per subtitle
                entry. Segments exceeding this are split into consecutive
                entries using word-level timestamps.

        Returns:
            Transcript string in the chosen format.
        """
        model = whisper.load_model(model_name)
        task = "translate" if do_translate else "transcribe"
        result = model.transcribe(
            path,
            verbose=False,
            task=task,
            word_timestamps=True,
        )

        if export_format is ExportFormat.SRT:
            return self._build_srt(result["segments"], max_words_per_subtitle)
        return result["text"]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_srt(self, segments, max_words_per_subtitle: int) -> str:
        """
        Produce a valid SRT file body.

        Each Whisper segment is split into one or more numbered blocks so
        that no single subtitle entry exceeds *max_words_per_subtitle* words.
        Word-level timestamps from DTW alignment are used for accurate timing.

        Format per block:
            <index>
            HH:MM:SS,mmm --> HH:MM:SS,mmm
            <text>
            <blank line>
        """
        blocks = []
        index = 1
        for seg in segments:
            for start, end, text in _split_segment(seg, max_words_per_subtitle):
                t_start = _format_srt_timestamp(start)
                t_end   = _format_srt_timestamp(end)
                blocks.append(f"{index}\n{t_start} --> {t_end}\n{text}\n")
                index += 1
        return "\n".join(blocks)
