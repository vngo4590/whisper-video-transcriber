"""
ui/theme.py — Dark visual theme: colors, fonts, and ttk style setup.

Import constants directly; call apply_ttk_styles(root) once at startup.
"""

from tkinter import ttk

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
C_BG       = "#0d0e14"   # root / deepest background
C_SIDEBAR  = "#111219"   # left panel background
C_CARD     = "#191b26"   # raised section / input background
C_BORDER   = "#1f2133"   # dividers
C_ACCENT   = "#6c63ff"   # primary accent (soft violet-blue)
C_ACCENT_H = "#5a52d5"   # accent hover
C_ACCENT_D = "#4a43b8"   # accent pressed / active
C_TEXT_1   = "#e2e4f0"   # primary text
C_TEXT_2   = "#7b7f9e"   # secondary / body
C_TEXT_3   = "#3e4158"   # muted labels
C_SUCCESS  = "#50fa7b"
C_ERROR    = "#ff5555"
C_WARN     = "#ffb86c"

# ---------------------------------------------------------------------------
# Typography  (Segoe UI ships with Windows; looks clean at every size)
# ---------------------------------------------------------------------------
FONT_TITLE   = ("Segoe UI", 13, "bold")
FONT_SECTION = ("Segoe UI", 7,  "bold")   # uppercase section labels
FONT_LABEL   = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 8)
FONT_BUTTON  = ("Segoe UI", 11, "bold")
FONT_MONO    = ("Consolas",  10)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
SIDEBAR_W   = 272   # canvas / sidebar pixel width
PAD_H       = 14    # horizontal outer padding inside sidebar
PAD_CARD    = 12    # inner padding inside a card frame
PAD_SECTION = 4     # vertical gap below a section label


# ---------------------------------------------------------------------------
# TTK style setup
# ---------------------------------------------------------------------------

def apply_ttk_styles(root) -> None:
    """Configure all ttk widget styles. Call once after Tk() is created."""
    s = ttk.Style(root)
    s.theme_use("clam")

    # Thin accent progress bar
    s.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor=C_CARD,
        background=C_ACCENT,
        borderwidth=0,
        thickness=4,
    )

    # Dark combobox
    s.configure(
        "Dark.TCombobox",
        fieldbackground=C_CARD,
        background=C_CARD,
        foreground=C_TEXT_1,
        arrowcolor=C_TEXT_2,
        bordercolor=C_BORDER,
        darkcolor=C_CARD,
        lightcolor=C_CARD,
        selectbackground=C_ACCENT,
        selectforeground="#ffffff",
        padding=(8, 6),
    )
    s.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", C_CARD)],
        foreground=[("readonly", C_TEXT_1)],
        arrowcolor=[("disabled", C_TEXT_3)],
    )

    # Sidebar scrollbar (slim, dark)
    s.configure(
        "Sidebar.Vertical.TScrollbar",
        troughcolor=C_SIDEBAR,
        background=C_BORDER,
        bordercolor=C_SIDEBAR,
        arrowcolor=C_TEXT_3,
        relief="flat",
        width=6,
    )
    s.map(
        "Sidebar.Vertical.TScrollbar",
        background=[("active", C_TEXT_3)],
    )

    # Output scrollbar
    s.configure(
        "Output.Vertical.TScrollbar",
        troughcolor=C_BG,
        background=C_BORDER,
        bordercolor=C_BG,
        arrowcolor=C_TEXT_3,
        relief="flat",
        width=8,
    )
    s.map(
        "Output.Vertical.TScrollbar",
        background=[("active", C_TEXT_2)],
    )
