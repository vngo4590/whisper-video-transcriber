"""
ui/app.py — Root window and top-level layout.

GRASP Controller: creates all collaborators, wires callbacks, and
                  routes controller results back to the correct panel.
DIP: App depends on abstract callbacks/interfaces, not on concrete
     widget internals from either panel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.clip_analyzer import ClipAnalyzer
from src.clips_controller import ClipsController
from src.controller import TranscriptionController
from src.file_handler import FileHandler
from src.models import ClipResult, WINDOW_SIZE, WINDOW_TITLE
from src.transcriber import TranscriptionService
from src.ui.clips_panel import ClipsPanel
from src.ui.left_panel import LeftPanel
from src.ui.right_panel import RightPanel
from src.ui.theme import C_BG, C_BORDER, C_CARD, C_TEXT_2, apply_ttk_styles
from src.video_cutter import VideoCutter


class App:
    """
    Bootstraps the application window, panels, and services.

    The right side uses a ttk.Notebook with two tabs:
      • Transcript — existing transcription output
      • Clips      — AI-generated viral clip cards
    """

    def __init__(self):
        self._root = tk.Tk()
        self._root.title(WINDOW_TITLE)
        self._root.geometry(WINDOW_SIZE)
        self._root.resizable(False, False)
        self._root.configure(bg=C_BG)

        apply_ttk_styles(self._root)
        self._configure_notebook_style()

        self._transcription_controller = TranscriptionController(
            transcription_service=TranscriptionService(),
            file_handler=FileHandler(),
            on_start=self._on_transcribe_start,
            on_success=self._on_transcribe_success,
            on_error=self._on_error,
            on_done=self._on_done,
        )

        self._clips_controller = ClipsController(
            transcription_service=TranscriptionService(),
            clip_analyzer=ClipAnalyzer(),
            video_cutter=VideoCutter(),
            on_stage=self._on_clips_stage,
            on_clip_done=self._on_clip_done,
            on_success=self._on_clips_success,
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
        main_frame = tk.Frame(self._root, bg=C_BG)
        main_frame.pack(fill="both", expand=True)

        self._left = LeftPanel(
            main_frame,
            on_transcribe=self._on_transcribe_requested,
            on_generate_clips=self._on_generate_clips_requested,
        )

        # 1px vertical divider
        tk.Frame(main_frame, bg=C_BORDER, width=1).pack(side="left", fill="y")

        # Right side: tabbed notebook
        right_frame = tk.Frame(main_frame, bg=C_BG)
        right_frame.pack(side="right", fill="both", expand=True)

        self._notebook = ttk.Notebook(right_frame, style="Dark.TNotebook")
        self._notebook.pack(fill="both", expand=True)

        transcript_tab = tk.Frame(self._notebook, bg=C_BG)
        clips_tab = tk.Frame(self._notebook, bg=C_BG)

        self._notebook.add(transcript_tab, text="  Transcript  ")
        self._notebook.add(clips_tab,      text="  Clips  ")

        self._right = RightPanel(transcript_tab)
        self._clips = ClipsPanel(clips_tab)

    # ------------------------------------------------------------------
    # Private — ttk notebook dark style
    # ------------------------------------------------------------------

    def _configure_notebook_style(self) -> None:
        s = ttk.Style(self._root)
        s.configure(
            "Dark.TNotebook",
            background=C_BG,
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )
        s.configure(
            "Dark.TNotebook.Tab",
            background=C_CARD,
            foreground=C_TEXT_2,
            padding=[12, 6],
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        s.map(
            "Dark.TNotebook.Tab",
            background=[("selected", C_BG)],
            foreground=[("selected", "#ffffff")],
        )

    # ------------------------------------------------------------------
    # Private — transcription callbacks
    # ------------------------------------------------------------------

    def _on_transcribe_requested(self, path, model_name, export_format, do_translate, max_words_per_line):
        self._transcription_controller.run(path, model_name, export_format, do_translate, max_words_per_line)

    def _on_transcribe_start(self):
        # Called from the main thread (controller calls on_start before spawning thread)
        self._left.set_busy(True)
        self._left.show_loading(True)

    def _on_transcribe_success(self, text: str, output_path: str):
        # Called from background thread — marshal to main thread
        self._root.after(0, lambda: self._right.set_text(text))
        self._root.after(0, lambda: self._notebook.select(0))
        self._root.after(0, lambda: messagebox.showinfo("Success", f"Transcription saved to:\n{output_path}"))

    # ------------------------------------------------------------------
    # Private — clips callbacks
    # ------------------------------------------------------------------

    def _on_generate_clips_requested(self, path, model_name, max_clips, api_key, claude_model, clip_mode, aspect_ratio):
        self._clips.reset()
        self._notebook.select(1)
        self._clips_controller.run(path, model_name, max_clips, api_key, claude_model, clip_mode, aspect_ratio)

    def _on_clips_stage(self, text: str):
        # Callbacks arrive from a background thread — use after() to be thread-safe
        self._root.after(0, lambda: self._clips.set_stage(text))
        self._root.after(0, lambda: self._clips.show_loading(True))

    def _on_clip_done(self, clip: ClipResult):
        self._root.after(0, lambda c=clip: self._clips.add_clip(c))

    def _on_clips_success(self, clips: list[ClipResult]):
        self._root.after(0, lambda: self._clips.show_loading(False))

    # ------------------------------------------------------------------
    # Private — shared callbacks
    # ------------------------------------------------------------------

    def _on_error(self, message: str):
        self._root.after(0, lambda: messagebox.showerror("Error", f"An error occurred:\n{message}"))

    def _on_done(self):
        self._root.after(0, lambda: self._left.show_loading(False))
        self._root.after(0, lambda: self._left.set_busy(False))
