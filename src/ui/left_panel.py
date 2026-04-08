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
from tkinter import filedialog, messagebox, ttk

from src import media_utils
from src.models import ASPECT_RATIO_LABELS, CLAUDE_MODELS, CLIP_MODE_LABELS, DEFAULT_ASPECT_RATIO, DEFAULT_CLAUDE_MODEL, DEFAULT_CLIP_MODE, DEFAULT_EXPORT_FORMAT, DEFAULT_MAX_CLIPS, DEFAULT_MAX_WORDS_PER_LINE, DEFAULT_MODEL, MEDIA_FILE_TYPES, WHISPER_MODELS, AspectRatio, ClipMode, ExportFormat
import src.ui.theme as T


def _hover(widget, normal: str, hot: str) -> None:
    """Bind simple bg hover colours to a tk widget."""
    widget.bind("<Enter>", lambda _: widget.configure(bg=hot))
    widget.bind("<Leave>", lambda _: widget.configure(bg=normal))


class LeftPanel:
    """
    Scrollable left sidebar containing file selection, options, and the
    Transcribe button.

    Args:
        parent: tkinter container widget.
        on_transcribe: Callable invoked when the user clicks "Transcribe".
            Signature: ``on_transcribe(path, model_name, export_format,
                                       do_translate, max_words_per_line)``.
    """

    def __init__(self, parent: tk.Widget, on_transcribe, on_generate_clips):
        self._on_transcribe = on_transcribe
        self._on_generate_clips = on_generate_clips
        self._selected_path = tk.StringVar()
        self._export_format_var = tk.StringVar(value=DEFAULT_EXPORT_FORMAT.value)
        self._max_words_var = tk.IntVar(value=DEFAULT_MAX_WORDS_PER_LINE)
        self._translate_var = tk.BooleanVar(value=False)
        self._model_choice = tk.StringVar(value=DEFAULT_MODEL)
        self._max_clips_var    = tk.IntVar(value=DEFAULT_MAX_CLIPS)
        self._api_key_var      = tk.StringVar()
        self._claude_model_var = tk.StringVar(value=DEFAULT_CLAUDE_MODEL.label)
        self._clip_mode_var    = tk.StringVar(value=CLIP_MODE_LABELS[DEFAULT_CLIP_MODE])
        self._aspect_ratio_var = tk.StringVar(value=ASPECT_RATIO_LABELS[DEFAULT_ASPECT_RATIO])

        self._build(parent)

    # ------------------------------------------------------------------
    # Public API used by App to lock / unlock the UI
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable or enable interactive widgets during transcription."""
        btn   = "disabled" if busy else "normal"
        combo = "disabled" if busy else "readonly"

        self._browse_button.config(state=btn)
        self._confirm_button.config(state=btn)
        self._radio_srt.config(state=btn)
        self._radio_plain.config(state=btn)
        self._max_words_spinbox.config(state=btn)
        self._translate_checkbox.config(state=btn)
        self._model_menu.config(state=combo)
        self._clips_button.config(state=btn)
        self._max_clips_spinbox.config(state=btn)
        self._api_key_entry.config(state=btn)
        self._claude_model_menu.config(state=combo)
        self._clip_mode_menu.config(state=combo)
        self._aspect_ratio_menu.config(state=combo)

        if busy:
            self._confirm_button.config(bg=T.C_ACCENT_D, cursor="")
            self._clips_button.config(bg=T.C_ACCENT_D, cursor="")
        else:
            self._confirm_button.config(bg=T.C_ACCENT, cursor="hand2")
            self._clips_button.config(bg=T.C_ACCENT, cursor="hand2")

    def show_loading(self, visible: bool) -> None:
        """Toggle the progress bar and status label."""
        if visible:
            self._progress_bar.start(12)
            self._loading_label.config(text="Transcribing…  please wait", fg=T.C_WARN)
        else:
            self._progress_bar.stop()
            self._loading_label.config(text="")

    # ------------------------------------------------------------------
    # Private — widget construction
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
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

        # ================================================================
        # Header
        # ================================================================
        hdr = tk.Frame(inner, bg=T.C_SIDEBAR)
        hdr.pack(fill="x", padx=T.PAD_H, pady=(18, 10))
        tk.Label(hdr, text="Whisper", font=T.FONT_TITLE, bg=T.C_SIDEBAR, fg=T.C_TEXT_1).pack(anchor="w")
        tk.Label(hdr, text="Video Transcriber", font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_TEXT_2).pack(anchor="w")
        self._divider(inner)

        # ================================================================
        # FILE section
        # ================================================================
        self._section_label(inner, "FILE")
        file_card = self._card(inner)

        self._browse_button = tk.Button(
            file_card, text="Select File", command=self._browse,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_ACCENT, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=10, pady=6,
            highlightthickness=1, highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._browse_button.pack(fill="x")
        _hover(self._browse_button, T.C_CARD, T.C_ACCENT_H)

        self._video_title = tk.Label(
            file_card, text="No file selected", font=T.FONT_SMALL,
            bg=T.C_CARD, fg=T.C_TEXT_2,
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2, anchor="w",
        )
        self._video_title.pack(fill="x", pady=(8, 0))

        self._preview_label = tk.Label(file_card, bg=T.C_CARD)
        self._preview_label.pack(pady=(8, 0))
        self._thumbnail_ref: object = None  # keeps PhotoImage alive (prevents GC)

        # ================================================================
        # EXPORT FORMAT section
        # ================================================================
        self._section_label(inner, "EXPORT FORMAT")
        fmt_card = self._card(inner)

        self._radio_srt = self._radiobutton(fmt_card, text="SRT  (with timestamps)", value=ExportFormat.SRT.value)
        self._radio_srt.pack(anchor="w")

        self._radio_plain = self._radiobutton(fmt_card, text="Plain text", value=ExportFormat.PLAIN_TEXT.value)
        self._radio_plain.pack(anchor="w", pady=(4, 10))

        words_row = tk.Frame(fmt_card, bg=T.C_CARD)
        words_row.pack(fill="x")
        tk.Label(words_row, text="Max words / subtitle", font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._max_words_spinbox = tk.Spinbox(
            words_row, from_=1, to=20, textvariable=self._max_words_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1, highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._max_words_spinbox.pack(side="right")

        # ================================================================
        # OPTIONS section
        # ================================================================
        self._section_label(inner, "OPTIONS")
        opt_card = self._card(inner)

        self._translate_checkbox = tk.Checkbutton(
            opt_card, text="Translate to English", variable=self._translate_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT, relief="flat", bd=0, cursor="hand2",
        )
        self._translate_checkbox.pack(anchor="w")

        # ================================================================
        # MODEL section
        # ================================================================
        self._section_label(inner, "MODEL")
        mdl_card = self._card(inner)

        self._model_menu = ttk.Combobox(
            mdl_card, textvariable=self._model_choice,
            state="readonly", values=WHISPER_MODELS, style="Dark.TCombobox",
        )
        self._model_menu.pack(fill="x")

        # ================================================================
        # Transcribe button
        # ================================================================
        btn_frame = tk.Frame(inner, bg=T.C_SIDEBAR)
        btn_frame.pack(fill="x", padx=T.PAD_H, pady=(16, 0))

        self._confirm_button = tk.Button(
            btn_frame, text="Transcribe", command=self._handle_transcribe,
            font=T.FONT_BUTTON, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=10,
        )
        self._confirm_button.pack(fill="x")
        _hover(self._confirm_button, T.C_ACCENT, T.C_ACCENT_H)

        # ================================================================
        # GENERATE CLIPS section
        # ================================================================
        tk.Frame(inner, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(14, 0))
        self._section_label(inner, "GENERATE CLIPS")
        clips_card = self._card(inner)

        # API key
        tk.Label(clips_card, text="Anthropic API key", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._api_key_entry = tk.Entry(
            clips_card,
            textvariable=self._api_key_var,
            show="•",
            font=T.FONT_LABEL,
            bg=T.C_BG,
            fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1,
            relief="flat",
            highlightthickness=1,
            highlightbackground=T.C_BORDER,
            highlightcolor=T.C_ACCENT,
        )
        self._api_key_entry.pack(fill="x", pady=(4, 10))

        # Claude model selector
        tk.Label(clips_card, text="Claude model", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._claude_model_menu = ttk.Combobox(
            clips_card,
            textvariable=self._claude_model_var,
            state="readonly",
            values=[f"{m.label}  ·  {m.cost_tier}" for m in CLAUDE_MODELS],
            style="Dark.TCombobox",
        )
        self._claude_model_menu.pack(fill="x", pady=(4, 10))

        # Clip mode
        tk.Label(clips_card, text="Clip mode", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._clip_mode_menu = ttk.Combobox(
            clips_card,
            textvariable=self._clip_mode_var,
            state="readonly",
            values=list(CLIP_MODE_LABELS.values()),
            style="Dark.TCombobox",
        )
        self._clip_mode_menu.pack(fill="x", pady=(4, 10))

        # Aspect ratio
        tk.Label(clips_card, text="Aspect ratio", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(anchor="w")
        self._aspect_ratio_menu = ttk.Combobox(
            clips_card,
            textvariable=self._aspect_ratio_var,
            state="readonly",
            values=list(ASPECT_RATIO_LABELS.values()),
            style="Dark.TCombobox",
        )
        self._aspect_ratio_menu.pack(fill="x", pady=(4, 10))

        # Clip count spinbox
        clips_row = tk.Frame(clips_card, bg=T.C_CARD)
        clips_row.pack(fill="x", pady=(0, 10))
        tk.Label(clips_row, text="Number of clips", font=T.FONT_LABEL,
                 bg=T.C_CARD, fg=T.C_TEXT_2).pack(side="left")
        self._max_clips_spinbox = tk.Spinbox(
            clips_row, from_=1, to=10, textvariable=self._max_clips_var, width=4,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            buttonbackground=T.C_BORDER, insertbackground=T.C_TEXT_1,
            relief="flat", highlightthickness=1,
            highlightbackground=T.C_BORDER, highlightcolor=T.C_ACCENT,
        )
        self._max_clips_spinbox.pack(side="right")

        # Generate Clips button
        clips_btn_frame = tk.Frame(inner, bg=T.C_SIDEBAR)
        clips_btn_frame.pack(fill="x", padx=T.PAD_H, pady=(8, 0))
        self._clips_button = tk.Button(
            clips_btn_frame,
            text="Generate Clips",
            command=self._handle_generate_clips,
            font=T.FONT_BUTTON,
            bg=T.C_ACCENT,
            fg="#ffffff",
            activebackground=T.C_ACCENT_H,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=10,
        )
        self._clips_button.pack(fill="x")
        _hover(self._clips_button, T.C_ACCENT, T.C_ACCENT_H)

        # ================================================================
        # Progress / status
        # ================================================================
        prog_frame = tk.Frame(inner, bg=T.C_SIDEBAR)
        prog_frame.pack(fill="x", padx=T.PAD_H, pady=(10, 0))

        self._progress_bar = ttk.Progressbar(prog_frame, mode="indeterminate", style="Accent.Horizontal.TProgressbar")
        self._progress_bar.pack(fill="x")

        self._loading_label = tk.Label(prog_frame, text="", font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_WARN)
        self._loading_label.pack(pady=(4, 0))

        # ================================================================
        # Footer
        # ================================================================
        tk.Frame(inner, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(20, 0))
        tk.Label(inner, text="Powered by OpenAI Whisper", font=T.FONT_SMALL, bg=T.C_SIDEBAR, fg=T.C_TEXT_3).pack(pady=(6, 16))

    # ------------------------------------------------------------------
    # Private — layout helpers
    # ------------------------------------------------------------------

    def _radiobutton(self, parent: tk.Widget, text: str, value: str) -> tk.Radiobutton:
        """Create a consistently styled radio button tied to the export-format variable."""
        return tk.Radiobutton(
            parent,
            text=text,
            value=value,
            variable=self._export_format_var,
            font=T.FONT_LABEL,
            bg=T.C_CARD,
            fg=T.C_TEXT_1,
            activebackground=T.C_CARD,
            activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT,
            relief="flat",
            bd=0,
            cursor="hand2",
        )

    def _divider(self, parent: tk.Widget) -> None:
        tk.Frame(parent, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(0, 4))

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, font=T.FONT_SECTION, bg=T.C_SIDEBAR, fg=T.C_TEXT_3).pack(
            anchor="w", padx=T.PAD_H, pady=(14, T.PAD_SECTION)
        )

    def _card(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=T.C_CARD, padx=T.PAD_CARD, pady=T.PAD_CARD)
        frame.pack(fill="x", padx=T.PAD_H)
        return frame

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
        self._video_title.config(text=os.path.basename(file_path), fg=T.C_TEXT_1)

        if media_utils.is_video(file_path):
            self._update_thumbnail(file_path)
        else:
            self._preview_label.config(image="")

    def _update_thumbnail(self, video_path: str) -> None:
        try:
            img_tk = media_utils.extract_thumbnail(video_path)
            if img_tk:
                self._thumbnail_ref = img_tk  # prevent GC
                self._preview_label.config(image=img_tk)
        except Exception as exc:
            print(f"Thumbnail error: {exc}")

    def _resolve_claude_model_id(self) -> str:
        selected = self._claude_model_var.get()
        for m in CLAUDE_MODELS:
            if selected.startswith(m.label):
                return m.model_id
        return DEFAULT_CLAUDE_MODEL.model_id

    def _resolve_clip_mode(self) -> ClipMode:
        selected = self._clip_mode_var.get()
        for mode, label in CLIP_MODE_LABELS.items():
            if selected == label:
                return mode
        return DEFAULT_CLIP_MODE

    def _resolve_aspect_ratio(self) -> AspectRatio:
        selected = self._aspect_ratio_var.get()
        for ratio, label in ASPECT_RATIO_LABELS.items():
            if selected == label:
                return ratio
        return DEFAULT_ASPECT_RATIO

    def _handle_generate_clips(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a video file first.")
            return
        api_key = self._api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API key required", "Please enter your Anthropic API key.")
            return
        self._on_generate_clips(
            path,
            self._model_choice.get(),
            self._max_clips_var.get(),
            api_key,
            self._resolve_claude_model_id(),
            self._resolve_clip_mode(),
            self._resolve_aspect_ratio(),
        )

    def _handle_transcribe(self) -> None:
        path = self._selected_path.get()
        if not path:
            messagebox.showwarning("No file selected", "Please select a file first.")
            return

        export_format = ExportFormat(self._export_format_var.get())
        self._on_transcribe(
            path,
            self._model_choice.get(),
            export_format,
            self._translate_var.get(),
            self._max_words_var.get(),
        )
