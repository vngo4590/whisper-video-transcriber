"""
ui/content_plan_panel.py — Content Plan tab: displays the AI-generated edit guide.

SRP: Only responsible for rendering the formatted plan text and providing
     Copy / Save actions. No LLM, no ffmpeg, no transcription logic.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import src.ui.theme as T

_PLACEHOLDER = "Generate a content plan — your edit guide will appear here."


class ContentPlanPanel:
    """
    Scrollable output panel for the AI-generated content plan.

    Public API
    ----------
    set_text(text)      — populate the panel with the formatted plan
    set_stage(text)     — update the progress label
    show_loading(bool)  — start / stop the progress bar
    reset()             — clear content and restore placeholder
    """

    def __init__(self, parent: tk.Widget):
        self._current_text = ""
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Replace the current content with the formatted plan."""
        self._current_text = text
        self._textbox.config(state="normal", fg=T.C_TEXT_1)
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, text)
        self._textbox.config(state="disabled")
        self._copy_btn.config(state="normal")
        self._save_txt_btn.config(state="normal")
        self._save_md_btn.config(state="normal")

    def set_stage(self, text: str) -> None:
        self._stage_label.config(text=text)

    def show_loading(self, visible: bool) -> None:
        if visible:
            self._progress_bar.start(12)
        else:
            self._progress_bar.stop()
            self._stage_label.config(text="")

    def reset(self) -> None:
        """Clear all cards and restore the empty-state placeholder."""
        self._current_text = ""
        self._textbox.config(state="normal", fg=T.C_TEXT_3)
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, _PLACEHOLDER)
        self._textbox.config(state="disabled")
        self._copy_btn.config(state="disabled")
        self._save_txt_btn.config(state="disabled")
        self._save_md_btn.config(state="disabled")
        self._stage_label.config(text="")

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=T.C_BG)
        panel.pack(fill="both", expand=True)

        # ── Header + action buttons ────────────────────────────────────
        header = tk.Frame(panel, bg=T.C_BG)
        header.pack(fill="x", padx=T.PAD_H, pady=(16, 6))

        tk.Label(
            header, text="CONTENT PLAN", font=T.FONT_SECTION,
            bg=T.C_BG, fg=T.C_TEXT_3,
        ).pack(side="left", anchor="w")

        # Action buttons — right-aligned in the header row
        _btn = dict(
            font=T.FONT_SMALL, relief="flat", bd=0,
            padx=10, pady=4,
            bg=T.C_BORDER, fg=T.C_TEXT_2,
            activebackground=T.C_ACCENT, activeforeground="#ffffff",
            state="disabled",
        )
        self._save_md_btn = tk.Button(
            header, text="Save .md",
            command=lambda: self._save("md"), **_btn,
        )
        self._save_md_btn.pack(side="right", padx=(4, 0))

        self._save_txt_btn = tk.Button(
            header, text="Save .txt",
            command=lambda: self._save("txt"), **_btn,
        )
        self._save_txt_btn.pack(side="right", padx=(4, 0))

        self._copy_btn = tk.Button(
            header, text="Copy",
            command=self._copy, **_btn,
        )
        self._copy_btn.pack(side="right", padx=(4, 0))

        # ── Progress strip ─────────────────────────────────────────────
        prog_frame = tk.Frame(panel, bg=T.C_BG)
        prog_frame.pack(fill="x", padx=T.PAD_H, pady=(0, 6))

        self._stage_label = tk.Label(
            prog_frame, text="", font=T.FONT_SMALL, bg=T.C_BG, fg=T.C_WARN,
        )
        self._stage_label.pack(anchor="w")

        self._progress_bar = ttk.Progressbar(
            prog_frame, mode="indeterminate",
            style="Accent.Horizontal.TProgressbar",
        )
        self._progress_bar.pack(fill="x", pady=(2, 0))

        # ── Scrollable monospace text area ─────────────────────────────
        text_frame = tk.Frame(panel, bg=T.C_BORDER, padx=1, pady=1)
        text_frame.pack(fill="both", expand=True, padx=T.PAD_H, pady=(0, T.PAD_H))

        self._textbox = tk.Text(
            text_frame,
            wrap=tk.NONE,          # no wrapping — plan uses deliberate line breaks
            font=T.FONT_MONO,
            bg=T.C_CARD,
            fg=T.C_TEXT_3,
            insertbackground=T.C_TEXT_1,
            selectbackground=T.C_ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=14,
            spacing1=1,
            spacing3=1,
            state="disabled",
        )

        v_scrollbar = ttk.Scrollbar(
            text_frame, orient="vertical",
            command=self._textbox.yview,
            style="Output.Vertical.TScrollbar",
        )
        h_scrollbar = ttk.Scrollbar(
            text_frame, orient="horizontal",
            command=self._textbox.xview,
            style="Output.Vertical.TScrollbar",
        )
        self._textbox.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set,
        )

        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        self._textbox.pack(side="left", fill="both", expand=True)

        # Placeholder
        self._textbox.config(state="normal")
        self._textbox.insert(tk.END, _PLACEHOLDER)
        self._textbox.config(state="disabled")

    # ------------------------------------------------------------------
    # Private — actions
    # ------------------------------------------------------------------

    def _copy(self) -> None:
        if not self._current_text:
            return
        root = self._textbox.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(self._current_text)
        orig = self._copy_btn.cget("text")
        self._copy_btn.config(text="Copied!")
        self._textbox.after(1500, lambda: self._copy_btn.config(text=orig))

    def _save(self, ext: str) -> None:
        if not self._current_text:
            return
        filetypes = (
            [("Text file", "*.txt")] if ext == "txt"
            else [("Markdown file", "*.md")]
        )
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=filetypes,
            title="Save content plan",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._current_text)
        messagebox.showinfo("Saved", f"Content plan saved to:\n{path}")
