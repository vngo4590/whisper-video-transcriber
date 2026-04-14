"""
ui/shared/strategy_picker.py — Reusable analysis-strategy checkbox group.

SRP: Owns the visual component for the "Analysis Strategies" section label +
     card + checkbox list. Used by VideoClipsTab and ContentPlanTab so neither
     tab duplicates this code.
"""

import tkinter as tk

from src.models import ANALYSIS_STRATEGY_LABELS, DEFAULT_ANALYSIS_STRATEGIES, AnalysisStrategy
import src.ui.theme as T
from src.ui.sidebar.widgets import card, section_label


class StrategyPickerWidget:
    """
    Composite widget: section label + card + one checkbox per AnalysisStrategy.

    Packs its section heading and card directly into *parent* (the tab frame).
    Exposes a ``selected`` property so the host tab can read the active
    strategies without touching internal BooleanVars.

    Args:
        parent: The tab frame (or any container) to pack into.
    """

    def __init__(self, parent: tk.Widget) -> None:
        self._strategy_vars: dict[AnalysisStrategy, tk.BooleanVar] = {
            s: tk.BooleanVar(value=(s in DEFAULT_ANALYSIS_STRATEGIES))
            for s in AnalysisStrategy
        }
        self._checkboxes: dict[AnalysisStrategy, tk.Checkbutton] = {}
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def selected(self) -> set[AnalysisStrategy]:
        """Return the set of currently checked strategies."""
        return {s for s, var in self._strategy_vars.items() if var.get()}

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for cb in self._checkboxes.values():
            cb.config(state=state)

    def set_strategy(self, strategy: AnalysisStrategy, value: bool) -> None:
        """Programmatically check or uncheck a single strategy."""
        self._strategy_vars[strategy].set(value)

    def any_enabled(self) -> bool:
        return any(v.get() for v in self._strategy_vars.values())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
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
            self._checkboxes[strategy] = cb
