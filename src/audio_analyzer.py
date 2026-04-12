"""
audio_analyzer.py — Audio energy analysis for streamer highlight detection.

SRP: Only responsible for decoding audio from a video file and identifying
     high-energy windows (peaks) using RMS analysis.  No ffmpeg cutting, no UI,
     no Claude calls.

Used exclusively in HIGHLIGHTS clip mode.
"""

import numpy as np
import ffmpeg


def build_energy_windows(
    video_path: str,
    whisper_segs: list,
    window_s: float = 2.0,
    hop_s: float = 0.5,
    threshold_db: float = 6.0,
    sample_rate: int = 16000,
) -> list[dict]:
    """
    Slide an RMS window over the audio track and return windows whose energy
    is at least *threshold_db* above the overall mean.

    Only windows that temporally overlap with at least one Whisper speech
    segment are included (pure silence / dead-air between speech is ignored).

    Args:
        video_path:    Path to the source video file.
        whisper_segs:  Whisper segment list (used to filter out non-speech peaks).
        window_s:      RMS window length in seconds.
        hop_s:         Window hop in seconds (controls resolution).
        threshold_db:  How many dB above mean a window must be to qualify.
        sample_rate:   Audio sample rate for decoding.

    Returns:
        List of {"start": float, "end": float, "rms_db": float,
                 "above_mean_db": float} sorted by start time, with
        overlapping windows merged into contiguous peaks.
    """
    audio = _extract_audio(video_path, sample_rate)
    window_n = int(window_s * sample_rate)
    hop_n    = int(hop_s    * sample_rate)

    if window_n <= 0 or len(audio) < window_n:
        return []

    # Compute RMS (dB) for every hop position
    raw_windows: list[dict] = []
    i = 0
    while i + window_n <= len(audio):
        chunk = audio[i: i + window_n]
        rms   = float(np.sqrt(np.mean(chunk ** 2)))
        db    = 20.0 * np.log10(max(rms, 1e-10))
        raw_windows.append({
            "start":  i / sample_rate,
            "end":    (i + window_n) / sample_rate,
            "rms_db": db,
        })
        i += hop_n

    if not raw_windows:
        return []

    mean_db = float(np.mean([w["rms_db"] for w in raw_windows]))

    # Keep windows above the threshold and annotate how much above mean
    peaks = [
        {
            "start":        w["start"],
            "end":          w["end"],
            "rms_db":       w["rms_db"],
            "above_mean_db": round(w["rms_db"] - mean_db, 1),
        }
        for w in raw_windows
        if w["rms_db"] - mean_db >= threshold_db
    ]

    # Merge overlapping/adjacent peak windows into contiguous blocks
    peaks = _merge_windows(peaks)

    # Keep only peaks that overlap with at least one Whisper speech segment.
    # When whisper_segs is empty (silent / non-speech video) the filter is
    # skipped so all energy peaks are preserved for visual-only content.
    seg_ranges = [(float(s["start"]), float(s["end"])) for s in whisper_segs]
    if seg_ranges:
        peaks = [p for p in peaks if _overlaps_any(p, seg_ranges)]

    return peaks


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_audio(video_path: str, sample_rate: int) -> np.ndarray:
    """
    Decode the audio track of *video_path* to a mono float32 numpy array
    using ffmpeg-python (already a project dependency).
    """
    out, _ = (
        ffmpeg
        .input(video_path)
        .output(
            "pipe:",
            format="f32le",
            acodec="pcm_f32le",
            ac=1,
            ar=str(sample_rate),
        )
        .run(capture_stdout=True, capture_stderr=True, quiet=True)
    )
    return np.frombuffer(out, dtype=np.float32).copy()


def _merge_windows(windows: list[dict]) -> list[dict]:
    """Merge temporally overlapping/adjacent peak windows into one per block."""
    if not windows:
        return []
    merged = [windows[0].copy()]
    for w in windows[1:]:
        last = merged[-1]
        if w["start"] <= last["end"]:
            last["end"]          = max(last["end"],          w["end"])
            last["rms_db"]       = max(last["rms_db"],       w["rms_db"])
            last["above_mean_db"] = max(last["above_mean_db"], w["above_mean_db"])
        else:
            merged.append(w.copy())
    return merged


def _overlaps_any(peak: dict, seg_ranges: list[tuple[float, float]]) -> bool:
    """Return True if *peak* overlaps with at least one (start, end) range."""
    for seg_start, seg_end in seg_ranges:
        if peak["start"] < seg_end and peak["end"] > seg_start:
            return True
    return False
