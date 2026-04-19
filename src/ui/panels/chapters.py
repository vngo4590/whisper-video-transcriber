"""
ui/panels/chapters.py — Chapters panel: displays AI-generated chapter markers.

SRP: Only responsible for rendering chapter data from generate_chapters().
     No LLM calls, no ffmpeg, no file I/O.
"""

import tkinter as tk
from tkinter import ttk

import src.ui.theme as T

_PLACEHOLDER = "Generate chapters — topic markers will appear here after transcription."


def _fmt_time(secs: float) -> str:
    secs = max(0.0, float(secs))
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class ChaptersPanel:
    """
    Scrollable panel showing a card for each AI-generated chapter.

    Public API
    ----------
    set_chapters(chapters)  — populate with a list of chapter dicts
    set_stage(text)         — update the progress label
    show_loading(bool)      — start / stop the progress bar
    reset()                 — clear all cards and restore placeholder
    """

    def __init__(self, parent: tk.Widget):
        self._cards: list[tk.Frame] = []
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_chapters(self, chapters: list[dict]) -> None:
        """Replace current content with chapter cards."""
        self.reset()
        self._empty_label.pack_forget()
        for ch in chapters:
            card = self._build_card(self._inner, ch)
            card.pack(fill="x", padx=T.PAD_H, pady=(0, 10))
            self._cards.append(card)
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def set_stage(self, text: str) -> None:
        self._stage_label.config(text=text)

    def show_loading(self, visible: bool) -> None:
        if visible:
            self._progress_bar.start(12)
        else:
            self._progress_bar.stop()
            self._stage_label.config(text="")

    def reset(self) -> None:
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

        header = tk.Frame(panel, bg=T.C_BG)
        header.pack(fill="x", padx=T.PAD_H, pady=(16, 4))
        tk.Label(header, text="CHAPTERS", font=T.FONT_SECTION,
                 bg=T.C_BG, fg=T.C_TEXT_3).pack(side="left", anchor="w")

        prog_frame = tk.Frame(panel, bg=T.C_BG)
        prog_frame.pack(fill="x", padx=T.PAD_H, pady=(0, 8))
        self._stage_label = tk.Label(prog_frame, text="", font=T.FONT_SMALL,
                                      bg=T.C_BG, fg=T.C_WARN)
        self._stage_label.pack(anchor="w")
        self._progress_bar = ttk.Progressbar(prog_frame, mode="indeterminate",
                                              style="Accent.Horizontal.TProgressbar")
        self._progress_bar.pack(fill="x", pady=(2, 0))

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

        self._empty_label = tk.Label(
            self._inner, text=_PLACEHOLDER,
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_3,
        )
        self._empty_label.pack(expand=True, pady=40)

    def _build_card(self, parent: tk.Widget, ch: dict) -> tk.Frame:
        card = tk.Frame(parent, bg=T.C_CARD)

        top = tk.Frame(card, bg=T.C_CARD)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text=f" CH {ch.get('chapter', '?')} ",
                 font=("Segoe UI", 7, "bold"),
                 bg=T.C_ACCENT, fg="#ffffff").pack(side="left", padx=(0, 8))

        tk.Label(top, text=str(ch.get("title", "Untitled")),
                 font=("Segoe UI", 11, "bold"),
                 bg=T.C_CARD, fg=T.C_TEXT_1,
                 wraplength=380, anchor="w", justify="left").pack(
                     side="left", fill="x", expand=True)

        ts_frame = tk.Frame(card, bg=T.C_CARD)
        ts_frame.pack(fill="x", padx=12, pady=(0, 6))
        start = float(ch.get("start_time", 0))
        end   = float(ch.get("end_time", 0))
        dur   = max(0.0, end - start)
        mins, srem = divmod(int(dur), 60)
        dur_text = f"{mins}m {srem}s" if mins else f"{srem}s"
        tk.Label(ts_frame, text=f"{_fmt_time(start)} → {_fmt_time(end)}",
                 font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_ACCENT).pack(side="left")
        tk.Label(ts_frame, text=f"  ·  {dur_text}",
                 font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3).pack(side="left")

        summary = str(ch.get("summary", ""))
        if summary:
            tk.Label(card, text=summary, font=T.FONT_SMALL,
                     bg=T.C_CARD, fg=T.C_TEXT_2,
                     wraplength=440, anchor="w", justify="left",
                     padx=12).pack(fill="x", pady=(0, 6))

        key_points = ch.get("key_points", [])
        if key_points:
            kp_frame = tk.Frame(card, bg=T.C_CARD, padx=12)
            kp_frame.pack(fill="x", pady=(0, 10))
            for pt in key_points[:4]:
                tk.Label(kp_frame, text=f"• {pt}", font=T.FONT_SMALL,
                         bg=T.C_CARD, fg=T.C_TEXT_2,
                         anchor="w", justify="left", wraplength=430).pack(anchor="w")

        tk.Frame(card, bg=T.C_BORDER, height=1).pack(fill="x")
        return card
