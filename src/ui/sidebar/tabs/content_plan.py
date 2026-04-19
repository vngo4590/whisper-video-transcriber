"""
ui/sidebar/tabs/content_plan.py — Content Plan mode tab panel.

SRP: Owns content-plan settings that are unique to this tab (focus,
     max highlights, context textarea) and the Generate Plan action.
     API key / Claude model / analysis strategies are delegated to
     shared widgets.
GRASP Information Expert: sole authority on content-plan parameters.
     Reads shared *selected_path* / *model_var* supplied by LeftPanel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.analysis.content_planner import FOCUS_OPTIONS
import src.ui.theme as T
from src.ui.sidebar.widgets import card, hover, section_label
from src.ui.shared.api_settings import ApiSettingsWidget
from src.ui.shared.strategy_picker import StrategyPickerWidget

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

        self._focus_var          = tk.StringVar(value=FOCUS_OPTIONS[0])
        self._max_highlights_var = tk.IntVar(value=5)
        self._context_placeholder_active = True

        self._build(parent)

    # ------------------------------------------------------------------
    # Public API — called by LeftPanel to reflect processing state
    # ------------------------------------------------------------------

    def submit(self) -> None:
        self._handle_submit()

    def set_busy(self, busy: bool) -> None:
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"
        self._api_settings.set_busy(busy)
        self._strategy_picker.set_busy(busy)
        self._max_highlights_spinbox.config(state=btn)
        self._focus_menu.config(state=combo)
        self._context_text.config(state=btn)
        self._plan_button.config(
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

        # ── Content-plan-specific settings card ───────────────────────
        cfg_card = card(parent)

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

        # ── Shared: analysis strategies ────────────────────────────────
        self._strategy_picker = StrategyPickerWidget(parent)

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
    # Private — submit
    # ------------------------------------------------------------------

    def _handle_submit(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return
        api_key = self._api_settings.api_key
        if not api_key:
            messagebox.showwarning("API key required", "Please enter your Anthropic API key.")
            return
        self._api_settings.save()
        self._on_generate_plan(
            path,
            self._model_var.get(),
            api_key,
            self._api_settings.claude_model_id,
            self._focus_var.get(),
            self._max_highlights_var.get(),
            self._get_context(),
            self._strategy_picker.selected,
        )
