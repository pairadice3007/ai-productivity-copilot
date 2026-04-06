import ctypes
import os
import time
import win32gui
import win32process
import win32api
import psutil
from config import SENSITIVE_APPS


def get_active_window() -> tuple[str, str]:
    """Return (app_name, window_title) for the currently focused window."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid)
            app_name = proc.name().replace(".exe", "")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            app_name = "unknown"
        return app_name, title
    except Exception:
        return "unknown", ""


def get_idle_seconds() -> float:
    """Seconds since the last mouse or keyboard input."""
    try:
        info = win32api.GetLastInputInfo()
        millis = ctypes.windll.kernel32.GetTickCount() - info
        return millis / 1000.0
    except Exception:
        return 0.0


def is_sensitive_app(app_name: str, window_title: str) -> bool:
    combined = (app_name + " " + window_title).lower()
    return any(s in combined for s in SENSITIVE_APPS)
