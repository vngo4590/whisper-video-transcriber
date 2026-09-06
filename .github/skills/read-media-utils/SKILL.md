---
name: read-media-utils
description: Explain src/media/utils.py — video/image helpers and the OpenCV to PIL to ImageTk thumbnail pipeline. Use when working on thumbnails or media probing.
---

Read and explain `src/media/utils.py` — video/image utilities.

Steps:
1. Read the file at `src/media/utils.py`.
2. Describe every public function: its inputs, outputs, and failure modes.
3. Explain the OpenCV → PIL → ImageTk pipeline used for thumbnail generation.
4. Note the SRP boundary: why this module knows nothing about Whisper, tkinter widgets, or file saving.
