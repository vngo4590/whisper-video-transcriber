"""
media_utils.py — Video/image utilities.

SRP: Only responsible for media-specific operations (thumbnail extraction,
     file-type detection). No transcription or UI logic here.
"""

import os

import cv2
from PIL import Image, ImageTk

from src.models import SUPPORTED_VIDEO_EXTENSIONS, THUMBNAIL_SIZE


def is_video(file_path: str) -> bool:
    """Return True when *file_path* has a recognised video extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_VIDEO_EXTENSIONS


def extract_thumbnail(video_path: str, size: tuple = THUMBNAIL_SIZE):
    """
    Capture the first frame of *video_path* and return a PhotoImage.

    Args:
        video_path: Absolute path to the video file.
        size: ``(width, height)`` thumbnail bounding box.

    Returns:
        ``ImageTk.PhotoImage`` on success, ``None`` if the frame cannot
        be read (e.g. corrupted file or unsupported codec).
    """
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    img.thumbnail(size)
    return ImageTk.PhotoImage(img)
