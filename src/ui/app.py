"""
ui/app.py — Root window and top-level layout.

GRASP Controller: creates all collaborators, wires callbacks, and
                  routes controller results back to the correct panel.
DIP: App depends on abstract callbacks/interfaces, not on concrete
     widget internals from either panel.
"""

import tkinter as tk
from tkinter import messagebox

from src.controller import TranscriptionController
from src.file_handler import FileHandler
from src.models import WINDOW_SIZE, WINDOW_TITLE
from src.transcriber import TranscriptionService
from src.ui.left_panel import LeftPanel
from src.ui.right_panel import RightPanel


class App:
    """
    Bootstraps the application window, panels, and services.

    All cross-cutting concerns (error dialogs, UI lock/unlock, progress
    indicator) are coordinated here so that individual panels and services
    remain decoupled from each other.
    """

    def __init__(self):
        self._root = tk.Tk()
        self._root.title(WINDOW_TITLE)
        self._root.geometry(WINDOW_SIZE)
        self._root.resizable(False, False)

        self._controller = TranscriptionController(
            transcription_service=TranscriptionService(),
            file_handler=FileHandler(),
            on_start=self._on_start,
            on_success=self._on_success,
            on_error=self._on_error,
            on_done=self._on_done,
        )

        self._build_layout()

    def run(self) -> None:
        """Enter the tkinter event loop."""
        self._root.mainloop()

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        main_frame = tk.Frame(self._root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self._left = LeftPanel(main_frame, on_transcribe=self._on_transcribe_requested)
        self._right = RightPanel(main_frame)

    # ------------------------------------------------------------------
    # Private — callbacks wired into LeftPanel and Controller
    # ------------------------------------------------------------------

    def _on_transcribe_requested(self, path, model_name, export_format, do_translate, max_words_per_line):
        """Received from LeftPanel; forwarded to the controller."""
        self._controller.run(path, model_name, export_format, do_translate, max_words_per_line)

    def _on_start(self):
        self._left.set_busy(True)
        self._left.show_loading(True)

    def _on_success(self, text: str, output_path: str):
        self._right.set_text(text)
        messagebox.showinfo("Success", f"Transcription saved to:\n{output_path}")

    def _on_error(self, message: str):
        messagebox.showerror("Error", f"An error occurred:\n{message}")

    def _on_done(self):
        self._left.show_loading(False)
        self._left.set_busy(False)
