"""
transcription/_srt_utils.py — Shared SRT formatting helpers.

SRP: Single home for timestamp formatting and segment-splitting logic used by
     both TranscriptionService (speech-only path) and TranscriptMerger
     (merged speech + on-screen path).  Neither caller needs to know *how*
     SRT timestamps are constructed.
"""

import math


def format_srt_timestamp(seconds: float) -> str:
    """Convert a floating-point second value to SRT format: HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h,  ms = divmod(ms, 3_600_000)
    m,  ms = divmod(ms,    60_000)
    s,  ms = divmod(ms,     1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_plain_timestamp(seconds: float) -> str:
    """Convert a floating-point second value to HH:MM:SS (no milliseconds)."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def split_segment(seg: dict, max_words: int):
    """
    Yield (start_sec, end_sec, text) tuples for one Whisper segment dict.

    Tries word-level timestamps first (DTW-aligned, most accurate).
    Falls back to evenly dividing the segment duration if word data is absent.
    """
    word_data = seg.get("words") or []
    if word_data:
        yield from _split_by_word_timestamps(word_data, max_words)
    else:
        yield from _split_by_equal_duration(seg, max_words)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

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
    num_chunks     = math.ceil(len(words) / max_words)

    if num_chunks == 1:
        yield seg["start"], seg["end"], " ".join(words)
        return

    chunk_duration = total_duration / num_chunks
    for i in range(num_chunks):
        chunk_words = words[i * max_words : (i + 1) * max_words]
        chunk_start = seg["start"] + i * chunk_duration
        chunk_end   = seg["start"] + (i + 1) * chunk_duration
        yield chunk_start, chunk_end, " ".join(chunk_words)
