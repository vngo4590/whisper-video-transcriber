"""
vision_analyzer.py — Claude vision API keyframe scorer.

SRP: Extracts keyframes from a video, sends them to Claude's vision API in
     one batched call, and returns high-interest time windows.  No audio
     analysis, no ffmpeg cutting, no UI.

Cost control:
  • Frames are capped at max_frames (default 30) per video.
  • Each frame is resized to ≤ max_width_px (default 640) before encoding.
  • A single API call covers all frames to minimise round-trips.
"""

import base64
import json
import re

import anthropic
import cv2
import numpy as np


_SCORE_PROMPT = (
    "Each image above is a keyframe sampled from a video. "
    "For every frame, respond with a JSON array where each element has:\n"
    '  "time"        : the timestamp in seconds (I will supply this),\n'
    '  "score"       : integer 0–10  (0 = static/empty, 10 = peak action/excitement),\n'
    '  "description" : one short phrase describing what makes it interesting (or "static").\n\n'
    "Return ONLY the JSON array — no markdown, no explanation."
)


def build_vision_windows(
    video_path: str,
    video_duration: float,
    api_key: str,
    claude_model: str,
    min_score: float = 6.0,
    max_frames: int = 30,
    min_interval_s: float = 5.0,
    max_width_px: int = 640,
) -> list[dict]:
    """
    Score keyframes with Claude vision and return high-interest windows.

    Args:
        video_path:     Path to the source video.
        video_duration: Total video length in seconds (for window clamping).
        api_key:        Anthropic API key.
        claude_model:   Claude model ID to use for scoring.
        min_score:      Frames with score < min_score are discarded.
        max_frames:     Hard cap on keyframes extracted (cost guard).
        min_interval_s: Minimum seconds between keyframes.
        max_width_px:   Frames wider than this are downscaled before encoding.

    Returns:
        List of {"start": float, "end": float, "score": float,
                 "description": str} sorted by start, overlaps merged.
    """
    if video_duration <= 0:
        return []

    interval_s = max(video_duration / max_frames, min_interval_s)
    keyframes   = _extract_keyframes(video_path, video_duration, interval_s, max_width_px)
    if not keyframes:
        return []

    scored = _score_with_claude(keyframes, api_key, claude_model)

    half = interval_s / 2.0
    windows: list[dict] = []
    for item in scored:
        if item.get("score", 0) < min_score:
            continue
        t = float(item["time"])
        windows.append({
            "start":       max(0.0, t - half),
            "end":         min(video_duration, t + half),
            "score":       float(item["score"]),
            "description": str(item.get("description", "")),
        })

    return _merge_windows(sorted(windows, key=lambda w: w["start"]))


# ---------------------------------------------------------------------------
# Private — keyframe extraction
# ---------------------------------------------------------------------------

def _extract_keyframes(
    video_path: str,
    video_duration: float,
    interval_s: float,
    max_width_px: int,
) -> list[dict]:
    """
    Seek to each interval timestamp and capture one frame.

    Returns list of {"time": float, "b64": str (JPEG base64)}.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"vision_analyzer: could not open video: {video_path}")

    frames: list[dict] = []
    t = interval_s / 2.0   # sample midpoints

    while t < video_duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = cap.read()
        if not ret:
            t += interval_s
            continue

        # Downscale if wider than max_width_px
        h, w = frame.shape[:2]
        if w > max_width_px:
            scale = max_width_px / w
            frame = cv2.resize(frame, (max_width_px, int(h * scale)))

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            b64 = base64.b64encode(buf).decode("utf-8")
            frames.append({"time": t, "b64": b64})

        t += interval_s

    cap.release()
    return frames


# ---------------------------------------------------------------------------
# Private — Claude vision call
# ---------------------------------------------------------------------------

def _score_with_claude(
    keyframes: list[dict],
    api_key: str,
    claude_model: str,
) -> list[dict]:
    """
    Send all keyframes in a single Claude API call and return parsed scores.

    Message structure:
        image_1  →  text "Time: Xs"
        image_2  →  text "Time: Xs"
        ...
        final text block with scoring instructions
    """
    content: list[dict] = []

    for kf in keyframes:
        content.append({
            "type": "image",
            "source": {
                "type":       "base64",
                "media_type": "image/jpeg",
                "data":       kf["b64"],
            },
        })
        content.append({
            "type": "text",
            "text": f"Time: {kf['time']:.1f}s",
        })

    content.append({"type": "text", "text": _SCORE_PROMPT})

    client   = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=claude_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )

    raw = ""
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            raw = text.strip()
            break

    if not raw:
        raise ValueError("vision_analyzer: Claude returned no text content.")

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"vision_analyzer: Claude returned invalid JSON.\n"
            f"Response: {raw[:400]}\nError: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Private — window merging
# ---------------------------------------------------------------------------

def _merge_windows(windows: list[dict]) -> list[dict]:
    """Merge temporally overlapping vision windows, keeping highest score."""
    if not windows:
        return []
    merged = [windows[0].copy()]
    for w in windows[1:]:
        last = merged[-1]
        if w["start"] <= last["end"]:
            last["end"] = max(last["end"], w["end"])
            if w["score"] > last["score"]:
                last["score"]       = w["score"]
                last["description"] = w["description"]
        else:
            merged.append(w.copy())
    return merged
