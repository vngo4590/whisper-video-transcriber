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

from src.config import settings
from src.models import DEFAULT_MODEL, WHISPER_MODELS
import src.ui.theme as T
from src.ui.sidebar.file_picker import FilePicker
from src.ui.sidebar.widgets import card, divider, section_label
from src.ui.sidebar.tabs.transcribe import TranscribeTab
from src.ui.sidebar.tabs.video_clips import VideoClipsTab
from src.ui.sidebar.tabs.content_plan import ContentPlanTab


class LeftPanel:
    """
    Scrollable left sidebar with three mode tabs: Transcribe, Video Clips, Content Plan.

    Shared state (selected file path, Whisper model) lives here and is
    injected into each tab. LeftPanel never touches Whisper or Claude
    directly — all business logic flows through callbacks.

    Args:
        parent: tkinter container widget.
        on_transcribe: Forwarded verbatim to TranscribeTab.
        on_generate_clips: Forwarded verbatim to VideoClipsTab.
        on_generate_plan: Forwarded verbatim to ContentPlanTab.
    """

    def __init__(self, parent: tk.Widget, on_transcribe, on_generate_clips, on_generate_plan) -> None:
        self._selected_path = tk.StringVar()
        self._model_var = tk.StringVar(value=settings.get("whisper_model", DEFAULT_MODEL))
        self._build(parent, on_transcribe, on_generate_clips, on_generate_plan)

    # ------------------------------------------------------------------
    # Public API — called by App to reflect processing state
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable or enable all interactive widgets during processing."""
        self._file_picker.set_busy(busy)
        self._transcribe_tab.set_busy(busy)
        self._clips_tab.set_busy(busy)
        self._plan_tab.set_busy(busy)
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

    def _build(self, parent: tk.Widget, on_transcribe, on_generate_clips, on_generate_plan) -> None:
        # Fill the PanedWindow pane completely.
        container = tk.Frame(parent, bg=T.C_SIDEBAR)
        container.pack(fill="both", expand=True)
        # Stop the container from requesting its children's full content height —
        # without this the inner frame would push the sidebar taller than the
        # window and overflow into the right panel.
        container.pack_propagate(False)

        scrollbar = ttk.Scrollbar(container, orient="vertical", style="Sidebar.Vertical.TScrollbar")
        # No hardcoded width — the canvas fills the pane width via fill="both".
        canvas = tk.Canvas(container, bg=T.C_SIDEBAR, highlightthickness=0, bd=0)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=canvas.yview)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner = tk.Frame(canvas, bg=T.C_SIDEBAR)
        # Update scroll region whenever content height changes.
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _win = canvas.create_window((0, 0), window=inner, anchor="nw")
        # Pin inner frame width to the canvas width so no widget bleeds
        # horizontally beyond the sidebar when the pane is resized.
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(_win, width=e.width))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Only intercept the mousewheel while the cursor is over the sidebar.
        container.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        container.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

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
        self._model_var.trace_add("write", lambda *_: settings.save(whisper_model=self._model_var.get()))

        # Mode notebook
        tk.Frame(inner, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(14, 0))
        mode_nb = ttk.Notebook(inner, style="Dark.TNotebook")
        mode_nb.pack(fill="x", padx=T.PAD_H, pady=(8, 0))

        transcribe_frame = tk.Frame(mode_nb, bg=T.C_SIDEBAR)
        clips_frame      = tk.Frame(mode_nb, bg=T.C_SIDEBAR)
        plan_frame       = tk.Frame(mode_nb, bg=T.C_SIDEBAR)
        mode_nb.add(transcribe_frame, text="  Transcribe  ")
        mode_nb.add(clips_frame,      text="  Video Clips  ")
        mode_nb.add(plan_frame,       text="  Content Plan  ")

        self._transcribe_tab = TranscribeTab(
            transcribe_frame, self._selected_path, self._model_var, on_transcribe
        )
        self._clips_tab = VideoClipsTab(
            clips_frame, self._selected_path, self._model_var, on_generate_clips
        )
        self._plan_tab = ContentPlanTab(
            plan_frame, self._selected_path, self._model_var, on_generate_plan
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
