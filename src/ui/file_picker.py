"""
ui/file_picker.py — File selection widget with thumbnail preview.

SRP: Only responsible for letting the user choose a media file and
     displaying the filename / video thumbnail. No knowledge of
     transcription or clip generation.
GRASP Information Expert: FilePicker is the sole authority on which
     file the user has selected; it writes to the shared *selected_path*
     StringVar that other components read.
"""

import os
import tkinter as tk
from tkinter import filedialog

from src.media import utils as media_utils
from src.models import MEDIA_FILE_TYPES
import src.ui.theme as T
from src.ui.sidebar_widgets import card, hover, section_label


class FilePicker:
    """
    Browse button + filename label + optional video thumbnail.

    Args:
        parent: Container widget (the sidebar inner frame).
        selected_path: Shared StringVar written when the user picks a file.
    """

    def __init__(self, parent: tk.Widget, selected_path: tk.StringVar) -> None:
        self._selected_path = selected_path
        self._thumbnail_ref: object = None  # prevents PhotoImage GC
        self._build(parent)

    def set_busy(self, busy: bool) -> None:
        self._browse_button.config(state="disabled" if busy else "normal")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        section_label(parent, "FILE")
        file_card = card(parent)

        self._browse_button = tk.Button(
            file_card, text="Select File", command=self._browse,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_ACCENT, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=10, pady=6,
            highlightthickness=1, highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._browse_button.pack(fill="x")
        hover(self._browse_button, T.C_CARD, T.C_ACCENT_H)

        self._filename_label = tk.Label(
            file_card, text="No file selected", font=T.FONT_SMALL,
            bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2, anchor="w",
        )
        self._filename_label.pack(fill="x", pady=(8, 0))

        self._thumbnail = tk.Label(file_card, bg=T.C_CARD)
        self._thumbnail.pack(pady=(8, 0))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a video or audio file",
            filetypes=MEDIA_FILE_TYPES,
        )
        if not path:
            return
        self._selected_path.set(path)
        self._filename_label.config(text=os.path.basename(path), fg=T.C_TEXT_1)
        if media_utils.is_video(path):
            self._load_thumbnail(path)
        else:
            self._thumbnail.config(image="")

    def _load_thumbnail(self, video_path: str) -> None:
        try:
            img_tk = media_utils.extract_thumbnail(video_path)
            if img_tk:
                self._thumbnail_ref = img_tk
                self._thumbnail.config(image=img_tk)
        except Exception as exc:
            print(f"Thumbnail error: {exc}")
