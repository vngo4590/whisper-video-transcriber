"""
ui/shared/api_settings.py — Reusable Anthropic API key + Claude model widget.

SRP: Owns the visual component and persistence logic for the API key entry
     and Claude model combobox. Used by VideoClipsTab and ContentPlanTab so
     neither tab duplicates this code.
"""

import tkinter as tk
from tkinter import ttk

from src.config import settings
from src.models import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL
import src.ui.theme as T
from src.ui.sidebar.widgets import card


class ApiSettingsWidget:
    """
    Composite widget: Anthropic API key field + Claude model combobox.

    Creates its own card frame packed into *parent*. Exposes ``api_key`` and
    ``claude_model_id`` properties so the host tab can pass them directly to
    a controller without knowing about the internal StringVars.

    Args:
        parent: The tab frame (or any container) to pack the card into.
    """

    def __init__(self, parent: tk.Widget) -> None:
        self._api_key_var = tk.StringVar(value=settings.get("api_key", ""))
        _saved = settings.get("claude_model", DEFAULT_CLAUDE_MODEL.model_id)
        _label = next(
            (m.label for m in CLAUDE_MODELS if m.model_id == _saved),
            DEFAULT_CLAUDE_MODEL.label,
        )
        self._claude_model_var = tk.StringVar(value=_label)
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def api_key(self) -> str:
        return self._api_key_var.get().strip()

    @property
    def claude_model_id(self) -> str:
        selected = self._claude_model_var.get()
        for m in CLAUDE_MODELS:
            if selected.startswith(m.label):
                return m.model_id
        return DEFAULT_CLAUDE_MODEL.model_id

    def save(self) -> None:
        """Persist api_key and claude_model to the settings store."""
        settings.save(api_key=self.api_key, claude_model=self.claude_model_id)

    def clear(self) -> None:
        """Wipe the local settings cache and reset both fields to defaults."""
        settings.clear()
        self._api_key_var.set("")
        self._claude_model_var.set(DEFAULT_CLAUDE_MODEL.label)

    def set_busy(self, busy: bool) -> None:
        self._api_key_entry.config(state="disabled" if busy else "normal")
        self._model_menu.config(state="disabled" if busy else "readonly")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        cfg_card = card(parent)
        cfg_card.pack_configure(pady=(14, 0))

        # API key label row (label left, clear-cache button right)
        key_label_row = tk.Frame(cfg_card, bg=T.C_CARD)
        key_label_row.pack(fill="x")
        tk.Label(
            key_label_row, text="Anthropic API key", font=T.FONT_LABEL,
            bg=T.C_CARD, fg=T.C_TEXT_2,
        ).pack(side="left")
        tk.Button(
            key_label_row, text="clear cache",
            command=self.clear,
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
        tk.Label(
            cfg_card, text="Claude model", font=T.FONT_LABEL,
            bg=T.C_CARD, fg=T.C_TEXT_2,
        ).pack(anchor="w")
        self._model_menu = ttk.Combobox(
            cfg_card, textvariable=self._claude_model_var, state="readonly",
            values=[f"{m.label}  ·  {m.cost_tier}" for m in CLAUDE_MODELS],
            style="Dark.TCombobox",
        )
        self._model_menu.pack(fill="x", pady=(4, 0))
