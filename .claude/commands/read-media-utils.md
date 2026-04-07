Read and explain `src/media_utils.py` — video/image utilities.

Steps:
1. Read the file at `src/media_utils.py`.
2. Describe `is_video()` and `extract_thumbnail()`: their inputs, outputs, and failure modes.
3. Explain the OpenCV → PIL → ImageTk pipeline used for thumbnail generation.
4. Note the SRP boundary: why this module knows nothing about Whisper, tkinter widgets, or file saving.
