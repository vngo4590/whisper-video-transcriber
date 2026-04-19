"""
ui/right_panel.py — Right output panel.

SRP: Responsible for displaying transcript text, allowing in-place edits,
     saving edits back to disk, showing filler-word stats, and triggering
     chapter generation.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

from src.models import FILLER_WORDS
from src.ui.theme import (
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_ERROR,
    C_TEXT_1,
    C_TEXT_2,
    C_TEXT_3,
    C_WARN,
    FONT_LABEL,
    FONT_MONO,
    FONT_SECTION,
    FONT_SMALL,
    PAD_H,
)


def _count_fillers(text: str) -> dict[str, int]:
    """Count whole-word occurrences of every filler word in *text*."""
    text_lower = text.lower()
    counts: dict[str, int] = {}
    for filler in sorted(FILLER_WORDS, key=len, reverse=True):
        pattern = r"(?<!\w)" + re.escape(filler) + r"(?!\w)"
        n = len(re.findall(pattern, text_lower))
        if n:
            counts[filler] = n
    return counts


class RightPanel:
    """
    Right-side panel: scrollable, editable transcript text box.

    Args:
        parent:               tkinter container widget.
        on_generate_chapters: Optional callback ``(transcript_text: str) → None``
                              fired when the user clicks "Generate Chapters".
    """

    def __init__(self, parent: tk.Widget, on_generate_chapters=None) -> None:
        self._output_path: str = ""
        self._on_generate_chapters = on_generate_chapters
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_text(self, text: str, output_path: str = "") -> None:
        """Replace the current content with *text* and remember *output_path*."""
        self._output_path = output_path
        self._textbox.config(state="normal", fg=C_TEXT_1)
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, text)
        self._save_btn.config(state="normal")
        if self._on_generate_chapters:
            self._chapters_btn.config(state="normal")
        self._show_filler_stats(text)

    def get_text(self) -> str:
        return self._textbox.get("1.0", tk.END).rstrip("\n")

    # ------------------------------------------------------------------
    # Private — layout
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

        _btn_kw = dict(
            font=FONT_SMALL, relief="flat", bd=0, padx=10, pady=4,
            bg=C_BORDER, fg=C_TEXT_2,
            activebackground=C_ACCENT, activeforeground="#ffffff",
            state="disabled",
        )

        self._save_btn = tk.Button(
            header, text="Save edits",
            command=self._save_edits, cursor="hand2", **_btn_kw,
        )
        self._save_btn.pack(side="right", padx=(4, 0))

        if self._on_generate_chapters:
            self._chapters_btn = tk.Button(
                header, text="Generate Chapters",
                command=self._request_chapters, cursor="hand2", **_btn_kw,
            )
            self._chapters_btn.pack(side="right", padx=(4, 0))

        # ---- Filler stats bar (hidden until content is set) ----
        self._stats_bar = tk.Frame(panel, bg=C_BG)
        self._stats_label = tk.Label(
            self._stats_bar, text="", font=FONT_SMALL, bg=C_BG, fg=C_WARN,
        )
        self._stats_label.pack(anchor="w", padx=PAD_H)

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

        self._textbox.insert(
            tk.END,
            "Select a file and click Transcribe — output will appear here.",
        )
        self._textbox.config(fg=C_TEXT_3)

    # ------------------------------------------------------------------
    # Private — actions
    # ------------------------------------------------------------------

    def _save_edits(self) -> None:
        if not self._output_path:
            messagebox.showwarning(
                "No output path",
                "The save location is unknown. Re-run Transcribe to generate an output file first.",
            )
            return
        text = self.get_text()
        try:
            with open(self._output_path, "w", encoding="utf-8") as f:
                f.write(text)
            orig = self._save_btn.cget("text")
            self._save_btn.config(text="Saved!")
            self._save_btn.after(1500, lambda: self._save_btn.config(text=orig))
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))

    def _request_chapters(self) -> None:
        if self._on_generate_chapters:
            self._on_generate_chapters(self.get_text())

    def _show_filler_stats(self, text: str) -> None:
        counts = _count_fillers(text)
        if not counts:
            self._stats_bar.pack_forget()
            return
        total = sum(counts.values())
        top = sorted(counts.items(), key=lambda x: -x[1])[:5]
        detail = "  ".join(f"{w} ×{n}" for w, n in top)
        self._stats_label.config(
            text=f"Fillers: {total} total    {detail}",
        )
        self._stats_bar.pack(fill="x", pady=(0, 6))
