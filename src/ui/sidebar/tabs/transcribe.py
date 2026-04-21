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

from src.config import settings
from src.models import DEFAULT_EXPORT_FORMAT, DEFAULT_MAX_WORDS_PER_LINE, ExportFormat
from src.transcription.diarizer import is_available as _diarization_available
import src.ui.theme as T
from src.ui.sidebar.widgets import card, hover, radiobutton, section_label

_DIARIZATION_AVAILABLE = _diarization_available()


class TranscribeTab:
    """
    Settings panel for the Transcribe mode tab.

    Args:
        parent: The tab frame inside the left-panel Notebook.
        selected_path: Shared StringVar holding the chosen file path.
        model_var: Shared StringVar holding the chosen Whisper model name.
        on_transcribe: Callback — ``on_transcribe(path, model_name,
                       export_format, do_translate, max_words_per_line,
                       extract_onscreen, ocr_languages, diarize, hf_token)``.
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

        self._export_format_var  = tk.StringVar(value=settings.get("transcribe_export_format", DEFAULT_EXPORT_FORMAT.value))
        self._max_words_var      = tk.IntVar(value=settings.get("transcribe_max_words", DEFAULT_MAX_WORDS_PER_LINE))
        self._translate_var      = tk.BooleanVar(value=settings.get("transcribe_translate", False))
        self._onscreen_var       = tk.BooleanVar(value=settings.get("transcribe_onscreen", False))
        self._ocr_langs_var      = tk.StringVar(value=settings.get("transcribe_ocr_langs", "en"))
        self._diarize_var        = tk.BooleanVar(value=settings.get("transcribe_diarize", False))
        self._hf_token_var       = tk.StringVar(value=settings.get("hf_token", ""))

        self._build(parent)

        if self._onscreen_var.get():
            self._toggle_ocr_langs()
        if self._diarize_var.get():
            self._toggle_hf_token()

    def submit(self) -> None:
        self._handle_submit()

    def set_busy(self, busy: bool) -> None:
        btn = "disabled" if busy else "normal"
        self._radio_srt.config(state=btn)
        self._radio_plain.config(state=btn)
        self._max_words_spinbox.config(state=btn)
        self._translate_checkbox.config(state=btn)
        self._onscreen_checkbox.config(state=btn)
        self._ocr_langs_entry.config(state=btn)
        self._diarize_checkbox.config(state=btn)
        self._hf_token_entry.config(state=btn)
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

        self._onscreen_checkbox = tk.Checkbutton(
            opt_card,
            text="Extract on-screen text  (OCR)",
            variable=self._onscreen_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT, relief="flat", bd=0, cursor="hand2",
            command=self._toggle_ocr_langs,
        )
        self._onscreen_checkbox.pack(anchor="w", pady=(4, 0))

        # Language picker — shown only when OCR is enabled
        self._ocr_langs_frame = tk.Frame(opt_card, bg=T.C_CARD)

        tk.Label(
            self._ocr_langs_frame, text="Languages (comma-separated)",
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2,
        ).pack(anchor="w", pady=(6, 1))

        self._ocr_langs_entry = tk.Entry(
            self._ocr_langs_frame, textvariable=self._ocr_langs_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1, relief="flat",
            highlightthickness=1, highlightbackground=T.C_BORDER,
            highlightcolor=T.C_ACCENT,
        )
        self._ocr_langs_entry.pack(fill="x", pady=(0, 2))

        tk.Label(
            self._ocr_langs_frame,
            text="e.g.  en · zh · ja · ko · fr · de · es · ar · hi · ru",
            font=("Segoe UI", 8), bg=T.C_CARD, fg=T.C_TEXT_2,
        ).pack(anchor="w")

        self._diarize_checkbox = tk.Checkbutton(
            opt_card,
            text="Speaker labels  (diarization)",
            variable=self._diarize_var,
            font=T.FONT_LABEL,
            bg=T.C_CARD,
            fg=T.C_TEXT_1,
            activebackground=T.C_CARD,
            activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT,
            relief="flat", bd=0,
            cursor="hand2",
            command=self._toggle_hf_token,
        )
        self._diarize_checkbox.pack(anchor="w", pady=(4, 0))

        # HF token entry — shown only when diarize is enabled
        self._hf_token_frame = tk.Frame(opt_card, bg=T.C_CARD)

        tk.Label(
            self._hf_token_frame, text="Hugging Face token",
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2,
        ).pack(anchor="w", pady=(6, 1))

        self._hf_token_entry = tk.Entry(
            self._hf_token_frame, textvariable=self._hf_token_var,
            show="*",
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1, relief="flat",
            highlightthickness=1, highlightbackground=T.C_BORDER,
            highlightcolor=T.C_ACCENT,
        )
        self._hf_token_entry.pack(fill="x", pady=(0, 2))

        tk.Label(
            self._hf_token_frame,
            text="Requires access to pyannote/speaker-diarization-3.1",
            font=("Segoe UI", 8), bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2 - 20,
            justify="left",
        ).pack(anchor="w")

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

    def _toggle_ocr_langs(self) -> None:
        if self._onscreen_var.get():
            self._ocr_langs_frame.pack(fill="x", padx=(20, 0), pady=(0, 4))
        else:
            self._ocr_langs_frame.pack_forget()

    def _toggle_hf_token(self) -> None:
        if self._diarize_var.get():
            self._hf_token_frame.pack(fill="x", padx=(20, 0), pady=(0, 4))
        else:
            self._hf_token_frame.pack_forget()

    def _parse_ocr_languages(self) -> list[str]:
        raw = self._ocr_langs_var.get()
        codes = [c.strip() for c in raw.replace(",", " ").split() if c.strip()]
        return codes if codes else ["en"]

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a file first.")
            return
        diarize  = self._diarize_var.get()
        hf_token = self._hf_token_var.get().strip()
        if diarize and not _DIARIZATION_AVAILABLE:
            messagebox.showwarning(
                "pyannote.audio not installed",
                "Speaker diarization requires pyannote.audio.\n\nInstall it with:\n  pip install pyannote.audio",
            )
            return
        if diarize and not hf_token:
            messagebox.showwarning(
                "HF token required",
                "Enter your Hugging Face access token to use speaker diarization.",
            )
            return
        settings.save(
            transcribe_export_format=self._export_format_var.get(),
            transcribe_max_words=self._max_words_var.get(),
            transcribe_translate=self._translate_var.get(),
            transcribe_onscreen=self._onscreen_var.get(),
            transcribe_ocr_langs=self._ocr_langs_var.get(),
            transcribe_diarize=diarize,
            hf_token=hf_token,
        )
        self._on_transcribe(
            path,
            self._model_var.get(),
            ExportFormat(self._export_format_var.get()),
            self._translate_var.get(),
            self._max_words_var.get(),
            self._onscreen_var.get(),
            self._parse_ocr_languages(),
            diarize,
            hf_token,
        )
