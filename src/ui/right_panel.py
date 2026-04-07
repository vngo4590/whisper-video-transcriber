"""
ui/right_panel.py — Right output panel.

SRP: Only responsible for displaying transcript text.
     No knowledge of file I/O, Whisper, or control flow.
"""

import tkinter as tk
from tkinter import scrolledtext


class RightPanel:
    """
    Right-side panel that shows the transcript in a scrollable text box.

    Args:
        parent: tkinter container widget.
    """

    def __init__(self, parent: tk.Widget):
        self._build(parent)

    def set_text(self, text: str) -> None:
        """Replace the current content with *text*."""
        self._textbox.config(state="normal")
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert(tk.END, text)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent)
        panel.pack(side="right", fill="both", expand=True)

        tk.Label(panel, text="Transcription Output:", font=("Arial", 12)).pack(anchor="w")

        self._textbox = scrolledtext.ScrolledText(panel, wrap=tk.WORD, font=("Arial", 10))
        self._textbox.pack(fill="both", expand=True, padx=5, pady=5)
