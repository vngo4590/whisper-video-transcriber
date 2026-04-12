"""
visual_analyzer.py — Motion-burst detection via OpenCV frame differencing.

SRP: Only responsible for measuring inter-frame pixel change in a video and
     returning high-motion windows.  No audio, no LLM, no UI.

Works on any video, including silent / no-speech content.
"""

import numpy as np
import cv2


def build_motion_windows(
    video_path: str,
    sample_fps: float = 4.0,
    window_s: float = 2.0,
    hop_s: float = 0.5,
    threshold_multiplier: float = 2.0,
    analysis_width_px: int = 320,
) -> list[dict]:
    """
    Slide a window over per-frame motion scores and return high-motion bursts.

    Frames are sampled at *sample_fps* (default 4 fps) and downscaled to
    *analysis_width_px* wide before computing the diff, keeping CPU usage low.

    Args:
        video_path:           Path to the source video file.
        sample_fps:           How many frames per second to analyse.
        window_s:             Sliding window length in seconds.
        hop_s:                Window hop in seconds.
        threshold_multiplier: A window must be this many times the overall
                              mean motion score to qualify as a burst.
        analysis_width_px:    Frames are resized to this width before diffing.

    Returns:
        List of {"start": float, "end": float, "motion_score": float,
                 "above_mean": float} sorted by start, with overlapping
        windows merged into contiguous bursts.
    """
    scores = _sample_frame_scores(video_path, sample_fps, analysis_width_px)
    if not scores:
        return []

    timestamps = [t for t, _ in scores]
    values     = np.array([s for _, s in scores], dtype=np.float32)

    duration = timestamps[-1] if timestamps else 0.0
    if duration < window_s:
        return []

    # Slide window over the sampled scores
    raw_windows: list[dict] = []
    t = 0.0
    while t + window_s <= duration + hop_s:
        win_start = t
        win_end   = t + window_s
        in_window = [
            values[i]
            for i, ts in enumerate(timestamps)
            if win_start <= ts < win_end
        ]
        if in_window:
            score = float(np.mean(in_window))
            raw_windows.append({"start": win_start, "end": win_end, "motion_score": score})
        t += hop_s

    if not raw_windows:
        return []

    mean_score = float(np.mean([w["motion_score"] for w in raw_windows]))
    if mean_score == 0:
        return []

    peaks = [
        {
            "start":        w["start"],
            "end":          w["end"],
            "motion_score": w["motion_score"],
            "above_mean":   round(w["motion_score"] / mean_score, 2),
        }
        for w in raw_windows
        if w["motion_score"] >= mean_score * threshold_multiplier
    ]

    return _merge_windows(peaks)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _sample_frame_scores(
    video_path: str,
    sample_fps: float,
    analysis_width_px: int,
) -> list[tuple[float, float]]:
    """
    Return a list of (timestamp_sec, motion_score) by comparing consecutive
    sampled grayscale frames.  Motion score = mean pixel absolute difference.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"visual_analyzer: could not open video: {video_path}")

    native_fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(1, int(round(native_fps / sample_fps)))

    scores: list[tuple[float, float]] = []
    prev_gray = None
    frame_idx = 0

    while frame_idx < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # Downscale for speed then convert to grayscale
        h, w = frame.shape[:2]
        if w > analysis_width_px:
            scale = analysis_width_px / w
            frame = cv2.resize(frame, (analysis_width_px, int(h * scale)))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None and prev_gray.shape == gray.shape:
            diff  = cv2.absdiff(gray, prev_gray)
            score = float(np.mean(diff))
            timestamp = frame_idx / native_fps
            scores.append((timestamp, score))

        prev_gray  = gray
        frame_idx += frame_interval

    cap.release()
    return scores


def _merge_windows(windows: list[dict]) -> list[dict]:
    """Merge temporally overlapping / adjacent motion windows."""
    if not windows:
        return []
    merged = [windows[0].copy()]
    for w in windows[1:]:
        last = merged[-1]
        if w["start"] <= last["end"]:
            last["end"]          = max(last["end"],          w["end"])
            last["motion_score"] = max(last["motion_score"], w["motion_score"])
            last["above_mean"]   = max(last["above_mean"],   w["above_mean"])
        else:
            merged.append(w.copy())
    return merged
