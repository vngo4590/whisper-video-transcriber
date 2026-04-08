"""
ui/left_panel.py — Left sidebar coordinator.

GRASP Controller: creates FilePicker, TranscribeTab, and VideoClipsTab;
                  wires shared state (selected_path, model_var) between them;
                  owns the scrollable scaffold, progress bar, and header.
Low Coupling: LeftPanel knows nothing about Whisper or Claude — it only
              delegates upward via on_transcribe / on_generate_clips.
"""

import tkinter as tk
from tkinter import ttk

from src.models import DEFAULT_MODEL, WHISPER_MODELS
import src.ui.theme as T
from src.ui.file_picker import FilePicker
from src.ui.sidebar_widgets import card, divider, section_label
from src.ui.transcribe_tab import TranscribeTab
from src.ui.video_clips_tab import VideoClipsTab


class LeftPanel:
    """
    Scrollable left sidebar with two mode tabs: Transcribe and Video Clips.

    Shared state (selected file path, Whisper model) lives here and is
    injected into each tab. LeftPanel never touches Whisper or Claude
    directly — all business logic flows through callbacks.

    Args:
        parent: tkinter container widget.
        on_transcribe: Forwarded verbatim to TranscribeTab.
        on_generate_clips: Forwarded verbatim to VideoClipsTab.
    """

    def __init__(self, parent: tk.Widget, on_transcribe, on_generate_clips) -> None:
        self._selected_path = tk.StringVar()
        self._model_var = tk.StringVar(value=DEFAULT_MODEL)
        self._build(parent, on_transcribe, on_generate_clips)

    # ------------------------------------------------------------------
    # Public API — called by App to reflect processing state
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable or enable all interactive widgets during processing."""
        self._file_picker.set_busy(busy)
        self._transcribe_tab.set_busy(busy)
        self._clips_tab.set_busy(busy)
        self._model_menu.config(state="disabled" if busy else "readonly")

    def show_loading(self, visible: bool) -> None:
        """Toggle the shared progress bar and status label."""
        if visible:
            self._progress_bar.start(12)
            self._loading_label.config(text="Processing…  please wait", fg=T.C_WARN)
        else:
            self._progress_bar.stop()
            self._loading_label.config(text="")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget, on_transcribe, on_generate_clips) -> None:
        container = tk.Frame(parent, bg=T.C_SIDEBAR)
        container.pack(side="left", fill="y")

        scrollbar = ttk.Scrollbar(container, orient="vertical", style="Sidebar.Vertical.TScrollbar")
        canvas = tk.Canvas(container, width=T.SIDEBAR_W, bg=T.C_SIDEBAR, highlightthickness=0, bd=0)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=canvas.yview)
        canvas.pack(side="left", fill="y")
        scrollbar.pack(side="right", fill="y")

        inner = tk.Frame(canvas, bg=T.C_SIDEBAR)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Header
        hdr = tk.Frame(inner, bg=T.C_SIDEBAR)
        hdr.pack(fill="x", padx=T.PAD_H, pady=(18, 10))
        tk.Label(hdr, text="Whisper", font=T.FONT_TITLE, bg=T.C_SIDEBAR, fg=T.C_TEXT_1).pack(anchor="w")
        tk.Label(hdr, text="Video Transcriber", font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_TEXT_2).pack(anchor="w")
        divider(inner)

        # Shared: file picker
        self._file_picker = FilePicker(inner, self._selected_path)

        # Shared: Whisper model (used by both tabs)
        section_label(inner, "WHISPER MODEL")
        mdl_card = card(inner)
        self._model_menu = ttk.Combobox(
            mdl_card, textvariable=self._model_var,
            state="readonly", values=WHISPER_MODELS, style="Dark.TCombobox",
        )
        self._model_menu.pack(fill="x")

        # Mode notebook
        tk.Frame(inner, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(14, 0))
        mode_nb = ttk.Notebook(inner, style="Dark.TNotebook")
        mode_nb.pack(fill="x", padx=T.PAD_H, pady=(8, 0))

        transcribe_frame = tk.Frame(mode_nb, bg=T.C_SIDEBAR)
        clips_frame      = tk.Frame(mode_nb, bg=T.C_SIDEBAR)
        mode_nb.add(transcribe_frame, text="  Transcribe  ")
        mode_nb.add(clips_frame,      text="  Video Clips  ")

        self._transcribe_tab = TranscribeTab(
            transcribe_frame, self._selected_path, self._model_var, on_transcribe
        )
        self._clips_tab = VideoClipsTab(
            clips_frame, self._selected_path, self._model_var, on_generate_clips
        )

        # Shared: progress bar + status label
        prog_frame = tk.Frame(inner, bg=T.C_SIDEBAR)
        prog_frame.pack(fill="x", padx=T.PAD_H, pady=(10, 0))
        self._progress_bar = ttk.Progressbar(
            prog_frame, mode="indeterminate", style="Accent.Horizontal.TProgressbar"
        )
        self._progress_bar.pack(fill="x")
        self._loading_label = tk.Label(
            prog_frame, text="", font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_WARN
        )
        self._loading_label.pack(pady=(4, 0))

        # Footer
        tk.Frame(inner, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(20, 0))
        tk.Label(
            inner, text="Powered by OpenAI Whisper",
            font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_TEXT_3
        ).pack(pady=(6, 16))
