"""
ui/app.py — Root window and top-level layout.

GRASP Controller: creates all collaborators, wires callbacks, and
                  routes controller results back to the correct panel.
DIP: App depends on abstract callbacks/interfaces, not on concrete
     widget internals from either panel.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from src.analysis.chapters import generate_chapters
from src.clips.analyzer import ClipAnalyzer
from src.config import settings
from src.controllers.clips import ClipsController
from src.controllers.content_plan import ContentPlanController
from src.controllers.transcription import TranscriptionController
from src.transcription.file_handler import FileHandler
from src.models import ClipResult, DEFAULT_CLAUDE_MODEL, WINDOW_SIZE, WINDOW_TITLE
from src.transcription.service import TranscriptionService
from src.ui.panels.activity_log import ActivityLogPanel
from src.ui.panels.chapters import ChaptersPanel
from src.ui.panels.clips import ClipsPanel
from src.ui.panels.content_plan import ContentPlanPanel
from src.ui.panels.transcript import RightPanel
from src.ui.sidebar.panel import LeftPanel
from src.ui.theme import C_BG, C_BORDER, C_CARD, C_SIDEBAR, C_TEXT_2, SIDEBAR_W, apply_ttk_styles
from src.clips.cutter import VideoCutter

try:
    from tkinterdnd2 import TkinterDnD
    _TK_BASE = TkinterDnD.Tk
except ImportError:
    _TK_BASE = tk.Tk


class App:
    """
    Bootstraps the application window, panels, and services.

    The right side uses a ttk.Notebook with five tabs:
      • Transcript    — transcription output (editable)
      • Clips         — AI-generated viral clip cards
      • Content Plan  — AI content plan
      • Chapters      — AI-generated chapter markers
      • Activity      — live operation log (auto-selected when a job starts)

    A single threading.Event (_cancel_event) is shared across all controllers.
    Clicking Cancel sets it; the active worker checks it between stages.

    Keyboard shortcuts
    ------------------
    Ctrl+Enter  — submit the active sidebar tab's form
    Escape      — cancel the running job (if any)
    Ctrl+Tab    — cycle to the next right-panel tab
    """

    def __init__(self):
        self._root = _TK_BASE()
        self._root.title(WINDOW_TITLE)
        self._root.geometry(WINDOW_SIZE)
        self._root.minsize(640, 480)
        self._root.resizable(True, True)
        self._root.configure(bg=C_BG)

        apply_ttk_styles(self._root)
        self._configure_notebook_style()

        self._cancel_event = threading.Event()
        self._is_busy = False

        self._transcription_controller = TranscriptionController(
            transcription_service=TranscriptionService(),
            file_handler=FileHandler(),
            on_start=self._on_transcribe_start,
            on_success=self._on_transcribe_success,
            on_error=self._on_error,
            on_done=self._on_done,
            on_log=self._on_log,
            on_stage=self._on_transcribe_stage,
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
            on_log=self._on_log,
        )

        self._plan_controller = ContentPlanController(
            on_stage=self._on_plan_stage,
            on_success=self._on_plan_success,
            on_error=self._on_error,
            on_done=self._on_done,
            on_log=self._on_log,
        )

        self._build_layout()
        self._bind_shortcuts()

    def run(self) -> None:
        self._root.mainloop()

    # ------------------------------------------------------------------
    # Private — layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        paned = tk.PanedWindow(
            self._root,
            orient="horizontal",
            bg=C_BORDER,
            sashwidth=5,
            sashpad=0,
            sashrelief="flat",
            borderwidth=0,
            showhandle=False,
        )
        paned.pack(fill="both", expand=True)

        left_frame  = tk.Frame(paned, bg=C_SIDEBAR)
        right_frame = tk.Frame(paned, bg=C_BG)

        paned.add(left_frame,  minsize=180, width=SIDEBAR_W, stretch="never")
        paned.add(right_frame, minsize=300,                  stretch="always")

        self._left = LeftPanel(
            left_frame,
            on_transcribe=self._on_transcribe_requested,
            on_generate_clips=self._on_generate_clips_requested,
            on_generate_plan=self._on_generate_plan_requested,
            on_cancel=self._on_cancel_requested,
        )

        self._notebook = ttk.Notebook(right_frame, style="Dark.TNotebook")
        self._notebook.pack(fill="both", expand=True)

        transcript_tab = tk.Frame(self._notebook, bg=C_BG)
        clips_tab      = tk.Frame(self._notebook, bg=C_BG)
        plan_tab       = tk.Frame(self._notebook, bg=C_BG)
        chapters_tab   = tk.Frame(self._notebook, bg=C_BG)
        activity_tab   = tk.Frame(self._notebook, bg=C_BG)

        self._notebook.add(transcript_tab, text="  Transcript  ")
        self._notebook.add(clips_tab,      text="  Clips  ")
        self._notebook.add(plan_tab,       text="  Content Plan  ")
        self._notebook.add(chapters_tab,   text="  Chapters  ")
        self._notebook.add(activity_tab,   text="  Activity  ")

        self._right      = RightPanel(transcript_tab, on_generate_chapters=self._on_generate_chapters_requested)
        self._clips      = ClipsPanel(clips_tab)
        self._plan_panel = ContentPlanPanel(plan_tab)
        self._chapters   = ChaptersPanel(chapters_tab)
        self._activity   = ActivityLogPanel(activity_tab, self._root)

    # ------------------------------------------------------------------
    # Private — keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        self._root.bind("<Control-Return>", self._shortcut_submit)
        self._root.bind("<Escape>",         self._shortcut_cancel)
        self._root.bind("<Control-Tab>",    self._shortcut_next_tab)

    def _shortcut_submit(self, _event=None) -> None:
        if not self._is_busy:
            self._left.submit_active()

    def _shortcut_cancel(self, _event=None) -> None:
        if self._is_busy:
            self._on_cancel_requested()

    def _shortcut_next_tab(self, _event=None) -> str:
        total = self._notebook.index("end")
        cur   = self._notebook.index("current")
        self._notebook.select((cur + 1) % total)
        return "break"   # prevent default Tk tab traversal

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
    # Private — shared job helpers
    # ------------------------------------------------------------------

    def _start_job(self) -> None:
        self._is_busy = True
        self._cancel_event.clear()
        self._activity.clear()
        self._root.after(0, lambda: self._notebook.select(4))   # Activity tab

    def _on_cancel_requested(self) -> None:
        self._cancel_event.set()

    # ------------------------------------------------------------------
    # Private — transcription callbacks
    # ------------------------------------------------------------------

    def _on_transcribe_requested(
        self, path, model_name, export_format, do_translate, max_words_per_line,
        extract_onscreen=False, ocr_languages=None, diarize=False, hf_token="",
    ):
        self._current_source_path = path
        self._start_job()
        self._transcription_controller.run(
            path, model_name, export_format, do_translate, max_words_per_line,
            extract_onscreen=extract_onscreen,
            ocr_languages=ocr_languages,
            diarize=diarize,
            hf_token=hf_token,
            cancel_event=self._cancel_event,
        )

    def _on_transcribe_start(self):
        self._left.set_busy(True)
        self._left.show_loading(True)

    def _on_transcribe_stage(self, text: str):
        self._root.after(0, lambda: self._left.set_stage(text))

    def _on_transcribe_success(self, text: str, output_path: str):
        self._root.after(0, lambda: self._right.set_text(text, output_path=output_path))
        self._root.after(0, lambda: self._notebook.select(0))
        self._root.after(0, lambda: messagebox.showinfo("Success", f"Transcription saved to:\n{output_path}"))

    # ------------------------------------------------------------------
    # Private — clips callbacks
    # ------------------------------------------------------------------

    def _on_generate_clips_requested(
        self, path, model_name, max_clips, api_key, claude_model,
        clip_mode, aspect_ratio, custom_instructions,
        allow_cut_anywhere, min_segment_duration, prompt_override,
        analysis_strategies,
    ):
        self._start_job()
        self._clips.reset()
        self._clips.set_source_path(path)
        self._clips_controller.run(
            path, model_name, max_clips, api_key, claude_model,
            clip_mode, aspect_ratio, custom_instructions,
            allow_cut_anywhere, min_segment_duration, prompt_override,
            analysis_strategies,
            cancel_event=self._cancel_event,
        )

    def _on_clips_stage(self, text: str):
        self._root.after(0, lambda: self._left.set_stage(text))
        self._root.after(0, lambda: self._clips.set_stage(text))
        self._root.after(0, lambda: self._clips.show_loading(True))

    def _on_clip_done(self, clip: ClipResult):
        self._root.after(0, lambda c=clip: self._clips.add_clip(c))

    def _on_clips_success(self, clips: list[ClipResult]):
        self._root.after(0, lambda: self._clips.show_loading(False))
        self._root.after(0, lambda: self._notebook.select(1))

    # ------------------------------------------------------------------
    # Private — content plan callbacks
    # ------------------------------------------------------------------

    def _on_generate_plan_requested(
        self, path, model_name, api_key, claude_model,
        focus, max_highlights, context, analysis_strategies,
    ):
        self._start_job()
        self._plan_panel.reset()
        self._plan_controller.run(
            path, model_name, api_key, claude_model,
            focus, max_highlights, context, analysis_strategies,
            cancel_event=self._cancel_event,
        )

    def _on_plan_stage(self, text: str):
        self._root.after(0, lambda: self._left.set_stage(text))
        self._root.after(0, lambda: self._plan_panel.set_stage(text))
        self._root.after(0, lambda: self._plan_panel.show_loading(True))

    def _on_plan_success(self, plan_text: str):
        self._root.after(0, lambda: self._plan_panel.set_text(plan_text))
        self._root.after(0, lambda: self._plan_panel.show_loading(False))
        self._root.after(0, lambda: self._notebook.select(2))

    # ------------------------------------------------------------------
    # Private — chapters callbacks
    # ------------------------------------------------------------------

    def _on_generate_chapters_requested(self, transcript_text: str) -> None:
        api_key     = settings.get("api_key", "")
        claude_model = settings.get("claude_model", DEFAULT_CLAUDE_MODEL.model_id)
        if not api_key:
            messagebox.showwarning(
                "API key required",
                "Enter your Anthropic API key in the Video Clips or Content Plan tab and run a job first.",
            )
            return
        self._start_job()
        self._chapters.reset()
        self._chapters.show_loading(True)
        self._left.set_busy(True)
        self._left.show_loading(True)
        self._left.set_stage("Generating chapters with Claude…")
        threading.Thread(
            target=self._chapters_worker,
            args=(transcript_text, api_key, claude_model),
            daemon=True,
        ).start()

    def _chapters_worker(self, transcript: str, api_key: str, claude_model: str) -> None:
        try:
            self._on_log("Generating chapters…", "stage")
            chapters = generate_chapters(
                transcript=transcript,
                api_key=api_key,
                claude_model=claude_model,
                on_log=self._on_log,
            )
            self._on_log(f"Chapters complete — {len(chapters)} chapter(s).", "success")
            self._root.after(0, lambda: self._chapters.set_chapters(chapters))
            self._root.after(0, lambda: self._chapters.show_loading(False))
            self._root.after(0, lambda: self._notebook.select(3))
        except Exception as exc:
            self._on_log(f"Error: {exc}", "error")
            self._root.after(0, lambda: self._chapters.show_loading(False))
            self._root.after(0, lambda: messagebox.showerror("Error", f"Chapter generation failed:\n{exc}"))
        finally:
            self._on_done()

    # ------------------------------------------------------------------
    # Private — shared callbacks
    # ------------------------------------------------------------------

    def _on_log(self, message: str, level: str = "info") -> None:
        self._activity.append(message, level)

    def _on_error(self, message: str):
        if message == "Operation was cancelled.":
            self._root.after(0, lambda: self._activity.append("Operation cancelled by user.", "warn"))
        else:
            self._root.after(0, lambda: messagebox.showerror("Error", f"An error occurred:\n{message}"))

    def _on_done(self):
        self._is_busy = False
        self._root.after(0, lambda: self._left.show_loading(False))
        self._root.after(0, lambda: self._left.set_busy(False))
