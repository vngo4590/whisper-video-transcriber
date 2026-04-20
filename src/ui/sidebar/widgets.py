"""
ui/sidebar/widgets.py — Reusable widget factory helpers for sidebar panels.

Pure layout utilities: no state, no callbacks, no business logic.
Any panel in src/ui/ may import and use them freely.
"""

import tkinter as tk
import src.ui.theme as T


def hover(widget: tk.Widget, normal: str, hot: str) -> None:
    """Bind simple background hover colours to *widget*."""
    widget.bind("<Enter>", lambda _: widget.configure(bg=hot))
    widget.bind("<Leave>", lambda _: widget.configure(bg=normal))


def card(parent: tk.Widget) -> tk.Frame:
    """Return a styled card frame already packed into *parent*."""
    frame = tk.Frame(parent, bg=T.C_CARD, padx=T.PAD_CARD, 
                     pady=T.PAD_CARD)
    frame.pack(fill="x", padx=T.PAD_H)
    return frame


def section_label(parent: tk.Widget, text: str) -> None:
    """Pack a muted uppercase section heading into *parent*."""
    tk.Label(parent, text=text, font=T.FONT_SECTION, bg=T.C_SIDEBAR, fg=T.C_TEXT_3).pack(
        anchor="w", padx=T.PAD_H, pady=(14, T.PAD_SECTION)
    )


def divider(parent: tk.Widget) -> None:
    """Pack a 1 px horizontal rule into *parent*."""
    tk.Frame(parent, bg=T.C_BORDER, height=1).pack(fill="x", padx=T.PAD_H, pady=(0, 4))


def radiobutton(
    parent: tk.Widget,
    text: str,
    value: str,
    variable: tk.StringVar,
) -> tk.Radiobutton:
    """Return a consistently styled radio button tied to *variable*."""
    return tk.Radiobutton(
        parent,
        text=text,
        value=value,
        variable=variable,
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
