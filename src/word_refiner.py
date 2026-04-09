"""
word_refiner.py — Word-level post-processing for clip boundary quality.

SRP: Pure functions that operate on Whisper word timestamps to:
     - Build a flat word index from Whisper segment data
     - Snap cut boundaries to word edges (for "allow cut anywhere" mode)
     - Trim leading/trailing filler words off segment boundaries
     - Remove consecutive stutter runs by splitting into micro-segments

No I/O, no state, no UI dependencies.  All functions are safe to call from
a background thread.
"""

import string

from src.models import FILLER_WORDS, MIN_WORD_DURATION, ClipResult, Segment


# ---------------------------------------------------------------------------
# Word index
# ---------------------------------------------------------------------------

def build_word_index(whisper_segments: list) -> list[dict]:
    """
    Flatten all word dicts from every Whisper segment into a single
    time-sorted list.  Each entry: {"start": float, "end": float, "word": str}.
    Words whose duration is below MIN_WORD_DURATION are dropped (Whisper noise).
    """
    words: list[dict] = []
    for seg in whisper_segments:
        for w in seg.get("words", []):
            try:
                start = float(w["start"])
                end   = float(w["end"])
                word  = str(w["word"])
            except (KeyError, TypeError, ValueError):
                continue
            if end - start >= MIN_WORD_DURATION and word.strip():
                words.append({"start": start, "end": end, "word": word})
    return sorted(words, key=lambda w: w["start"])


# ---------------------------------------------------------------------------
# Word-level boundary snapping
# ---------------------------------------------------------------------------

def snap_to_word_boundary(
    clips: list[ClipResult],
    word_index: list[dict],
    video_duration: float,
) -> list[ClipResult]:
    """
    Snap each segment start/end to the nearest word boundary.

    Used when allow_cut_anywhere=True — ensures cuts always land between
    complete words, never inside a phoneme, without enforcing full-sentence
    alignment.  Uses the same strictly_after guard as the segment-level snap
    to prevent a word from appearing in two consecutive segments.
    """
    if not word_index:
        return clips

    for clip in clips:
        snapped: list[Segment] = []
        prev_end: float = -1.0

        for seg in clip.segments:
            s = _snap_start_word(seg.start, word_index, strictly_after=prev_end)
            e = _snap_end_word(seg.end, word_index, video_duration)
            if e > s:
                snapped.append(Segment(s, e))
                prev_end = e

        if snapped:
            clip.segments = snapped

    return clips


def _snap_start_word(
    requested: float,
    word_index: list[dict],
    strictly_after: float = -1.0,
) -> float:
    first_unused: float | None = None
    for w in word_index:
        if w["start"] <= strictly_after:
            continue
        if first_unused is None:
            first_unused = w["start"]
        if w["end"] >= requested:
            return w["start"]
    return first_unused if first_unused is not None else requested


def _snap_end_word(
    requested: float,
    word_index: list[dict],
    video_duration: float,
) -> float:
    best = requested
    for w in word_index:
        if w["start"] <= requested:
            best = w["end"]
    return min(best, video_duration)


# ---------------------------------------------------------------------------
# Filler trimming
# ---------------------------------------------------------------------------

def trim_leading_fillers(
    seg: Segment,
    word_index: list[dict],
    max_trim_fraction: float = 0.25,
) -> Segment:
    """
    Advance seg.start past any leading filler words.

    Checks 2-grams ("you know") before 1-grams so multi-word fillers are
    caught as a unit.  Never trims more than max_trim_fraction of the
    segment's original duration to avoid catastrophic over-trimming on
    short segments.
    """
    words_in_seg = _words_in_segment(seg, word_index)
    if not words_in_seg:
        return seg

    max_trim = seg.duration * max_trim_fraction
    new_start = seg.start
    i = 0

    while i < len(words_in_seg):
        # 2-gram check first
        if i + 1 < len(words_in_seg):
            bigram = _normalize(words_in_seg[i]["word"] + " " + words_in_seg[i + 1]["word"])
            if bigram in FILLER_WORDS:
                candidate = words_in_seg[i + 2]["start"] if i + 2 < len(words_in_seg) else seg.end
                if candidate - seg.start <= max_trim:
                    new_start = candidate
                    i += 2
                    continue
                else:
                    break
        # 1-gram check
        if _normalize(words_in_seg[i]["word"]) in FILLER_WORDS:
            candidate = words_in_seg[i + 1]["start"] if i + 1 < len(words_in_seg) else seg.end
            if candidate - seg.start <= max_trim:
                new_start = candidate
                i += 1
                continue
        break

    if new_start >= seg.end:
        return seg
    return Segment(new_start, seg.end)


def trim_trailing_fillers(
    seg: Segment,
    word_index: list[dict],
    max_trim_fraction: float = 0.25,
) -> Segment:
    """
    Retreat seg.end before any trailing filler words.
    Same guard logic as trim_leading_fillers, applied from the right.
    """
    words_in_seg = _words_in_segment(seg, word_index)
    if not words_in_seg:
        return seg

    max_trim = seg.duration * max_trim_fraction
    new_end = seg.end
    i = len(words_in_seg) - 1

    while i >= 0:
        # 2-gram check first (words[i-1] + words[i])
        if i > 0:
            bigram = _normalize(words_in_seg[i - 1]["word"] + " " + words_in_seg[i]["word"])
            if bigram in FILLER_WORDS:
                candidate = words_in_seg[i - 1]["start"]
                if seg.end - candidate <= max_trim:
                    new_end = candidate
                    i -= 2
                    continue
                else:
                    break
        # 1-gram check
        if _normalize(words_in_seg[i]["word"]) in FILLER_WORDS:
            candidate = words_in_seg[i]["start"]
            if seg.end - candidate <= max_trim:
                new_end = candidate
                i -= 1
                continue
        break

    if new_end <= seg.start:
        return seg
    return Segment(seg.start, new_end)


# ---------------------------------------------------------------------------
# Stutter removal
# ---------------------------------------------------------------------------

def remove_stutters(
    seg: Segment,
    word_index: list[dict],
    min_sub_segment_duration: float = 0.3,
) -> list[Segment]:
    """
    Detect consecutive same-word runs and split the segment around them.

    A stutter is two or more consecutive occurrences of the same normalised
    word (e.g. "I I want", "the the the thing").  All but the final occurrence
    are excised by splitting the segment into sub-segments with a micro-cut.

    Returns [seg] unchanged if no stutters found, or a list of sub-segments.
    Sub-segments shorter than min_sub_segment_duration are dropped.
    The sub-segments slot directly into clip.segments without any changes to
    video_cutter.py (it already concatenates arbitrary segment lists).
    """
    words_in_seg = _words_in_segment(seg, word_index)
    if len(words_in_seg) < 2:
        return [seg]

    # Identify stutter runs: consecutive identical normalised words, len >= 2
    stutter_ranges: list[tuple[int, int]] = []  # (first_idx, last_idx) inclusive
    i = 0
    while i < len(words_in_seg):
        j = i + 1
        norm_i = _normalize(words_in_seg[i]["word"])
        while j < len(words_in_seg) and _normalize(words_in_seg[j]["word"]) == norm_i:
            j += 1
        if j - i >= 2:
            stutter_ranges.append((i, j - 1))
        i = j

    if not stutter_ranges:
        return [seg]

    sub_segments: list[Segment] = []
    seg_cursor = seg.start

    for stutter_start_idx, stutter_end_idx in stutter_ranges:
        # End the current sub-segment just before the first duplicate word
        cut_end = words_in_seg[stutter_start_idx]["start"]
        if cut_end - seg_cursor >= min_sub_segment_duration:
            sub_segments.append(Segment(seg_cursor, cut_end))
        # Resume from the last (clean) occurrence of the stuttered word
        seg_cursor = words_in_seg[stutter_end_idx]["start"]

    # Final sub-segment from last stutter to original end
    if seg.end - seg_cursor >= min_sub_segment_duration:
        sub_segments.append(Segment(seg_cursor, seg.end))

    return sub_segments if sub_segments else [seg]


# ---------------------------------------------------------------------------
# Clip-level refinement
# ---------------------------------------------------------------------------

def refine_clip(
    clip: ClipResult,
    word_index: list[dict],
    min_sub_segment_duration: float,
) -> ClipResult:
    """
    Apply filler trimming then stutter removal to every segment in the clip.

    Order per segment:
      1. trim_leading_fillers  — advance start past opening fillers
      2. trim_trailing_fillers — retreat end before closing fillers
      3. remove_stutters       — may expand one segment into several sub-segs

    clip.segments is mutated in place (matches the existing pattern in
    _snap_boundaries and _filter_short_segments).
    """
    refined: list[Segment] = []
    for seg in clip.segments:
        seg = trim_leading_fillers(seg, word_index)
        seg = trim_trailing_fillers(seg, word_index)
        refined.extend(remove_stutters(seg, word_index, min_sub_segment_duration))
    clip.segments = refined
    return clip


def refine_all_clips(
    clips: list[ClipResult],
    word_index: list[dict],
    min_sub_segment_duration: float = 0.3,
) -> list[ClipResult]:
    """Stage 2d entry point.  Drops clips that end up with zero segments."""
    result: list[ClipResult] = []
    for clip in clips:
        refine_clip(clip, word_index, min_sub_segment_duration)
        if clip.segments:
            result.append(clip)
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _words_in_segment(seg: Segment, word_index: list[dict]) -> list[dict]:
    """Return all words whose start falls within [seg.start, seg.end)."""
    return [w for w in word_index if seg.start <= w["start"] < seg.end]


def _normalize(word: str) -> str:
    """Lowercase and strip surrounding punctuation for comparison."""
    return word.strip(string.punctuation + string.whitespace).lower()
