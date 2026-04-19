"""
ui/file_picker.py — File selection widget with thumbnail preview.

SRP: Only responsible for letting the user choose a media file and
     displaying the filename / video thumbnail. No knowledge of
     transcription or clip generation.
GRASP Information Expert: FilePicker is the sole authority on which
     file the user has selected; it writes to the shared *selected_path*
     StringVar that other components read.

New in this version:
  • Recent files — up to 8 previously-used files listed as clickable rows.
  • Drag-and-drop — the file card accepts OS file drops via tkinterdnd2
    when that package is available; degrades gracefully when absent.
"""

import os
import tkinter as tk
from tkinter import filedialog

from src.config import settings
from src.media import utils as media_utils
from src.models import MEDIA_FILE_TYPES
import src.ui.theme as T
from src.ui.sidebar.widgets import card, hover, section_label

try:
    from tkinterdnd2 import DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

_SUPPORTED_EXTENSIONS = {
    ext.lstrip("*")
    for _, patterns in MEDIA_FILE_TYPES[:-1]
    for ext in patterns.split()
}


class FilePicker:
    """
    Browse button + filename label + optional video thumbnail + recent files list.

    Args:
        parent: Container widget (the sidebar inner frame).
        selected_path: Shared StringVar written when the user picks a file.
    """

    def __init__(self, parent: tk.Widget, selected_path: tk.StringVar) -> None:
        self._selected_path = selected_path
        self._thumbnail_ref: object = None
        self._recent_rows: list[tk.Frame] = []
        self._build(parent)

    def set_busy(self, busy: bool) -> None:
        self._browse_button.config(state="disabled" if busy else "normal")

    # ------------------------------------------------------------------
    # Private — build
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        section_label(parent, "FILE")
        file_card = card(parent)

        # Drop-zone hint only visible when DnD is available
        if _DND_AVAILABLE:
            drop_hint = tk.Label(
                file_card,
                text="Drop a file here or",
                font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3,
            )
            drop_hint.pack(anchor="w", pady=(0, 4))

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

        # Register the entire card as a drop target
        if _DND_AVAILABLE:
            try:
                file_card.drop_target_register(DND_FILES)
                file_card.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # Recent files section
        self._recent_frame_outer = tk.Frame(parent, bg=T.C_SIDEBAR)
        self._recent_frame_outer.pack(fill="x")
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        """Re-build the recent files list from settings."""
        for w in self._recent_frame_outer.winfo_children():
            w.destroy()
        self._recent_rows.clear()

        recent = settings.get_recent_files()
        if not recent:
            return

        section_label(self._recent_frame_outer, "RECENT FILES")
        recent_card = tk.Frame(
            self._recent_frame_outer, bg=T.C_CARD, padx=T.PAD_CARD, pady=4,
        )
        recent_card.pack(fill="x", padx=T.PAD_H)

        for path in recent[:6]:
            row = tk.Frame(recent_card, bg=T.C_CARD, cursor="hand2")
            row.pack(fill="x", pady=2)
            lbl = tk.Label(
                row,
                text=os.path.basename(path),
                font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_2,
                anchor="w",
                wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2 - 4,
            )
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda _e, p=path: self._set_file(p))
            lbl.bind("<Enter>", lambda _e, l=lbl: l.config(fg=T.C_TEXT_1))
            lbl.bind("<Leave>", lambda _e, l=lbl: l.config(fg=T.C_TEXT_2))
            self._recent_rows.append(row)

    # ------------------------------------------------------------------
    # Private — file handling
    # ------------------------------------------------------------------

    def _set_file(self, path: str) -> None:
        """Select *path*, update UI, persist to recent files."""
        if not os.path.exists(path):
            self._refresh_recent()
            return
        self._selected_path.set(path)
        self._filename_label.config(text=os.path.basename(path), fg=T.C_TEXT_1)
        if media_utils.is_video(path):
            self._load_thumbnail(path)
        else:
            self._thumbnail.config(image="")
        settings.add_recent_file(path)
        self._refresh_recent()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a video or audio file",
            filetypes=MEDIA_FILE_TYPES,
        )
        if not path:
            return
        self._set_file(path)

    def _on_drop(self, event) -> None:
        """Handle OS file-drop event from tkinterdnd2."""
        raw = event.data.strip()
        # tkinterdnd2 may wrap paths in braces on Windows
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.split("} {")[0]   # take first file if multiple dropped
        ext = os.path.splitext(path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return
        self._set_file(path)

    def _load_thumbnail(self, video_path: str) -> None:
        try:
            img_tk = media_utils.extract_thumbnail(video_path)
            if img_tk:
                self._thumbnail_ref = img_tk
                self._thumbnail.config(image=img_tk)
        except Exception:
            pass
