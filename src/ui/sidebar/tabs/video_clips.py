"""
ui/sidebar/tabs/video_clips.py — Video Clips mode tab panel.

SRP: Owns clip-generation settings that are unique to this tab (clip mode,
     aspect ratio, clip count, cut options, instructions, prompt override)
     and the Generate Clips action. API key / Claude model / analysis
     strategies are delegated to shared widgets.
GRASP Information Expert: sole authority on clip parameters. Reads shared
     *selected_path* / *model_var* supplied by LeftPanel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.models import (
    ASPECT_RATIO_LABELS, CLIP_MODE_LABELS,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_CLIP_MODE, DEFAULT_MAX_CLIPS,
    AnalysisStrategy, AspectRatio, ClipMode,
)
import src.ui.theme as T
from src.ui.sidebar.widgets import card, hover, section_label
from src.ui.shared.api_settings import ApiSettingsWidget
from src.ui.shared.strategy_picker import StrategyPickerWidget

_INSTRUCTIONS_PLACEHOLDER = (
    "e.g. Focus on funny moments only. Highlight any product mentions. "
    "Keep clips under 45 s. Avoid political topics."
)

_OVERRIDE_PLACEHOLDER = (
    "Paste your full replacement prompt here. Use {transcript} where you want "
    "the transcript injected, or it will be appended automatically. "
    "Replaces the mode template entirely — system rules still apply."
)

_ENTRY_STYLE = dict(
    font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
    insertbackground=T.C_TEXT_1, relief="flat",
    highlightthickness=1, highlightbackground=T.C_BORDER,
    highlightcolor=T.C_ACCENT,
)


class VideoClipsTab:
    """
    Settings panel for the Video Clips mode tab.

    Args:
        parent: The tab frame inside the left-panel Notebook.
        selected_path: Shared StringVar holding the chosen file path.
        model_var: Shared StringVar holding the chosen Whisper model name.
        on_generate_clips: Callback — ``on_generate_clips(path, model_name,
                           max_clips, api_key, claude_model, clip_mode,
                           aspect_ratio, custom_instructions,
                           allow_cut_anywhere, min_segment_duration,
                           prompt_override, analysis_strategies,
                           min_clip_duration, max_clip_duration,
                           cuts_per_clip)``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        selected_path: tk.StringVar,
        model_var: tk.StringVar,
        on_generate_clips,
    ) -> None:
        self._selected_path     = selected_path
        self._model_var         = model_var
        self._on_generate_clips = on_generate_clips

        self._clip_mode_var          = tk.StringVar(value=CLIP_MODE_LABELS[DEFAULT_CLIP_MODE])
        self._aspect_ratio_var       = tk.StringVar(value=ASPECT_RATIO_LABELS[DEFAULT_ASPECT_RATIO])
        self._max_clips_var          = tk.IntVar(value=DEFAULT_MAX_CLIPS)
        self._min_segment_var        = tk.DoubleVar(value=0.8)
        self._allow_cut_anywhere_var = tk.BooleanVar(value=False)
        # Clip duration / cuts constraints (all optional)
        self._min_clip_dur_var  = tk.StringVar(value="")
        self._max_clip_dur_var  = tk.StringVar(value="")
        self._auto_cuts_var     = tk.BooleanVar(value=True)
        self._cuts_per_clip_var = tk.IntVar(value=3)

        self._build(parent)

        self._clip_mode_var.trace_add("write", self._on_clip_mode_changed)

    def submit(self) -> None:
        self._handle_submit()

    def set_busy(self, busy: bool) -> None:
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"
        self._api_settings.set_busy(busy)
        self._strategy_picker.set_busy(busy)
        self._max_clips_spinbox.config(state=btn)
        self._min_segment_spinbox.config(state=btn)
        self._cut_anywhere_check.config(state=btn)
        self._clip_mode_menu.config(state=combo)
        self._aspect_ratio_menu.config(state=combo)
        self._min_dur_entry.config(state=btn)
        self._max_dur_entry.config(state=btn)
        self._auto_cuts_check.config(state=btn)
        if not self._auto_cuts_var.get():
            self._cuts_spinbox.config(state=btn)
        self._instructions_text.config(state=btn)
        self._override_text.config(state=btn)
        self._clips_button.config(
            state=btn,
            bg=T.C_ACCENT_D if busy else T.C_ACCENT,
            cursor="" if busy else "hand2",
        )

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        # ── Shared: API key + Claude model ────────────────────────────
        self._api_settings = ApiSettingsWidget(parent)

        # ── Clip-specific settings card ────────────────────────────────
        clips_card = card(parent)

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
        clips_row.pack(fill="x")
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

        # Min segment duration
        min_seg_row = tk.Frame(clips_card, bg=T.C_CARD)
        min_seg_row.pack(fill="x", pady=(8, 0))
        tk.Label(min_seg_row, text="Min. segment (s)", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._min_segment_spinbox = tk.Spinbox(
            min_seg_row, from_=0.1, to=30.0, increment=0.1,
            textvariable=self._min_segment_var, width=5, format="%.1f",
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1,
            highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._min_segment_spinbox.pack(side="right")

        # Allow cut anywhere
        self._cut_anywhere_check = tk.Checkbutton(
            clips_card,
            text="Allow cut anywhere (full word)",
            variable=self._allow_cut_anywhere_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_BG, relief="flat", bd=0, cursor="hand2",
        )
        self._cut_anywhere_check.pack(anchor="w", pady=(8, 0))

        # ── Clip duration + cuts constraints ──────────────────────────
        section_label(parent, "CLIP CONSTRAINTS  (optional)")
        dur_card = card(parent)

        # Min / Max clip duration on one row
        dur_row = tk.Frame(dur_card, bg=T.C_CARD)
        dur_row.pack(fill="x")

        tk.Label(dur_row, text="Min (s)", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).grid(row=0, column=0, sticky="w")
        self._min_dur_entry = tk.Entry(
            dur_row, textvariable=self._min_clip_dur_var, width=6,
            **_ENTRY_STYLE,
        )
        self._min_dur_entry.grid(row=0, column=1, padx=(4, 16), sticky="w")

        tk.Label(dur_row, text="Max (s)", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).grid(row=0, column=2, sticky="w")
        self._max_dur_entry = tk.Entry(
            dur_row, textvariable=self._max_clip_dur_var, width=6,
            **_ENTRY_STYLE,
        )
        self._max_dur_entry.grid(row=0, column=3, padx=(4, 0), sticky="w")

        tk.Label(dur_card,
                 text="Leave blank to let AI choose clip length.",
                 font=("Segoe UI", 8), bg=T.C_CARD, fg=T.C_TEXT_3,
                 ).pack(anchor="w", pady=(4, 8))

        # Cuts per clip
        cuts_row = tk.Frame(dur_card, bg=T.C_CARD)
        cuts_row.pack(fill="x")
        tk.Label(cuts_row, text="Cuts per clip", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")

        self._auto_cuts_check = tk.Checkbutton(
            cuts_row, text="Auto",
            variable=self._auto_cuts_var,
            command=self._toggle_cuts_spinbox,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_BG, relief="flat", bd=0, cursor="hand2",
        )
        self._auto_cuts_check.pack(side="right")

        self._cuts_spinbox = tk.Spinbox(
            cuts_row, from_=1, to=20, textvariable=self._cuts_per_clip_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1,
            highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
            state="disabled",
        )
        self._cuts_spinbox.pack(side="right", padx=(0, 6))

        # ── Shared: analysis strategies ────────────────────────────────
        self._strategy_picker = StrategyPickerWidget(parent)

        # ── Custom instructions card ───────────────────────────────────
        section_label(parent, "CUSTOM INSTRUCTIONS  (optional)")
        instr_card = card(parent)

        tk.Label(
            instr_card,
            text="Tell Claude what to focus on, avoid, or how to edit:",
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
            justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 6))

        text_frame = tk.Frame(instr_card, bg=T.C_BORDER, padx=1, pady=1)
        text_frame.pack(fill="x")

        self._instructions_text = tk.Text(
            text_frame, height=5, wrap=tk.WORD,
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_3,
            insertbackground=T.C_TEXT_1, selectbackground=T.C_ACCENT,
            selectforeground="#ffffff", relief="flat", bd=0, padx=8, pady=6,
        )
        instr_scrollbar = ttk.Scrollbar(
            text_frame, orient="vertical",
            command=self._instructions_text.yview,
            style="Sidebar.Vertical.TScrollbar",
        )
        self._instructions_text.configure(yscrollcommand=instr_scrollbar.set)
        self._instructions_text.pack(side="left", fill="x", expand=True)
        instr_scrollbar.pack(side="right", fill="y")

        self._instructions_text.insert("1.0", _INSTRUCTIONS_PLACEHOLDER)
        self._instructions_placeholder_active = True
        self._instructions_text.bind("<FocusIn>",  self._on_instructions_focus_in)
        self._instructions_text.bind("<FocusOut>", self._on_instructions_focus_out)

        # ── Prompt override card ───────────────────────────────────────
        section_label(parent, "PROMPT OVERRIDE  (optional)")
        override_card = card(parent)

        tk.Label(
            override_card,
            text="Replace the mode template sent to Claude:",
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
            justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 6))

        override_frame = tk.Frame(override_card, bg=T.C_BORDER, padx=1, pady=1)
        override_frame.pack(fill="x")

        self._override_text = tk.Text(
            override_frame, height=6, wrap=tk.WORD,
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_3,
            insertbackground=T.C_TEXT_1, selectbackground=T.C_ACCENT,
            selectforeground="#ffffff", relief="flat", bd=0, padx=8, pady=6,
        )
        override_scrollbar = ttk.Scrollbar(
            override_frame, orient="vertical",
            command=self._override_text.yview,
            style="Sidebar.Vertical.TScrollbar",
        )
        self._override_text.configure(yscrollcommand=override_scrollbar.set)
        self._override_text.pack(side="left", fill="x", expand=True)
        override_scrollbar.pack(side="right", fill="y")

        self._override_text.insert("1.0", _OVERRIDE_PLACEHOLDER)
        self._override_placeholder_active = True
        self._override_text.bind("<FocusIn>",  self._on_override_focus_in)
        self._override_text.bind("<FocusOut>", self._on_override_focus_out)

        # ── Generate Clips button ──────────────────────────────────────
        btn_frame = tk.Frame(parent, bg=T.C_SIDEBAR)
        btn_frame.pack(fill="x", padx=T.PAD_H, pady=(12, 10))
        self._clips_button = tk.Button(
            btn_frame, text="Generate Clips", command=self._handle_submit,
            font=T.FONT_BUTTON, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=10,
        )
        self._clips_button.pack(fill="x")
        hover(self._clips_button, T.C_ACCENT, T.C_ACCENT_H)

    # ------------------------------------------------------------------
    # Private — placeholder helpers
    # ------------------------------------------------------------------

    def _on_instructions_focus_in(self, _event) -> None:
        if self._instructions_placeholder_active:
            self._instructions_text.delete("1.0", tk.END)
            self._instructions_text.config(fg=T.C_TEXT_1)
            self._instructions_placeholder_active = False

    def _on_instructions_focus_out(self, _event) -> None:
        if not self._instructions_text.get("1.0", tk.END).strip():
            self._instructions_text.insert("1.0", _INSTRUCTIONS_PLACEHOLDER)
            self._instructions_text.config(fg=T.C_TEXT_3)
            self._instructions_placeholder_active = True

    def _on_override_focus_in(self, _event) -> None:
        if self._override_placeholder_active:
            self._override_text.delete("1.0", tk.END)
            self._override_text.config(fg=T.C_TEXT_1)
            self._override_placeholder_active = False

    def _on_override_focus_out(self, _event) -> None:
        if not self._override_text.get("1.0", tk.END).strip():
            self._override_text.insert("1.0", _OVERRIDE_PLACEHOLDER)
            self._override_text.config(fg=T.C_TEXT_3)
            self._override_placeholder_active = True

    def _toggle_cuts_spinbox(self) -> None:
        self._cuts_spinbox.config(
            state="disabled" if self._auto_cuts_var.get() else "normal"
        )

    # ------------------------------------------------------------------
    # Private — resolve helpers
    # ------------------------------------------------------------------

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

    def _get_custom_instructions(self) -> str:
        if self._instructions_placeholder_active:
            return ""
        return self._instructions_text.get("1.0", tk.END).strip()

    def _get_prompt_override(self) -> str:
        if self._override_placeholder_active:
            return ""
        return self._override_text.get("1.0", tk.END).strip()

    def _get_duration(self, var: tk.StringVar) -> float | None:
        """Parse a duration entry; return None if blank or invalid."""
        raw = var.get().strip()
        if not raw:
            return None
        try:
            v = float(raw)
            return v if v > 0 else None
        except ValueError:
            return None

    def _get_cuts_per_clip(self) -> int | None:
        """Return None when Auto is checked (let Claude decide)."""
        if self._auto_cuts_var.get():
            return None
        try:
            return max(1, int(self._cuts_per_clip_var.get()))
        except (ValueError, tk.TclError):
            return None

    def _on_clip_mode_changed(self, *_) -> None:
        if self._resolve_clip_mode() is ClipMode.HIGHLIGHTS:
            if not self._strategy_picker.any_enabled():
                self._strategy_picker.set_strategy(AnalysisStrategy.AUDIO_ENERGY, True)

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return
        api_key = self._api_settings.api_key
        if not api_key:
            messagebox.showwarning("API key required", "Please enter your Anthropic API key.")
            return

        min_dur = self._get_duration(self._min_clip_dur_var)
        max_dur = self._get_duration(self._max_clip_dur_var)
        if min_dur is not None and max_dur is not None and min_dur >= max_dur:
            messagebox.showwarning(
                "Invalid clip length",
                "Min clip length must be less than Max clip length.",
            )
            return

        self._api_settings.save()
        self._on_generate_clips(
            path,
            self._model_var.get(),
            self._max_clips_var.get(),
            api_key,
            self._api_settings.claude_model_id,
            self._resolve_clip_mode(),
            self._resolve_aspect_ratio(),
            self._get_custom_instructions(),
            self._allow_cut_anywhere_var.get(),
            self._min_segment_var.get(),
            self._get_prompt_override(),
            self._strategy_picker.selected,
            min_dur,
            max_dur,
            self._get_cuts_per_clip(),
        )
