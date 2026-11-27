"""Colours and small formatting helpers shared by the UI.

Everything visual reads its colours from PALETTE through C(), so a future
light theme (or accent change) only has to touch this file.
"""

from datetime import datetime, timedelta

from kivy.utils import get_color_from_hex

PALETTE = {
    "bg": "#0E1117",
    "surface": "#161A23",
    "surface_2": "#1E2330",
    "surface_3": "#2A3040",
    "border": "#262C3A",
    "text": "#F3F4F6",
    "text_2": "#A1A8B5",
    "text_3": "#6B7280",
    "accent": "#4F8CFF",
    "success": "#22C55E",
    "danger": "#EF4444",
    "warning": "#F59E0B",
}


def C(name, alpha=None):
    """Return the palette colour `name` as an RGBA list, optionally re-alpha'd."""
    rgba = list(get_color_from_hex(PALETTE[name]))
    if alpha is not None:
        rgba[3] = alpha
    return rgba


def lighten(rgba, amount=0.08):
    """Blend an RGBA colour toward white (used for hover states)."""
    r, g, b, a = rgba
    return [r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount, a]


def fmt_clock(seconds):
    """142 -> '02:22'."""
    seconds = max(0, int(seconds))
    mins, secs = divmod(seconds, 60)
    return f"{mins:02d}:{secs:02d}"


def fmt_duration(seconds):
    """Human duration for summaries: '45s', '12 min', '3 h 5 min'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def fmt_when(iso):
    """ISO timestamp -> 'Today, 14:32' / 'Yesterday, 09:10' / 'Mon 24 Nov, 09:10'."""
    try:
        when = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return "Unknown time"
    today = datetime.now().date()
    if when.date() == today:
        day = "Today"
    elif when.date() == today - timedelta(days=1):
        day = "Yesterday"
    else:
        day = when.strftime("%a %d %b")
        if when.year != today.year:
            day += when.strftime(" %Y")
    return f"{day}, {when.strftime('%H:%M')}"
