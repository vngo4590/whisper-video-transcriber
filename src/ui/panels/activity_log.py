"""
ui/panels/activity_log.py — Live activity log panel for the right-side notebook.

SRP:  Displays timestamped log entries while an operation is running.
      No knowledge of Whisper, Claude, or any controller.

Each entry has a level that controls its colour so the user can scan the log
at a glance and distinguish pipeline stages, API calls, raw details, and errors.

Levels and colours:
    stage   — cyan     — major pipeline step ("Transcribing video…")
    api     — yellow   — outbound API call   ("→ Claude API  model=…")
    detail  — muted    — fine-grained info   ("→ Sending 3 412 chars…")
    success — green    — job finished
    warn    — orange   — non-fatal warning / cancellation
    error   — red      — exception message
    info    — white    — general messages (default)
"""

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from src.ui.theme import (
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_ERROR,
    C_SUCCESS,
    C_TEXT_1,
    C_TEXT_2,
    C_TEXT_3,
    C_WARN,
    FONT_MONO,
    FONT_SECTION,
    PAD_H,
)

# One colour per level — kept in a single dict so the Text widget tag table
# and the append() dispatcher stay in sync automatically.
_LEVEL_COLOURS: dict[str, str] = {
    "stage":   "#8be9fd",   # bright cyan — stands out as a phase header
    "api":     "#f1fa8c",   # yellow      — any outbound API call
    "detail":  C_TEXT_2,    # muted       — verbose / fine-grained info
    "success": C_SUCCESS,   # green
    "warn":    C_WARN,      # orange
    "error":   C_ERROR,     # red
    "info":    C_TEXT_1,    # default white-ish
}


class ActivityLogPanel:
    """
    Scrollable, colour-coded activity log shown in the "Activity" right-panel tab.

    Call ``append(message, level)`` from any thread — it marshals to the main
    thread internally via ``after(0, …)``.  ``clear()`` resets for a new run.

    Args:
        parent:    tkinter container widget (the notebook tab frame).
        root:      The root Tk window — needed for ``after()`` thread-marshalling.
    """

    def __init__(self, parent: tk.Widget, root: tk.Tk) -> None:
        self._root = root
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all log entries and show the waiting placeholder."""
        self._textbox.config(state="normal")
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, "Waiting for operation to start…")
        self._textbox.config(state="disabled", fg=C_TEXT_3)

    def append(self, message: str, level: str = "info") -> None:
        """
        Add a timestamped log entry.

        Thread-safe — can be called from any thread.  The actual widget update
        is always dispatched to the main thread via after(0).
        """
        # Capture level now so the lambda doesn't close over a mutable variable
        self._root.after(0, lambda m=message, lv=level: self._write(m, lv))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=C_BG)
        panel.pack(fill="both", expand=True)

        # Header bar
        header = tk.Frame(panel, bg=C_BG)
        header.pack(fill="x", padx=PAD_H, pady=(16, 8))
        tk.Label(
            header,
            text="ACTIVITY LOG",
            font=FONT_SECTION,
            bg=C_BG,
            fg=C_TEXT_3,
        ).pack(side="left")

        # Scrollable text area
        text_frame = tk.Frame(panel, bg=C_BORDER, padx=1, pady=1)
        text_frame.pack(fill="both", expand=True, padx=PAD_H, pady=(0, PAD_H))

        self._textbox = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=FONT_MONO,
            bg=C_CARD,
            fg=C_TEXT_1,
            insertbackground=C_TEXT_1,
            selectbackground=C_ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=14,
            spacing1=1,
            spacing3=1,
            state="disabled",
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self._textbox.yview,
            style="Output.Vertical.TScrollbar",
        )
        self._textbox.configure(yscrollcommand=scrollbar.set)
        self._textbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Register a colour tag for each log level
        for level, colour in _LEVEL_COLOURS.items():
            self._textbox.tag_configure(level, foreground=colour)

        # Muted tag used for the [HH:MM:SS] timestamp prefix on every line
        self._textbox.tag_configure("timestamp", foreground=C_TEXT_3)

        self.clear()

    def _write(self, message: str, level: str) -> None:
        """Insert one log line.  Must be called on the main thread."""
        self._textbox.config(state="normal", fg=C_TEXT_1)

        # Remove the placeholder on the very first real write
        current = self._textbox.get("1.0", tk.END).strip()
        if current == "Waiting for operation to start…":
            self._textbox.delete("1.0", tk.END)

        ts   = datetime.now().strftime("%H:%M:%S")
        tag  = level if level in _LEVEL_COLOURS else "info"
        line = f"[{ts}]  "

        self._textbox.insert(tk.END, line, "timestamp")
        self._textbox.insert(tk.END, message + "\n", tag)

        # Keep the most recent entry visible
        self._textbox.see(tk.END)
        self._textbox.config(state="disabled")
