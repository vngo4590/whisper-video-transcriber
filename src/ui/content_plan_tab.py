"""
ui/content_plan_tab.py — Content Plan mode tab panel.

SRP: Owns all content-plan settings (API key, Claude model, focus, analysis
     strategies, context) and the Generate Plan action. Has no knowledge of
     transcription internals or video cutting.
GRASP Information Expert: sole authority on content-plan parameters. Reads
     shared *selected_path* / *model_var* supplied by LeftPanel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.analysis.content_planner import FOCUS_OPTIONS
from src.config import settings
from src.models import (
    ANALYSIS_STRATEGY_LABELS, CLAUDE_MODELS, DEFAULT_ANALYSIS_STRATEGIES,
    DEFAULT_CLAUDE_MODEL, AnalysisStrategy,
)
import src.ui.theme as T
from src.ui.sidebar_widgets import card, hover, section_label

_CONTEXT_PLACEHOLDER = (
    "e.g. This is a gaming stream. Focus on reaction moments and clutch plays. "
    "Ignore tutorial sections. Prefer clips under 45 s."
)


class ContentPlanTab:
    """
    Settings panel for the Content Plan mode tab.

    Args:
        parent: The tab frame inside the left-panel Notebook.
        selected_path: Shared StringVar holding the chosen file path.
        model_var: Shared StringVar holding the chosen Whisper model name.
        on_generate_plan: Callback — ``on_generate_plan(path, model_name,
                          api_key, claude_model, focus, max_highlights,
                          context, analysis_strategies)``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        selected_path: tk.StringVar,
        model_var: tk.StringVar,
        on_generate_plan,
    ) -> None:
        self._selected_path    = selected_path
        self._model_var        = model_var
        self._on_generate_plan = on_generate_plan

        self._api_key_var          = tk.StringVar(value=settings.get("api_key", ""))
        _saved_model               = settings.get("claude_model", DEFAULT_CLAUDE_MODEL.model_id)
        _model_label               = next((m.label for m in CLAUDE_MODELS if m.model_id == _saved_model), DEFAULT_CLAUDE_MODEL.label)
        self._claude_model_var     = tk.StringVar(value=_model_label)
        self._focus_var            = tk.StringVar(value=FOCUS_OPTIONS[0])
        self._max_highlights_var   = tk.IntVar(value=5)
        self._context_placeholder_active = True

        self._strategy_vars: dict[AnalysisStrategy, tk.BooleanVar] = {
            s: tk.BooleanVar(value=(s in DEFAULT_ANALYSIS_STRATEGIES))
            for s in AnalysisStrategy
        }
        self._strategy_checkboxes: dict[AnalysisStrategy, tk.Checkbutton] = {}

        self._build(parent)

    # ------------------------------------------------------------------
    # Public API — called by LeftPanel to reflect processing state
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"
        self._api_key_entry.config(state=btn)
        self._max_highlights_spinbox.config(state=btn)
        self._claude_model_menu.config(state=combo)
        self._focus_menu.config(state=combo)
        self._context_text.config(state=btn)
        for cb in self._strategy_checkboxes.values():
            cb.config(state=btn)
        self._plan_button.config(
            state=btn,
            bg=T.C_ACCENT_D if busy else T.C_ACCENT,
            cursor="" if busy else "hand2",
        )

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        # ── Settings card ─────────────────────────────────────────────
        cfg_card = card(parent)
        cfg_card.pack_configure(pady=(14, 0))

        # API key
        key_label_row = tk.Frame(cfg_card, bg=T.C_CARD)
        key_label_row.pack(fill="x")
        tk.Label(key_label_row, text="Anthropic API key", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        tk.Button(
            key_label_row, text="clear cache",
            command=self._clear_cache,
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3,
            activebackground=T.C_CARD, activeforeground=T.C_ERROR,
            relief="flat", bd=0, cursor="hand2",
        ).pack(side="right")
        self._api_key_entry = tk.Entry(
            cfg_card, textvariable=self._api_key_var, show="•",
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1, relief="flat",
            highlightthickness=1, highlightbackground=T.C_BORDER,
            highlightcolor=T.C_ACCENT,
        )
        self._api_key_entry.pack(fill="x", pady=(4, 10))

        # Claude model
        tk.Label(cfg_card, text="Claude model", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._claude_model_menu = ttk.Combobox(
            cfg_card, textvariable=self._claude_model_var, state="readonly",
            values=[f"{m.label}  ·  {m.cost_tier}" for m in CLAUDE_MODELS],
            style="Dark.TCombobox",
        )
        self._claude_model_menu.pack(fill="x", pady=(4, 10))

        # Focus
        tk.Label(cfg_card, text="Focus", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._focus_menu = ttk.Combobox(
            cfg_card, textvariable=self._focus_var, state="readonly",
            values=FOCUS_OPTIONS, style="Dark.TCombobox",
        )
        self._focus_menu.pack(fill="x", pady=(4, 10))

        # Max highlights
        hl_row = tk.Frame(cfg_card, bg=T.C_CARD)
        hl_row.pack(fill="x")
        tk.Label(hl_row, text="Max highlights", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._max_highlights_spinbox = tk.Spinbox(
            hl_row, from_=1, to=20, textvariable=self._max_highlights_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1,
            highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._max_highlights_spinbox.pack(side="right")

        # ── Analysis strategies card ───────────────────────────────────
        section_label(parent, "ANALYSIS STRATEGIES")
        strategy_card = card(parent)

        tk.Label(
            strategy_card,
            text="Inject moment signals into the transcript for Claude:",
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
            justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 6))

        for strategy in AnalysisStrategy:
            cb = tk.Checkbutton(
                strategy_card,
                text=ANALYSIS_STRATEGY_LABELS[strategy],
                variable=self._strategy_vars[strategy],
                font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2,
                activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
                selectcolor=T.C_BG, relief="flat", bd=0, cursor="hand2",
            )
            cb.pack(anchor="w", pady=(2, 0))
            self._strategy_checkboxes[strategy] = cb

        # ── Context card ───────────────────────────────────────────────
        section_label(parent, "CONTEXT  (optional)")
        ctx_card = card(parent)

        tk.Label(
            ctx_card,
            text="Tell Claude what to focus on, ignore, or prioritise:",
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
            justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 6))

        text_frame = tk.Frame(ctx_card, bg=T.C_BORDER, padx=1, pady=1)
        text_frame.pack(fill="x")

        self._context_text = tk.Text(
            text_frame, height=4, wrap=tk.WORD,
            font=T.FONT_LABEL, bg=T.C_BG, fg=T.C_TEXT_3,
            insertbackground=T.C_TEXT_1, selectbackground=T.C_ACCENT,
            selectforeground="#ffffff", relief="flat", bd=0, padx=8, pady=6,
        )
        ctx_sb = ttk.Scrollbar(
            text_frame, orient="vertical",
            command=self._context_text.yview,
            style="Sidebar.Vertical.TScrollbar",
        )
        self._context_text.configure(yscrollcommand=ctx_sb.set)
        self._context_text.pack(side="left", fill="x", expand=True)
        ctx_sb.pack(side="right", fill="y")

        self._context_text.insert("1.0", _CONTEXT_PLACEHOLDER)
        self._context_text.bind("<FocusIn>",  self._on_context_focus_in)
        self._context_text.bind("<FocusOut>", self._on_context_focus_out)

        # ── Generate button ────────────────────────────────────────────
        btn_frame = tk.Frame(parent, bg=T.C_SIDEBAR)
        btn_frame.pack(fill="x", padx=T.PAD_H, pady=(12, 10))
        self._plan_button = tk.Button(
            btn_frame, text="Generate Content Plan", command=self._handle_submit,
            font=T.FONT_BUTTON, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=10,
        )
        self._plan_button.pack(fill="x")
        hover(self._plan_button, T.C_ACCENT, T.C_ACCENT_H)

    # ------------------------------------------------------------------
    # Private — placeholder helpers
    # ------------------------------------------------------------------

    def _on_context_focus_in(self, _event) -> None:
        if self._context_placeholder_active:
            self._context_text.delete("1.0", tk.END)
            self._context_text.config(fg=T.C_TEXT_1)
            self._context_placeholder_active = False

    def _on_context_focus_out(self, _event) -> None:
        if not self._context_text.get("1.0", tk.END).strip():
            self._context_text.insert("1.0", _CONTEXT_PLACEHOLDER)
            self._context_text.config(fg=T.C_TEXT_3)
            self._context_placeholder_active = True

    def _get_context(self) -> str:
        if self._context_placeholder_active:
            return ""
        return self._context_text.get("1.0", tk.END).strip()

    # ------------------------------------------------------------------
    # Private — cache helpers
    # ------------------------------------------------------------------

    def _clear_cache(self) -> None:
        settings.clear()
        self._api_key_var.set("")
        self._claude_model_var.set(DEFAULT_CLAUDE_MODEL.label)

    # ------------------------------------------------------------------
    # Private — resolve helpers
    # ------------------------------------------------------------------

    def _resolve_claude_model_id(self) -> str:
        selected = self._claude_model_var.get()
        for m in CLAUDE_MODELS:
            if selected.startswith(m.label):
                return m.model_id
        return DEFAULT_CLAUDE_MODEL.model_id

    def _get_analysis_strategies(self) -> set:
        return {s for s, var in self._strategy_vars.items() if var.get()}

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return
        api_key = self._api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API key required", "Please enter your Anthropic API key.")
            return
        settings.save(api_key=api_key, claude_model=self._resolve_claude_model_id())
        self._on_generate_plan(
            path,
            self._model_var.get(),
            api_key,
            self._resolve_claude_model_id(),
            self._focus_var.get(),
            self._max_highlights_var.get(),
            self._get_context(),
            self._get_analysis_strategies(),
        )
