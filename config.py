import os
from pathlib import Path

SCREENSHOT_INTERVAL = int(os.getenv("SCREENSHOT_INTERVAL", 45))  # seconds between cycles
DIFF_THRESHOLD = 0.05         # fraction of pixels changed to trigger API call
IDLE_THRESHOLD_SECONDS = 300  # 5 minutes of no input → auto-pause
ACTIVITY_LOG_CONTEXT = 5      # number of recent log entries sent to Claude

CLAUDE_MODEL = "claude-sonnet-4-6"

DB_PATH = Path.home() / ".copilot_sessions.db"
LOCK_FILE = Path.home() / ".copilot.lock"

NUDGE_WIDTH = 320
NUDGE_HEIGHT = 190

# ── Design system: AI-Native Minimalism + OLED Dark (Developer Tool / Timer palette) ──
# Style source: ui-ux-pro-max — Row 18 (AI/Chatbot) + Row 81 (Developer Tool)
COLORS = {
    "productive": "#22C55E",   # action green
    "drift":      "#EF4444",   # destructive red
    "break":      "#F59E0B",   # amber
    "unknown":    "#6366F1",   # AI purple
}

BG_COLOR     = "#0F172A"   # OLED dark (slate-950)
SURFACE_COLOR = "#1E293B"  # card surface (slate-800)
SURFACE_2    = "#334155"   # elevated surface / hover (slate-700)
BORDER_COLOR = "#334155"   # subtle border
FG_COLOR     = "#F8FAFC"   # primary text (slate-50)
DIM_COLOR    = "#94A3B8"   # muted text (slate-400)
ACCENT_COLOR = "#6366F1"   # AI purple accent

# Typography: Segoe UI (Inter equivalent on Windows) + Consolas (JetBrains Mono equivalent)
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_LABEL = ("Segoe UI", 9, "bold")
FONT_MONO  = ("Consolas", 9)       # clock, task name
FONT_NUDGE = ("Segoe UI", 10)

SENSITIVE_APPS = [
    "1password", "keepass", "keepassxc", "bitwarden",
    "signal", "whatsapp",
    "banking", "chase", "wellsfargo", "bankofamerica",
]
