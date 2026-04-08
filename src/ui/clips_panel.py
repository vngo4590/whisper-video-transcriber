"""
ui/clips_panel.py — Clips tab: displays generated clip cards with progress.

SRP: Only responsible for displaying ClipResult data and progress state.
     No LLM, no ffmpeg, no transcription logic.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from src.models import ClipResult
import src.ui.theme as T

_CATEGORY_COLORS = {
    "humor":       "#f59e0b",
    "insight":     "#6c63ff",
    "emotional":   "#ec4899",
    "shocking":    "#ef4444",
    "educational": "#10b981",
}


class ClipsPanel:
    """
    Scrollable panel that shows a card for each generated clip.

    Public API
    ----------
    add_clip(clip)      — append a single card (called as each clip finishes)
    set_stage(text)     — update the progress label
    show_loading(True)  — start progress bar
    reset()             — clear all cards for a new run
    """

    def __init__(self, parent: tk.Widget):
        self._cards: list[tk.Frame] = []
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_clip(self, clip: ClipResult) -> None:
        """Append a card for *clip* to the scrollable list."""
        self._empty_label.pack_forget()
        card = self._build_card(self._inner, clip)
        card.pack(fill="x", padx=T.PAD_H, pady=(0, 10))
        self._cards.append(card)
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        # Scroll to bottom so the newest card is visible
        self._canvas.yview_moveto(1.0)

    def set_stage(self, text: str) -> None:
        self._stage_label.config(text=text)

    def show_loading(self, visible: bool) -> None:
        if visible:
            self._progress_bar.start(12)
        else:
            self._progress_bar.stop()
            self._stage_label.config(text="")

    def reset(self) -> None:
        """Remove all cards and restore the empty-state label."""
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        self._empty_label.pack(expand=True)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=T.C_BG)
        panel.pack(fill="both", expand=True)

        # ── Header bar ────────────────────────────────────────────────
        header = tk.Frame(panel, bg=T.C_BG)
        header.pack(fill="x", padx=T.PAD_H, pady=(16, 4))
        tk.Label(header, text="GENERATED CLIPS", font=T.FONT_SECTION,
                 bg=T.C_BG, fg=T.C_TEXT_3).pack(side="left", anchor="w")

        # ── Progress strip ────────────────────────────────────────────
        prog_frame = tk.Frame(panel, bg=T.C_BG)
        prog_frame.pack(fill="x", padx=T.PAD_H, pady=(0, 8))

        self._stage_label = tk.Label(prog_frame, text="", font=T.FONT_SMALL,
                                      bg=T.C_BG, fg=T.C_WARN)
        self._stage_label.pack(anchor="w")

        self._progress_bar = ttk.Progressbar(prog_frame, mode="indeterminate",
                                              style="Accent.Horizontal.TProgressbar")
        self._progress_bar.pack(fill="x", pady=(2, 0))

        # ── Scrollable card list ──────────────────────────────────────
        list_frame = tk.Frame(panel, bg=T.C_BG)
        list_frame.pack(fill="both", expand=True, padx=1, pady=(0, T.PAD_H))

        self._canvas = tk.Canvas(list_frame, bg=T.C_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self._canvas.yview,
                                   style="Output.Vertical.TScrollbar")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=T.C_BG)
        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.bind_all(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

        # Empty-state hint
        self._empty_label = tk.Label(
            self._inner,
            text="Clips will appear here after generation.",
            font=T.FONT_LABEL,
            bg=T.C_BG,
            fg=T.C_TEXT_3,
        )
        self._empty_label.pack(expand=True, pady=40)

    def _build_card(self, parent: tk.Widget, clip: ClipResult) -> tk.Frame:
        """Build a single clip card widget."""
        card = tk.Frame(parent, bg=T.C_CARD)

        # ── Top row: title + category badge ──────────────────────────
        top = tk.Frame(card, bg=T.C_CARD)
        top.pack(fill="x", padx=12, pady=(12, 4))

        category_color = _CATEGORY_COLORS.get(clip.category.lower(), T.C_ACCENT)

        badge = tk.Label(top, text=f" {clip.category.upper()} ",
                         font=("Segoe UI", 7, "bold"),
                         bg=category_color, fg="#ffffff")
        badge.pack(side="right", padx=(4, 0))

        tk.Label(top, text=clip.title, font=("Segoe UI", 11, "bold"),
                 bg=T.C_CARD, fg=T.C_TEXT_1,
                 wraplength=380, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

        # ── Timestamps ────────────────────────────────────────────────
        ts_frame = tk.Frame(card, bg=T.C_CARD)
        ts_frame.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(ts_frame, text=clip.timestamp_label,
                 font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_ACCENT).pack(side="left")
        mins = int(clip.duration) // 60
        secs = int(clip.duration) % 60
        dur_text = f"{mins}m {secs}s" if mins else f"{secs}s"
        tk.Label(ts_frame, text=f"  ·  {dur_text}",
                 font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3).pack(side="left")
        if len(clip.segments) > 1:
            tk.Label(ts_frame, text=f"  ·  {len(clip.segments)} cuts",
                     font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3).pack(side="left")

        # ── Hook ──────────────────────────────────────────────────────
        if clip.hook:
            hook_row = tk.Frame(card, bg=T.C_CARD)
            hook_row.pack(fill="x", padx=12, pady=(0, 4))
            tk.Label(hook_row, text="HOOK", font=T.FONT_SECTION,
                     bg=T.C_CARD, fg=T.C_TEXT_3).pack(side="left", padx=(0, 6))
            tk.Label(hook_row, text=clip.hook, font=T.FONT_SMALL,
                     bg=T.C_CARD, fg=T.C_TEXT_2,
                     wraplength=400, anchor="w", justify="left").pack(side="left", fill="x")

        # ── Reason ────────────────────────────────────────────────────
        if clip.reason:
            tk.Label(card, text=clip.reason, font=T.FONT_SMALL,
                     bg=T.C_CARD, fg=T.C_TEXT_2,
                     wraplength=440, anchor="w", justify="left",
                     padx=12).pack(fill="x", pady=(0, 8))

        # ── Divider + Open folder button ──────────────────────────────
        tk.Frame(card, bg=T.C_BORDER, height=1).pack(fill="x")

        btn_row = tk.Frame(card, bg=T.C_CARD)
        btn_row.pack(fill="x", padx=12, pady=8)

        if clip.output_path:
            open_btn = tk.Button(
                btn_row,
                text="Open folder",
                command=lambda p=clip.output_path: _open_folder(p),
                font=T.FONT_SMALL,
                bg=T.C_BORDER,
                fg=T.C_TEXT_2,
                activebackground=T.C_ACCENT,
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=10,
                pady=4,
            )
            open_btn.pack(side="left")

        return card


def _open_folder(file_path: str) -> None:
    """Open the folder containing *file_path* in the OS file explorer."""
    folder = os.path.dirname(file_path)
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])
