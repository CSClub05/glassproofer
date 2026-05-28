from __future__ import annotations

import ctypes
import sys


def enable_high_dpi_awareness() -> None:
    """Make the process DPI-aware on Windows before Tk creates a window.

    Without this, Windows may bitmap-scale the whole Tkinter window on
    high-DPI displays, which makes text and controls look blurry.
    """
    if sys.platform != "win32":
        return

    # Windows 10 Anniversary Update+: best option, per-monitor v2 awareness.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass

    # Windows 8.1+: per-monitor awareness.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    # Windows Vista+: system DPI awareness.
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
