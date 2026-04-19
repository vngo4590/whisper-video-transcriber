"""
transcription/ocr_extractor.py — On-screen text extraction from video frames.

SRP:  Samples video frames at a fixed interval, runs OCR on each, and merges
      consecutive frames that show the same text into a single time-span.
      No knowledge of Whisper, SRT formatting, UI, or file I/O.

OCP:  Swap _extract_frame_text to plug in a different OCR engine (e.g.
      pytesseract, PaddleOCR) without touching any caller.

DIP:  Callers (TranscriptionService) depend on the OcrEntry dataclass and the
      OcrExtractor.extract() interface — not on EasyOCR directly.
"""

import re
from dataclasses import dataclass

import cv2


@dataclass
class OcrEntry:
    """
    A contiguous time window during which a piece of on-screen text was visible.

    start / end are in seconds and follow the same convention as Whisper segments
    so they can be interleaved with speech entries by timestamp.
    """
    start: float   # first video frame where this text was detected (seconds)
    end:   float   # last detected frame + one sample interval (seconds)
    text:  str     # the extracted on-screen text


class OcrExtractor:
    """
    Extracts visible on-screen text from a video by sampling frames with OpenCV
    and running optical character recognition with EasyOCR.

    EasyOCR is lazy-initialised on first use because loading its neural network
    model takes a few seconds and should not slow down runs that don't need OCR.

    Typical use::

        entries = OcrExtractor().extract("recipe.mp4", sample_interval_s=1.0)

    Returns a list of OcrEntry objects sorted by start time.
    """

    # Discard OCR hits whose combined text is shorter than this many characters.
    # Very short hits (e.g. "2", "OK") are usually UI noise, not instructions.
    _MIN_TEXT_LENGTH = 3

    # EasyOCR confidence score in [0, 1].  Hits below this threshold are too
    # unreliable to include (blurry frames, partially visible text, etc.).
    _CONFIDENCE_THRESHOLD = 0.4

    def __init__(self) -> None:
        # Deferred so the heavy model load only happens when .extract() is called.
        self._reader = None

    def extract(
        self,
        video_path: str,
        sample_interval_s: float = 1.0,
    ) -> list[OcrEntry]:
        """
        Sample *video_path* once every *sample_interval_s* seconds and return
        all detected on-screen text as a list of OcrEntry time-spans.

        Consecutive frames that contain the same text (after normalisation) are
        merged into a single OcrEntry so that, for example, a recipe step that
        stays on screen for 8 seconds appears as one entry spanning 8 seconds
        rather than eight individual 1-second entries.

        Args:
            video_path:        Absolute path to the source video file.
            sample_interval_s: Gap between sampled frames in seconds (default 1 s).

        Returns:
            Chronologically sorted list of OcrEntry objects.
            Returns an empty list if the video cannot be opened or contains no text.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"OcrExtractor: cannot open video: {video_path}")

        fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # How many native frames to skip between samples.
        # e.g. 30 fps video with 1 s interval → jump every 30 frames.
        frame_step = max(1, int(round(fps * sample_interval_s)))

        # Collect (timestamp_seconds, ocr_text) for every sampled frame that
        # produced a non-empty OCR result.
        raw: list[tuple[float, str]] = []
        frame_idx = 0

        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_idx / fps
            text = self._extract_frame_text(frame)
            if text:
                raw.append((timestamp, text))

            frame_idx += frame_step

        cap.release()

        # Merge frames that show the same text into single time-span entries.
        return _merge_consecutive(raw, sample_interval_s)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _extract_frame_text(self, frame) -> str:
        """
        Run OCR on a single BGR frame and return the visible text as a string.

        Multiple text regions in the frame are joined with " | " so that a
        frame showing both "Step 1: Preheat oven" and "350°F" produces a
        single coherent string rather than two separate entries.

        Returns an empty string if no confident text is detected.
        """
        reader = self._get_reader()

        # readtext returns: list of ([bbox_points], text, confidence_score)
        results = reader.readtext(frame, detail=1)

        lines = []
        for _, text, confidence in results:
            text = text.strip()
            # Skip low-confidence hits and very short fragments (noise)
            if confidence >= self._CONFIDENCE_THRESHOLD and len(text) >= self._MIN_TEXT_LENGTH:
                lines.append(text)

        return " | ".join(lines) if lines else ""

    def _get_reader(self):
        """
        Lazy-init the EasyOCR reader.

        EasyOCR downloads a ~100 MB English model on the first run and caches it
        in ~/.EasyOCR/.  Subsequent runs load from the local cache (~2 s startup).
        gpu=False is safest for a desktop app; set to True for GPU-accelerated hosts.
        """
        if self._reader is None:
            # Deferred import: easyocr is only required when the feature is enabled.
            # This prevents an ImportError crash if the user has not installed it.
            import easyocr
            self._reader = easyocr.Reader(["en"], gpu=False)
        return self._reader


# ---------------------------------------------------------------------------
# Module-level helper — consecutive-frame deduplication
# ---------------------------------------------------------------------------

def _merge_consecutive(
    raw: list[tuple[float, str]],
    sample_interval_s: float,
) -> list[OcrEntry]:
    """
    Merge adjacent (timestamp, text) samples that show the same text.

    "Same text" is determined after normalisation: lowercase, collapse whitespace,
    strip punctuation.  This tolerates minor OCR variance between frames caused
    by compression artefacts or slight changes in rendering.

    The end time of each merged span is set to the timestamp of the last matching
    frame *plus one sample interval* so the span covers the full period during
    which the text was visible (not just the moment of the last sampled frame).
    """
    if not raw:
        return []

    def _normalise(t: str) -> str:
        """Lowercase, strip non-word chars, collapse whitespace."""
        t = t.lower()
        t = re.sub(r"[^\w\s|]", "", t)
        return re.sub(r"\s+", " ", t).strip()

    entries: list[OcrEntry] = []

    # Start tracking the first span
    cur_start   = raw[0][0]
    cur_text    = raw[0][1]
    cur_norm    = _normalise(cur_text)
    cur_last_ts = raw[0][0]   # timestamp of the most recent matching frame

    for ts, text in raw[1:]:
        norm = _normalise(text)

        if norm == cur_norm:
            # Same text seen again — push the span's end forward
            cur_last_ts = ts
        else:
            # Text changed — close the current span and start a new one
            entries.append(OcrEntry(
                start=cur_start,
                end=cur_last_ts + sample_interval_s,
                text=cur_text,
            ))
            cur_start   = ts
            cur_text    = text
            cur_norm    = norm
            cur_last_ts = ts

    # Close the final span
    entries.append(OcrEntry(
        start=cur_start,
        end=cur_last_ts + sample_interval_s,
        text=cur_text,
    ))

    return entries
