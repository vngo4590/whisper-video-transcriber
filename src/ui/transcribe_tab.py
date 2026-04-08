"""
ui/transcribe_tab.py — Transcribe mode tab panel.

SRP: Owns all transcription settings (export format, options) and the
     Transcribe action. Has no knowledge of clip generation.
GRASP Information Expert: sole authority on export format, word limit, and
     translation preference. Reads shared *selected_path* / *model_var*
     supplied by LeftPanel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.models import DEFAULT_EXPORT_FORMAT, DEFAULT_MAX_WORDS_PER_LINE, ExportFormat
import src.ui.theme as T
from src.ui.sidebar_widgets import card, hover, radiobutton, section_label


class TranscribeTab:
    """
    Settings panel for the Transcribe mode tab.

    Args:
        parent: The tab frame inside the left-panel Notebook.
        selected_path: Shared StringVar holding the chosen file path.
        model_var: Shared StringVar holding the chosen Whisper model name.
        on_transcribe: Callback — ``on_transcribe(path, model_name,
                       export_format, do_translate, max_words_per_line)``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        selected_path: tk.StringVar,
        model_var: tk.StringVar,
        on_transcribe,
    ) -> None:
        self._selected_path = selected_path
        self._model_var = model_var
        self._on_transcribe = on_transcribe

        self._export_format_var = tk.StringVar(value=DEFAULT_EXPORT_FORMAT.value)
        self._max_words_var = tk.IntVar(value=DEFAULT_MAX_WORDS_PER_LINE)
        self._translate_var = tk.BooleanVar(value=False)

        self._build(parent)

    def set_busy(self, busy: bool) -> None:
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"
        self._radio_srt.config(state=btn)
        self._radio_plain.config(state=btn)
        self._max_words_spinbox.config(state=btn)
        self._translate_checkbox.config(state=btn)
        self._confirm_button.config(
            state=btn,
            bg=T.C_ACCENT_D if busy else T.C_ACCENT,
            cursor="" if busy else "hand2",
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        # EXPORT FORMAT
        section_label(parent, "EXPORT FORMAT")
        fmt_card = card(parent)

        self._radio_srt = radiobutton(fmt_card, "SRT  (with timestamps)", ExportFormat.SRT.value, self._export_format_var)
        self._radio_srt.pack(anchor="w")

        self._radio_plain = radiobutton(fmt_card, "Plain text", ExportFormat.PLAIN_TEXT.value, self._export_format_var)
        self._radio_plain.pack(anchor="w", pady=(4, 10))

        words_row = tk.Frame(fmt_card, bg=T.C_CARD)
        words_row.pack(fill="x")
        tk.Label(words_row, text="Max words / subtitle", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._max_words_spinbox = tk.Spinbox(
            words_row, from_=1, to=20, textvariable=self._max_words_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1, highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._max_words_spinbox.pack(side="right")

        # OPTIONS
        section_label(parent, "OPTIONS")
        opt_card = card(parent)
        self._translate_checkbox = tk.Checkbutton(
            opt_card, text="Translate to English", variable=self._translate_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT, relief="flat", bd=0, cursor="hand2",
        )
        self._translate_checkbox.pack(anchor="w")

        # Transcribe button
        btn_frame = tk.Frame(parent, bg=T.C_SIDEBAR)
        btn_frame.pack(fill="x", padx=T.PAD_H, pady=(16, 10))
        self._confirm_button = tk.Button(
            btn_frame, text="Transcribe", command=self._handle_submit,
            font=T.FONT_BUTTON, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=10,
        )
        self._confirm_button.pack(fill="x")
        hover(self._confirm_button, T.C_ACCENT, T.C_ACCENT_H)

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a file first.")
            return
        self._on_transcribe(
            path,
            self._model_var.get(),
            ExportFormat(self._export_format_var.get()),
            self._translate_var.get(),
            self._max_words_var.get(),
        )
