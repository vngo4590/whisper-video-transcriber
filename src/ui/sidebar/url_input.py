"""
ui/sidebar/url_input.py — Paste-a-URL media source widget.

SRP: Only responsible for collecting a media URL and a fetch mode from the user
     and validating that input locally. It performs no download and does not
     know where files are stored — it delegates upward via *on_fetch*.
GRASP Information Expert: sole authority on the entered URL and the audio-only
     preference, which it persists through the settings module.

Lives beside FilePicker rather than inside it: FilePicker was already at the
project's ~200-line soft limit, so the URL controls are a sibling module.
"""

import tkinter as tk
from tkinter import messagebox

from src.config import settings
from src.media import downloader
from src.media.url_utils import is_playlist_url, is_valid_url
from src.models import DEFAULT_FETCH_MODE, FetchMode
import src.ui.theme as T
from src.ui.sidebar.widgets import card, hover


class UrlInput:
    """
    URL entry + Fetch button + "Audio only" toggle, shown under the FILE section.

    Degrades gracefully: when yt-dlp is missing the controls are disabled and a
    hint explains how to enable them, exactly as drag-and-drop does when
    tkinterdnd2 is absent.

    Args:
        parent:   Container widget inside the sidebar's FILE section.
        on_fetch: Callback ``on_fetch(url, fetch_mode)``, invoked only after the
                  URL has passed local validation.
    """

    def __init__(self, parent: tk.Widget, on_fetch) -> None:
        self._on_fetch = on_fetch
        self._available = downloader.is_available()
        self._url_var = tk.StringVar()
        self._audio_only_var = tk.BooleanVar(
            value=settings.get("fetch_audio_only", DEFAULT_FETCH_MODE is FetchMode.AUDIO_ONLY)
        )
        self._build(parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable the controls while any job is running."""
        state = "disabled" if (busy or not self._available) else "normal"
        self._entry.config(state=state)
        self._audio_checkbox.config(state=state)
        self._fetch_button.config(
            state=state,
            bg=T.C_ACCENT_D if state == "disabled" else T.C_ACCENT,
            cursor="" if state == "disabled" else "hand2",
        )

    def clear(self) -> None:
        """Empty the URL field after a successful fetch."""
        self._url_var.set("")

    # ------------------------------------------------------------------
    # Private — build
    # ------------------------------------------------------------------

    def _build(self, parent: tk.Widget) -> None:
        url_card = card(parent)

        tk.Label(
            url_card, text="or paste a video URL",
            font=T.FONT_SMALL, bg=T.C_CARD, fg=T.C_TEXT_3, anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._entry = tk.Entry(
            url_card, textvariable=self._url_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            insertbackground=T.C_TEXT_1, relief="flat",
            highlightthickness=1, highlightbackground=T.C_BORDER,
            highlightcolor=T.C_ACCENT,
        )
        self._entry.pack(fill="x", ipady=3)
        self._entry.bind("<Return>", self._handle_return)

        self._fetch_button = tk.Button(
            url_card, text="Fetch", command=self._handle_submit,
            font=T.FONT_LABEL, bg=T.C_ACCENT, fg="#ffffff",
            activebackground=T.C_ACCENT_H, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", pady=5,
        )
        self._fetch_button.pack(fill="x", pady=(6, 0))
        hover(self._fetch_button, T.C_ACCENT, T.C_ACCENT_H)

        self._audio_checkbox = tk.Checkbutton(
            url_card, text="Audio only  (faster)", variable=self._audio_only_var,
            font=T.FONT_LABEL, bg=T.C_CARD, fg=T.C_TEXT_1,
            activebackground=T.C_CARD, activeforeground=T.C_TEXT_1,
            selectcolor=T.C_ACCENT, relief="flat", bd=0, cursor="hand2",
            command=self._persist_mode,
        )
        self._audio_checkbox.pack(anchor="w", pady=(4, 0))

        # Downloads and their transcripts share a folder, so the destination
        # decides where every later output for this media is written.
        tk.Label(
            url_card,
            text="Saved to your download folder, alongside its transcript.",
            font=("Segoe UI", 8), bg=T.C_CARD, fg=T.C_TEXT_3,
            anchor="w", justify="left",
            wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
        ).pack(fill="x", pady=(4, 0))

        if not self._available:
            tk.Label(
                url_card,
                text="Unavailable — install yt-dlp to enable:\n  pip install -U yt-dlp",
                font=("Segoe UI", 8), bg=T.C_CARD, fg=T.C_WARN,
                anchor="w", justify="left",
                wraplength=T.SIDEBAR_W - T.PAD_H * 2 - T.PAD_CARD * 2,
            ).pack(fill="x", pady=(4, 0))
            self.set_busy(False)   # applies the permanently disabled state

    # ------------------------------------------------------------------
    # Private — behaviour
    # ------------------------------------------------------------------

    def _persist_mode(self) -> None:
        settings.save(fetch_audio_only=self._audio_only_var.get())

    def _handle_return(self, _event=None) -> str:
        self._handle_submit()
        return "break"

    def _handle_submit(self) -> None:
        if not self._available:
            messagebox.showwarning(
                "Downloader not installed",
                "Fetching from a URL requires yt-dlp.\n\nInstall it with:\n  pip install -U yt-dlp",
            )
            return

        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Paste a video URL first.")
            return
        if not is_valid_url(url):
            messagebox.showwarning(
                "Unsupported URL",
                "That does not look like a video link.\n\n"
                "Paste a full address beginning with http:// or https://",
            )
            return
        if is_playlist_url(url):
            messagebox.showwarning(
                "Playlists are not supported",
                "That link is a playlist. Only single videos can be fetched.\n\n"
                "Open the video you want and paste its own link instead.",
            )
            return

        self._persist_mode()
        mode = FetchMode.AUDIO_ONLY if self._audio_only_var.get() else FetchMode.VIDEO
        self._on_fetch(url, mode)
