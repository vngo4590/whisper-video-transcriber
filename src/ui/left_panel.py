"""
ui/left_panel.py — Left sidebar panel.

SRP: Owns and manages all left-panel widgets. Does NOT drive transcription
     logic — it delegates via the *on_transcribe* callback (Low Coupling).
GRASP Information Expert: the panel is the expert on its own widget state
     (selected path, model choice, checkbox values) and reads that state
     when handing control to the controller.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from src import media_utils
from src.models import (
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_MODEL,
    MEDIA_FILE_TYPES,
    WHISPER_MODELS,
    ExportFormat,
)


class LeftPanel:
    """
    Scrollable left sidebar containing file selection, options, and the
    Transcribe button.

    Args:
        parent: tkinter container widget.
        on_transcribe: Callable invoked when the user clicks "Transcribe".
            Signature: ``on_transcribe(path, model_name, export_format, do_translate)``.
    """

    def __init__(self, parent: tk.Widget, on_transcribe):
        self._on_transcribe = on_transcribe
        self._selected_path = tk.StringVar()
        self._export_format_var = tk.StringVar(value=DEFAULT_EXPORT_FORMAT.value)
        self._translate_var = tk.BooleanVar(value=False)
        self._model_choice = tk.StringVar(value=DEFAULT_MODEL)

        self._build(parent)

    # ------------------------------------------------------------------
    # Public API used by App to lock / unlock the UI
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable or enable interactive widgets during transcription."""
        state_button = "disabled" if busy else "normal"
        state_combo = "disabled" if busy else "readonly"

        self._confirm_button.config(state=state_button)
        self._browse_button.config(state=state_button)
        self._model_menu.config(state=state_combo)
        self._radio_srt.config(state=state_button)
        self._radio_plain.config(state=state_button)
        self._translate_checkbox.config(state=state_button)

    def show_loading(self, visible: bool) -> None:
        """Toggle the progress bar and status label."""
        if visible:
            self._progress_bar.start()
            self._loading_label.config(text="Loading… Please wait.")
        else:
            self._progress_bar.stop()
            self._loading_label.config(text="")

    # ------------------------------------------------------------------
    # Private — widget construction
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        container = tk.Frame(parent)
        container.pack(side="left", fill="y")

        canvas = tk.Canvas(container, width=260)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="y")
        scrollbar.pack(side="right", fill="y")

        # ---- widgets ----
        tk.Label(
            inner,
            text="Drop or Select your video or audio file to transcribe",
            font=("Arial", 12),
            wraplength=200,
        ).pack(pady=10)

        self._browse_button = tk.Button(
            inner, text="Select Video", command=self._browse, font=("Arial", 11)
        )
        self._browse_button.pack(pady=5)

        self._video_title = tk.Label(
            inner, text="No video selected", font=("Arial", 10), wraplength=200, fg="blue"
        )
        self._video_title.pack(pady=5)

        self._preview_label = tk.Label(inner)
        self._preview_label.pack(pady=5)

        tk.Label(inner, text="Export format:", font=("Arial", 10)).pack(pady=(8, 0))

        self._radio_srt = tk.Radiobutton(
            inner,
            text="SRT (with timestamps)",
            variable=self._export_format_var,
            value=ExportFormat.SRT.value,
            font=("Arial", 10),
        )
        self._radio_srt.pack(anchor="w", padx=20)

        self._radio_plain = tk.Radiobutton(
            inner,
            text="Plain text",
            variable=self._export_format_var,
            value=ExportFormat.PLAIN_TEXT.value,
            font=("Arial", 10),
        )
        self._radio_plain.pack(anchor="w", padx=20, pady=(0, 4))

        self._translate_checkbox = tk.Checkbutton(
            inner, text="Translate to English", variable=self._translate_var, font=("Arial", 10)
        )
        self._translate_checkbox.pack(pady=2)

        tk.Label(inner, text="Select Model:", font=("Arial", 10)).pack(pady=5)

        self._model_menu = ttk.Combobox(
            inner,
            textvariable=self._model_choice,
            state="readonly",
            values=WHISPER_MODELS,
        )
        self._model_menu.pack()

        self._confirm_button = tk.Button(
            inner, text="Transcribe", command=self._handle_transcribe, font=("Arial", 11)
        )
        self._confirm_button.pack(pady=10)

        self._progress_bar = ttk.Progressbar(inner, mode="indeterminate")
        self._progress_bar.pack(pady=5, fill="x")

        self._loading_label = tk.Label(inner, text="", font=("Arial", 9), fg="red")
        self._loading_label.pack()

        tk.Label(inner, text="Powered by Whisper", font=("Arial", 9), fg="gray").pack(
            side="bottom", pady=10
        )

    # ------------------------------------------------------------------
    # Private — event handlers
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select a video or audio file",
            filetypes=MEDIA_FILE_TYPES,
        )
        if not file_path:
            return

        self._selected_path.set(file_path)
        self._video_title.config(text=os.path.basename(file_path))

        if media_utils.is_video(file_path):
            self._update_thumbnail(file_path)
        else:
            self._preview_label.config(image="")

    def _update_thumbnail(self, video_path: str) -> None:
        try:
            img_tk = media_utils.extract_thumbnail(video_path)
            if img_tk:
                self._preview_label.img = img_tk  # prevent GC
                self._preview_label.config(image=img_tk)
        except Exception as exc:
            print(f"Thumbnail error: {exc}")

    def _handle_transcribe(self) -> None:
        path = self._selected_path.get()
        if not path:
            from tkinter import messagebox
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return

        export_format = ExportFormat(self._export_format_var.get())
        self._on_transcribe(
            path,
            self._model_choice.get(),
            export_format,
            self._translate_var.get(),
        )
