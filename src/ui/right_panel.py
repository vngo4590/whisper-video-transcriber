"""
ui/right_panel.py — Right output panel.

SRP: Only responsible for displaying transcript text.
     No knowledge of file I/O, Whisper, or control flow.
"""

import tkinter as tk
from tkinter import ttk

from src.ui.theme import (
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_TEXT_1,
    C_TEXT_2,
    C_TEXT_3,
    FONT_LABEL,
    FONT_MONO,
    FONT_SECTION,
    FONT_SMALL,
    PAD_H,
)


class RightPanel:
    """
    Right-side panel that shows the transcript in a scrollable text box.

    Args:
        parent: tkinter container widget.
    """

    def __init__(self, parent: tk.Widget):
        self._build(parent)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=C_BG)
        panel.pack(side="right", fill="both", expand=True)

        # ---- Header bar ----
        header = tk.Frame(panel, bg=C_BG)
        header.pack(fill="x", padx=PAD_H, pady=(16, 8))

        tk.Label(
            header,
            text="TRANSCRIPTION OUTPUT",
            font=FONT_SECTION,
            bg=C_BG,
            fg=C_TEXT_3,
        ).pack(side="left", anchor="w")

        # ---- Text area with custom scrollbar ----
        text_frame = tk.Frame(panel, bg=C_BORDER, padx=1, pady=1)
        text_frame.pack(fill="both", expand=True, padx=PAD_H, pady=(0, PAD_H))

        self._textbox = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=FONT_MONO,
            bg=C_CARD,
            fg=C_TEXT_1,
            insertbackground=C_TEXT_1,
            selectbackground=C_ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=14,
            spacing1=2,
            spacing3=2,
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self._textbox.yview,
            style="Output.Vertical.TScrollbar",
        )
        self._textbox.configure(yscrollcommand=scrollbar.set)

        self._textbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ---- Placeholder hint ----
        self._textbox.insert(
            tk.END,
            "Select a file and click Transcribe — output will appear here.",
        )
        self._textbox.config(fg=C_TEXT_3)

        # Clear placeholder on first real write
        self._has_content = False

    def set_text(self, text: str) -> None:
        """Replace the current content with *text*."""
        self._textbox.config(state="normal", fg=C_TEXT_1)
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, text)
        self._has_content = True
