"""
ui/video_clips_tab.py — Video Clips mode tab panel.

SRP: Owns all clip-generation settings (API key, Claude model, clip mode,
     aspect ratio, clip count) and the Generate Clips action. Has no
     knowledge of transcription settings.
GRASP Information Expert: sole authority on clip parameters. Reads shared
     *selected_path* / *model_var* supplied by LeftPanel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.models import (
    ASPECT_RATIO_LABELS, CLAUDE_MODELS, CLIP_MODE_LABELS,
    DEFAULT_ASPECT_RATIO, DEFAULT_CLAUDE_MODEL, DEFAULT_CLIP_MODE, DEFAULT_MAX_CLIPS,
    AspectRatio, ClipMode,
)
import src.ui.theme as T
from src.ui.sidebar_widgets import card, hover


class VideoClipsTab:
    """
    Settings panel for the Video Clips mode tab.

    Args:
        parent: The tab frame inside the left-panel Notebook.
        selected_path: Shared StringVar holding the chosen file path.
        model_var: Shared StringVar holding the chosen Whisper model name.
        on_generate_clips: Callback invoked on submit.
    """

    def __init__(
        self,
        parent: tk.Widget,
        selected_path: tk.StringVar,
        model_var: tk.StringVar,
        on_generate_clips,
    ) -> None:
        self._selected_path = selected_path
        self._model_var = model_var
        self._on_generate_clips = on_generate_clips

        self._api_key_var      = tk.StringVar()
        self._claude_model_var = tk.StringVar(value=DEFAULT_CLAUDE_MODEL.label)
        self._clip_mode_var    = tk.StringVar(value=CLIP_MODE_LABELS[DEFAULT_CLIP_MODE])
        self._aspect_ratio_var = tk.StringVar(value=ASPECT_RATIO_LABELS[DEFAULT_ASPECT_RATIO])
        self._max_clips_var    = tk.IntVar(value=DEFAULT_MAX_CLIPS)

        self._build(parent)

    def set_busy(self, busy: bool) -> None:
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"
        self._api_key_entry.config(state=btn)
        self._max_clips_spinbox.config(state=btn)
        self._claude_model_menu.config(state=combo)
        self._clip_mode_menu.config(state=combo)
        self._aspect_ratio_menu.config(state=combo)
        self._clips_button.config(
            state=btn,
            bg=T.C_ACCENT_D if busy else T.C_ACCENT,
            cursor="" if busy else "hand2",
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        clips_card = card(parent)
        clips_card.pack_configure(pady=(14, 0))

        # API key
        tk.Label(clips_card, text="Anthropic API key", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._api_key_entry = tk.Entry(
            clips_card, textvariable=self._api_key_var, show="•",
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1, relief="flat",
            highlightthickness=1, highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._api_key_entry.pack(fill="x", pady=(4, 10))

        # Claude model
        tk.Label(clips_card, text="Claude model", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._claude_model_menu = ttk.Combobox(
            clips_card, textvariable=self._claude_model_var, state="readonly",
            values=[f"{m.label}  ·  {m.cost_tier}" for m in CLAUDE_MODELS],
            style="Dark.TCombobox",
        )
        self._claude_model_menu.pack(fill="x", pady=(4, 10))

        # Clip mode
        tk.Label(clips_card, text="Clip mode", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._clip_mode_menu = ttk.Combobox(
            clips_card, textvariable=self._clip_mode_var, state="readonly",
            values=list(CLIP_MODE_LABELS.values()), style="Dark.TCombobox",
        )
        self._clip_mode_menu.pack(fill="x", pady=(4, 10))

        # Aspect ratio
        tk.Label(clips_card, text="Aspect ratio", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._aspect_ratio_menu = ttk.Combobox(
            clips_card, textvariable=self._aspect_ratio_var, state="readonly",
            values=list(ASPECT_RATIO_LABELS.values()), style="Dark.TCombobox",
        )
        self._aspect_ratio_menu.pack(fill="x", pady=(4, 10))

        # Number of clips
        clips_row = tk.Frame(clips_card, bg=T.C_CARD)
        clips_row.pack(fill="x", pady=(0, 10))
        tk.Label(clips_row, text="Number of clips", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._max_clips_spinbox = tk.Spinbox(
            clips_row, from_=1, to=10, textvariable=self._max_clips_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1,
            highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._max_clips_spinbox.pack(side="right")

        # Generate Clips button
        btn_frame = tk.Frame(parent, bg=T.C_SIDEBAR)
        btn_frame.pack(fill="x", padx=T.PAD_H, pady=(10, 10))
        self._clips_button = tk.Button(
            btn_frame, text="Generate Clips", command=self._handle_submit,
            font=T.FONT_BUTTON, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=10,
        )
        self._clips_button.pack(fill="x")
        hover(self._clips_button, T.C_ACCENT, T.C_ACCENT_H)

    def _resolve_claude_model_id(self) -> str:
        selected = self._claude_model_var.get()
        for m in CLAUDE_MODELS:
            if selected.startswith(m.label):
                return m.model_id
        return DEFAULT_CLAUDE_MODEL.model_id

    def _resolve_clip_mode(self) -> ClipMode:
        selected = self._clip_mode_var.get()
        for mode, label in CLIP_MODE_LABELS.items():
            if selected == label:
                return mode
        return DEFAULT_CLIP_MODE

    def _resolve_aspect_ratio(self) -> AspectRatio:
        selected = self._aspect_ratio_var.get()
        for ratio, label in ASPECT_RATIO_LABELS.items():
            if selected == label:
                return ratio
        return DEFAULT_ASPECT_RATIO

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return
        api_key = self._api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API key required", "Please enter your Anthropic API key.")
            return
        self._on_generate_clips(
            path,
            self._model_var.get(),
            self._max_clips_var.get(),
            api_key,
            self._resolve_claude_model_id(),
            self._resolve_clip_mode(),
            self._resolve_aspect_ratio(),
        )
