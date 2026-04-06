"""
UI module — AI Co-Pilot
Design system: AI-Native Minimalism + OLED Dark
Style source: ui-ux-pro-max (Row 18 AI/Chatbot + Row 81 Developer Tool)
Color palette: slate-950 bg, slate-800 surfaces, AI purple accent, status-semantic colors
Typography: Segoe UI (Inter equivalent) + Consolas (monospace)
"""
import tkinter as tk
from datetime import datetime
import threading
import pystray
from PIL import Image, ImageDraw
import database as db
import time_tracker
import claude_client
from config import (
    NUDGE_WIDTH, NUDGE_HEIGHT,
    COLORS, BG_COLOR, SURFACE_COLOR, SURFACE_2, BORDER_COLOR,
    FG_COLOR, DIM_COLOR, ACCENT_COLOR,
    FONT_BODY, FONT_SMALL, FONT_LABEL, FONT_MONO, FONT_NUDGE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _btn(parent, text, command, fg=None, bg=None, padx=8, pady=3, **kw):
    """Flat button with hover state — 150ms micro-interaction feel via config."""
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg or SURFACE_COLOR, fg=fg or DIM_COLOR,
        activebackground=SURFACE_2, activeforeground=FG_COLOR,
        relief="flat", bd=0, cursor="hand2",
        font=FONT_SMALL, padx=padx, pady=pady, **kw,
    )
    b.bind("<Enter>", lambda e: b.config(bg=SURFACE_2, fg=FG_COLOR))
    b.bind("<Leave>", lambda e: b.config(bg=bg or SURFACE_COLOR, fg=fg or DIM_COLOR))
    return b


def _label(parent, text="", fg=None, font=None, **kw):
    return tk.Label(parent, text=text, bg=BG_COLOR, fg=fg or FG_COLOR,
                    font=font or FONT_BODY, **kw)


def _surface_label(parent, text="", fg=None, font=None, bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or SURFACE_COLOR,
                    fg=fg or FG_COLOR, font=font or FONT_BODY, **kw)


# ── Startup dialog ────────────────────────────────────────────────────────────

def show_startup_dialog(root: tk.Tk):
    """Returns (tasks: list[str], next_commitment: str) or None if cancelled."""
    result = {"value": None}

    dlg = tk.Toplevel(root)
    dlg.title("AI Co-Pilot")
    dlg.resizable(False, False)
    dlg.configure(bg=BG_COLOR)
    dlg.grab_set()

    W, H = 420, 460
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(dlg, bg=SURFACE_COLOR, height=48)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="AI Co-Pilot", bg=SURFACE_COLOR, fg=FG_COLOR,
             font=("Segoe UI", 13, "bold"), anchor="w", padx=16).pack(side="left", fill="y")
    tk.Label(hdr, text="Start your day", bg=SURFACE_COLOR, fg=DIM_COLOR,
             font=FONT_SMALL, anchor="e", padx=16).pack(side="right", fill="y")

    body = tk.Frame(dlg, bg=BG_COLOR)
    body.pack(fill="both", expand=True, padx=20, pady=16)

    # ── Tasks ─────────────────────────────────────────────────────────────────
    tk.Label(body, text="TODAY'S TASKS", bg=BG_COLOR, fg=DIM_COLOR,
             font=("Segoe UI", 7, "bold"), anchor="w").pack(fill="x")

    task_outer = tk.Frame(body, bg=BORDER_COLOR, pady=1, padx=1)
    task_outer.pack(fill="x", expand=False, pady=(4, 12))
    task_inner = tk.Frame(task_outer, bg=SURFACE_COLOR)
    task_inner.pack(fill="x", expand=False)

    task_scroll = tk.Scrollbar(task_inner, bg=SURFACE_COLOR, troughcolor=SURFACE_COLOR,
                                activebackground=SURFACE_2, relief="flat", bd=0, width=8)
    task_scroll.pack(side="right", fill="y")
    task_text = tk.Text(
        task_inner, yscrollcommand=task_scroll.set,
        bg=SURFACE_COLOR, fg=FG_COLOR, insertbackground=ACCENT_COLOR,
        selectbackground=ACCENT_COLOR, selectforeground=FG_COLOR,
        relief="flat", bd=0, padx=10, pady=8,
        font=FONT_BODY, wrap="word", height=7,
    )
    task_text.pack(fill="both", expand=True)
    task_scroll.config(command=task_text.yview)
    task_text.insert("1.0", "e.g. Write project proposal\nReview pull requests\n")
    task_text.config(fg=DIM_COLOR)

    def _clear_placeholder(e):
        if task_text.cget("fg") == DIM_COLOR:
            task_text.delete("1.0", "end")
            task_text.config(fg=FG_COLOR)
    task_text.bind("<FocusIn>", _clear_placeholder)

    # ── Commitment ────────────────────────────────────────────────────────────
    tk.Label(body, text="NEXT COMMITMENT", bg=BG_COLOR, fg=DIM_COLOR,
             font=("Segoe UI", 7, "bold"), anchor="w").pack(fill="x")

    commit_outer = tk.Frame(body, bg=BORDER_COLOR, pady=1, padx=1)
    commit_outer.pack(fill="x", pady=(4, 16))
    commit_var = tk.StringVar()
    tk.Entry(
        commit_outer, textvariable=commit_var,
        bg=SURFACE_COLOR, fg=FG_COLOR, insertbackground=ACCENT_COLOR,
        selectbackground=ACCENT_COLOR, relief="flat", bd=0,
        font=FONT_BODY,
    ).pack(fill="x", ipady=7, padx=1)

    # ── Privacy note ──────────────────────────────────────────────────────────
    tk.Label(body, text="Screenshots are sent to Claude API · Nothing stored on disk",
             bg=BG_COLOR, fg=DIM_COLOR, font=("Segoe UI", 7), anchor="w").pack(fill="x")

    # ── Start button ──────────────────────────────────────────────────────────
    def on_start():
        raw = task_text.get("1.0", "end").strip()
        tasks = [t.strip() for t in raw.splitlines()
                 if t.strip() and t.strip() != "e.g. Write project proposal" and t.strip() != "Review pull requests"]
        result["value"] = (tasks, commit_var.get().strip())
        dlg.destroy()

    start_btn = tk.Button(
        body, text="Start Monitoring →", command=on_start,
        bg=ACCENT_COLOR, fg=FG_COLOR,
        activebackground="#4F46E5", activeforeground=FG_COLOR,
        relief="flat", bd=0, cursor="hand2",
        font=("Segoe UI", 10, "bold"), pady=9,
    )
    start_btn.pack(fill="x", pady=(8, 0))

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    root.wait_window(dlg)
    return result["value"]


# ── Nudge window ──────────────────────────────────────────────────────────────

class NudgeWindow:

    def __init__(self, root: tk.Tk, state, conn, session_id: int,
                 on_correct, on_pause, on_quit):
        self.root = root
        self.state = state
        self.conn = conn
        self.session_id = session_id
        self._on_quit = on_quit
        self._session_start = datetime.now()
        self._current_category = "unknown"
        self._drag_x = self._drag_y = 0
        self._blink_phase = True

        self._build()
        self._start_clock()
        self._pulse_indicator()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = self.root
        root.overrideredirect(True)
        root.wm_attributes("-topmost", True)
        root.configure(bg=BG_COLOR)

        # Transparent-border effect: 1px border via wrapping frame
        outer = tk.Frame(root, bg=BORDER_COLOR, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=BG_COLOR)
        inner.pack(fill="both", expand=True)

        # Position: bottom-right, 20px margin
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{NUDGE_WIDTH}x{NUDGE_HEIGHT}+{sw - NUDGE_WIDTH - 20}+{sh - NUDGE_HEIGHT - 60}")

        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(inner, bg=SURFACE_COLOR, height=28)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        title_bar.bind("<Button-1>", self._drag_start)
        title_bar.bind("<B1-Motion>", self._drag_move)

        # Indicator dot
        self._indicator = tk.Label(title_bar, text="●", bg=SURFACE_COLOR,
                                   fg=COLORS["unknown"], font=("Segoe UI", 8))
        self._indicator.pack(side="left", padx=(10, 4))
        self._indicator.bind("<Button-1>", self._drag_start)
        self._indicator.bind("<B1-Motion>", self._drag_move)

        tk.Label(title_bar, text="AI CO-PILOT", bg=SURFACE_COLOR, fg=DIM_COLOR,
                 font=("Segoe UI", 7, "bold")).pack(side="left")

        # Window controls
        _btn(title_bar, "×", self._on_quit, fg=DIM_COLOR, bg=SURFACE_COLOR,
             padx=8, pady=0).pack(side="right", fill="y")
        _btn(title_bar, "−", self._minimize, fg=DIM_COLOR, bg=SURFACE_COLOR,
             padx=8, pady=0).pack(side="right", fill="y")

        # ── Category accent strip (left edge, 3px wide) ───────────────────────
        self._accent_strip = tk.Frame(inner, bg=COLORS["unknown"], width=3)
        self._accent_strip.pack(side="left", fill="y")

        # ── Main content ──────────────────────────────────────────────────────
        content = tk.Frame(inner, bg=BG_COLOR)
        content.pack(side="left", fill="both", expand=True)

        # Nudge text
        self._nudge_label = tk.Label(
            content, text="Initializing…",
            wraplength=NUDGE_WIDTH - 36,
            bg=BG_COLOR, fg=FG_COLOR,
            font=FONT_NUDGE, justify="left", anchor="nw",
            padx=10, pady=8,
        )
        self._nudge_label.pack(fill="both", expand=True)

        # ── Status bar ────────────────────────────────────────────────────────
        status = tk.Frame(content, bg=SURFACE_COLOR, height=22)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)

        self._task_label = tk.Label(status, text="—",
                                    bg=SURFACE_COLOR, fg=DIM_COLOR,
                                    font=FONT_MONO, anchor="w", padx=8)
        self._task_label.pack(side="left")

        self._clock_label = tk.Label(status, text="00:00:00",
                                     bg=SURFACE_COLOR, fg=DIM_COLOR,
                                     font=FONT_MONO, anchor="e", padx=8)
        self._clock_label.pack(side="right")

        # ── Button row 1: primary actions ─────────────────────────────────────
        btn_row = tk.Frame(content, bg=BG_COLOR)
        btn_row.pack(fill="x", padx=6, pady=(0, 2))

        self._pause_btn = _btn(btn_row, "⏸ Pause", self._toggle_pause,
                               fg=DIM_COLOR, padx=6)
        self._pause_btn.pack(side="left", padx=(0, 3))

        self._away_btn = _btn(btn_row, "🏃 Away", self._toggle_away,
                              fg=DIM_COLOR, padx=6)
        self._away_btn.pack(side="left", padx=3)

        _btn(btn_row, "∑ Summary", self._show_summary,
             fg=DIM_COLOR, padx=6).pack(side="left", padx=3)

        self._chat_btn = _btn(btn_row, "💬", self._toggle_chat,
                               fg=DIM_COLOR, padx=6)
        self._chat_btn.pack(side="left", padx=3)

        # ── Button row 2: task actions ─────────────────────────────────────────
        btn_row2 = tk.Frame(content, bg=BG_COLOR)
        btn_row2.pack(fill="x", padx=6, pady=(0, 6))

        _btn(btn_row2, "＋ Task", self._add_task,
             fg=DIM_COLOR, padx=6).pack(side="left", padx=(0, 3))

        self._correct_btn = _btn(btn_row2, "✎ Switch", self._show_correction,
                                  fg=DIM_COLOR, padx=6)
        self._correct_btn.pack(side="left", padx=3)

        self._done_btn = _btn(btn_row2, "✓ Done", self._mark_done,
                              fg=COLORS["productive"], padx=6)
        self._done_btn.pack(side="right")

        # ── Chat panel (hidden by default) ────────────────────────────────────
        self._chat_frame = tk.Frame(content, bg=SURFACE_COLOR)

        chat_input_row = tk.Frame(self._chat_frame, bg=SURFACE_COLOR)
        chat_input_row.pack(fill="x", padx=6, pady=4)

        self._chat_entry = tk.Entry(
            chat_input_row, bg=SURFACE_2, fg=FG_COLOR,
            insertbackground=ACCENT_COLOR, relief="flat",
            font=FONT_BODY,
        )
        self._chat_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 4))
        self._chat_entry.bind("<Return>", lambda e: self._send_chat())

        self._send_btn = _btn(chat_input_row, "→", self._send_chat,
                               fg=ACCENT_COLOR, bg=SURFACE_2, padx=8)
        self._send_btn.pack(side="right")

        self._chat_visible = False

        # ── All-edge resize handles ────────────────────────────────────────────
        self._add_resize_handles(root)

        # ── Tray icon ──────────────────────────────────────────────────────────
        self._tray_icon = None
        self._build_tray()

    # ── Thread-safe UI update ─────────────────────────────────────────────────

    def update_nudge(self, task: str, category: str, nudge: str, indicator: str):
        self.root.after(0, lambda: self._apply(task, category, nudge, indicator))

    def _apply(self, task: str, category: str, nudge: str, indicator: str):
        self._current_category = category
        cat_color = COLORS.get(category, COLORS["unknown"])

        # Accent strip color = category
        self._accent_strip.config(bg=cat_color)

        # Nudge text — color signals urgency
        nudge_fg = FG_COLOR if category in ("productive", "unknown") else cat_color
        self._nudge_label.config(text=nudge, fg=nudge_fg)

        # Task in status bar
        short = task if task and task != "none" else "—"
        self._task_label.config(text=short)

        # Correct button tooltip
        self._correct_btn.config(
            text="✎" if short == "—" else f"✎ {short[:14]}{'…' if len(short) > 14 else ''}"
        )

        # Indicator state
        ind_states = {
            "monitoring": (cat_color,           "●"),
            "paused":     (DIM_COLOR,            "⏸"),
            "idle":       (DIM_COLOR,            "○"),
            "away":       (COLORS["break"],      "🏃"),
            "sensitive":  (COLORS["drift"],      "▪"),
            "error":      (COLORS["drift"],      "✕"),
        }
        fg, sym = ind_states.get(indicator, (cat_color, "●"))
        self._indicator.config(text=sym, fg=fg)

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _start_clock(self):
        def tick():
            elapsed = datetime.now() - self._session_start
            h, rem = divmod(int(elapsed.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            self._clock_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.root.after(1000, tick)
        tick()

    # ── Pulsing indicator (200ms period — AI-Native style) ────────────────────

    def _pulse_indicator(self):
        def pulse():
            if not self.state.is_paused and not self.state.is_snoozed():
                cat_color = COLORS.get(self._current_category, COLORS["unknown"])
                dim = _darken(cat_color)
                self._indicator.config(fg=cat_color if self._blink_phase else dim)
                self._blink_phase = not self._blink_phase
            self.root.after(1200, pulse)
        pulse()

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ── Controls ──────────────────────────────────────────────────────────────

    # ── Tray icon ─────────────────────────────────────────────────────────────

    def _build_tray(self):
        # Draw a simple purple circle icon
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 60, 60], fill="#6366F1")
        d.ellipse([20, 20, 44, 44], fill="#22C55E")

        menu = pystray.Menu(
            pystray.MenuItem("Show AI Co-Pilot", self._tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self._tray_icon = pystray.Icon("AI Co-Pilot", img, "AI Co-Pilot", menu)

    def _minimize(self):
        """Hide window and show system tray icon."""
        self.root.withdraw()
        if self._tray_icon and not self._tray_icon.visible:
            threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _tray_show(self, icon=None, item=None):
        """Restore window from tray."""
        if self._tray_icon:
            self._tray_icon.stop()
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.wm_attributes("-topmost", True)

    def _tray_quit(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
        self.root.after(0, self._on_quit)

    # ── All-edge resize ───────────────────────────────────────────────────────

    def _add_resize_handles(self, root):
        """Add invisible 5px drag handles on all 8 edges/corners."""
        B = 5  # border thickness
        handles = {
            "n":  dict(cursor="size_ns",     relx=0,   rely=0,   relwidth=1,   height=B,  anchor="nw"),
            "s":  dict(cursor="size_ns",     relx=0,   rely=1,   relwidth=1,   height=B,  anchor="sw"),
            "e":  dict(cursor="size_we",     relx=1,   rely=0,   width=B,      relheight=1, anchor="ne"),
            "w":  dict(cursor="size_we",     relx=0,   rely=0,   width=B,      relheight=1, anchor="nw"),
            "ne": dict(cursor="size_ne_sw",  relx=1,   rely=0,   width=B*2,    height=B*2,  anchor="ne"),
            "nw": dict(cursor="size_nw_se",  relx=0,   rely=0,   width=B*2,    height=B*2,  anchor="nw"),
            "se": dict(cursor="size_nw_se",  relx=1,   rely=1,   width=B*2,    height=B*2,  anchor="se"),
            "sw": dict(cursor="size_ne_sw",  relx=0,   rely=1,   width=B*2,    height=B*2,  anchor="sw"),
        }
        for direction, opts in handles.items():
            h = tk.Frame(root, bg=BG_COLOR, cursor=opts["cursor"])
            place_kw = {k: v for k, v in opts.items() if k != "cursor"}
            h.place(**place_kw)
            h.bind("<Button-1>",  lambda e, d=direction: self._resize_start(e, d))
            h.bind("<B1-Motion>", lambda e, d=direction: self._resize_drag(e, d))

    def _resize_start(self, event, direction):
        self._rsz_dir  = direction
        self._rsz_x0   = event.x_root
        self._rsz_y0   = event.y_root
        self._rsz_w0   = self.root.winfo_width()
        self._rsz_h0   = self.root.winfo_height()
        self._rsz_wx0  = self.root.winfo_x()
        self._rsz_wy0  = self.root.winfo_y()

    def _resize_drag(self, event, direction):
        dx = event.x_root - self._rsz_x0
        dy = event.y_root - self._rsz_y0
        w, h = self._rsz_w0, self._rsz_h0
        x, y = self._rsz_wx0, self._rsz_wy0
        MIN_W, MIN_H = 280, 180

        if "e" in direction:  w = max(MIN_W, self._rsz_w0 + dx)
        if "s" in direction:  h = max(MIN_H, self._rsz_h0 + dy)
        if "w" in direction:
            w = max(MIN_W, self._rsz_w0 - dx)
            x = self._rsz_wx0 + self._rsz_w0 - w
        if "n" in direction:
            h = max(MIN_H, self._rsz_h0 - dy)
            y = self._rsz_wy0 + self._rsz_h0 - h

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self._nudge_label.config(wraplength=w - 36)

    def _toggle_pause(self):
        self.state.is_paused = not self.state.is_paused
        self._pause_btn.config(
            text="▶ Resume" if self.state.is_paused else "⏸ Pause"
        )
        if self.state.is_paused:
            self._nudge_label.config(text="Monitoring paused.", fg=DIM_COLOR)
            self._accent_strip.config(bg=DIM_COLOR)

    def _toggle_away(self):
        self.state.is_working_away = not self.state.is_working_away
        if self.state.is_working_away:
            self._away_btn.config(text="✓ I'm Back", fg=COLORS["productive"],
                                  bg=SURFACE_2, activebackground=SURFACE_COLOR)
            self._nudge_label.config(
                text="Working away — time tracking continues.\nClick 'I'm Back' when you return.",
                fg=COLORS["break"])
            self._accent_strip.config(bg=COLORS["break"])
        else:
            self._away_btn.config(text="🏃 Away", fg=DIM_COLOR,
                                  bg=SURFACE_COLOR, activebackground=SURFACE_2)
            self._nudge_label.config(text="Welcome back! Resuming monitoring.", fg=FG_COLOR)

    def _add_task(self):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.wm_attributes("-topmost", True)
        popup.configure(bg=BORDER_COLOR)

        pw, ph = 260, 68
        px = self.root.winfo_x()
        py = self.root.winfo_y() - ph - 4
        popup.geometry(f"{pw}x{ph}+{px}+{py}")

        inner = tk.Frame(popup, bg=SURFACE_COLOR)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Label(inner, text="NEW TASK", bg=SURFACE_COLOR, fg=DIM_COLOR,
                 font=("Segoe UI", 7, "bold"), anchor="w", padx=10).pack(fill="x", pady=(6, 2))

        row = tk.Frame(inner, bg=SURFACE_COLOR)
        row.pack(fill="x", padx=6, pady=(0, 6))

        entry = tk.Entry(row, bg=SURFACE_2, fg=FG_COLOR,
                         insertbackground=ACCENT_COLOR, relief="flat", font=FONT_BODY)
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 4))
        entry.focus_set()

        def save(e=None):
            name = entry.get().strip()
            if name:
                db.add_task(self.conn, self.session_id, name)
                self.state.tasks = db.get_tasks(self.conn, self.session_id)
            popup.destroy()

        entry.bind("<Return>", save)
        entry.bind("<Escape>", lambda e: popup.destroy())
        _btn(row, "＋", save, fg=ACCENT_COLOR, bg=SURFACE_2, padx=8).pack(side="right")
        self.root.bind("<Button-1>",
                       lambda e: popup.destroy() if not (px <= e.x_root <= px+pw and py <= e.y_root <= py+ph) else None,
                       add="+")

    def _mark_done(self):
        task = self.state.current_task
        if not task or task in ("none", "error", "—"):
            return
        db.complete_task(self.conn, self.session_id, task)
        db.close_transition(self.conn, self.session_id)
        self.state.set_nudge("none", "unknown", f"✓ '{task}' marked complete. What's next?")
        self._nudge_label.config(text=f"✓ '{task}' marked complete. What's next?",
                                 fg=COLORS["productive"])
        self._accent_strip.config(bg=COLORS["productive"])
        self._task_label.config(text="—")
        self._done_btn.config(state="disabled", fg=DIM_COLOR)

    def _toggle_chat(self):
        self._chat_visible = not self._chat_visible
        if self._chat_visible:
            self._chat_frame.pack(fill="x", before=self._nudge_label)
            self._chat_entry.focus_set()
            self._chat_btn.config(fg=ACCENT_COLOR)
        else:
            self._chat_frame.pack_forget()
            self._chat_btn.config(fg=DIM_COLOR)

    def _send_chat(self):
        msg = self._chat_entry.get().strip()
        if not msg:
            return
        self._chat_entry.delete(0, "end")
        self._nudge_label.config(text="Thinking…", fg=DIM_COLOR)
        self._send_btn.config(state="disabled")

        tasks = db.get_tasks(self.conn, self.session_id)

        def call():
            reply = claude_client.chat_with_claude(
                msg, tasks,
                self.state.current_task,
                self.state.next_commitment,
            )
            self.root.after(0, lambda: self._show_chat_reply(reply))

        threading.Thread(target=call, daemon=True).start()

    def _show_chat_reply(self, reply: str):
        self._nudge_label.config(text=reply, fg=COLORS["unknown"])
        self._accent_strip.config(bg=COLORS["unknown"])
        self._send_btn.config(state="normal")

    def _show_correction(self):
        # Show all tasks — active first, then completed (marked with ✓)
        active = db.get_tasks(self.conn, self.session_id)
        completed = db.get_completed_tasks(self.conn, self.session_id)
        all_tasks = [(t, False) for t in active] + [(t, True) for t in completed]
        if not all_tasks:
            return

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.wm_attributes("-topmost", True)
        popup.configure(bg=BORDER_COLOR)

        # Position above the nudge window
        px = self.root.winfo_x()
        py = self.root.winfo_y() - (len(all_tasks) * 32 + 56)
        popup.geometry(f"260x{len(all_tasks) * 32 + 52}+{px}+{py}")

        inner = tk.Frame(popup, bg=SURFACE_COLOR)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Label(inner, text="WHAT ARE YOU DOING?", bg=SURFACE_COLOR,
                 fg=DIM_COLOR, font=("Segoe UI", 7, "bold"),
                 anchor="w", padx=10).pack(fill="x", pady=(8, 4))

        for task, done in all_tasks:
            label_text = f"✓ {task}" if done else task
            fg = DIM_COLOR if done else FG_COLOR
            row = tk.Frame(inner, bg=SURFACE_COLOR, cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)
            lbl = tk.Label(row, text=label_text, bg=SURFACE_COLOR, fg=fg,
                           font=FONT_BODY, anchor="w", padx=8, pady=5)
            lbl.pack(fill="x")
            for widget in (row, lbl):
                widget.bind("<Enter>", lambda e, r=row, l=lbl: (r.config(bg=SURFACE_2), l.config(bg=SURFACE_2)))
                widget.bind("<Leave>", lambda e, r=row, l=lbl: (r.config(bg=SURFACE_COLOR), l.config(bg=SURFACE_COLOR)))
                widget.bind("<Button-1>", lambda e, t=task: self._apply_correction(t, popup))

        # Dismiss on click outside (FocusOut is unreliable with overrideredirect on Windows)
        def on_click_outside(e):
            wx, wy = popup.winfo_x(), popup.winfo_y()
            ww, wh = popup.winfo_width(), popup.winfo_height()
            if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                popup.destroy()
        self.root.bind("<Button-1>", on_click_outside, add="+")
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)
        popup.focus_force()

    def _apply_correction(self, task: str, popup: tk.Toplevel):
        popup.destroy()
        db.close_transition(self.conn, self.session_id)
        db.record_transition(self.conn, self.session_id, task, "user_correction")
        db.correct_last_activity(self.conn, self.session_id, task)
        self.state.set_nudge(task, self.state.category, self.state.nudge_text)
        self._apply(task, self.state.category, self.state.nudge_text, "monitoring")

    def _show_summary(self):
        report = time_tracker.format_report(self.session_id, self.conn)

        win = tk.Toplevel(self.root)
        win.title("AI Co-Pilot — Summary")
        win.configure(bg=BG_COLOR)
        win.wm_attributes("-topmost", True)
        win.resizable(False, False)

        # Header
        hdr = tk.Frame(win, bg=SURFACE_COLOR, height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Today's Summary", bg=SURFACE_COLOR, fg=FG_COLOR,
                 font=("Segoe UI", 11, "bold"), anchor="w", padx=16).pack(fill="y", side="left")

        # Report text
        tk.Label(win, text=report, bg=BG_COLOR, fg=FG_COLOR,
                 font=("Consolas", 10), justify="left",
                 padx=20, pady=16, anchor="nw").pack(anchor="w")

        # Buttons
        btn_bar = tk.Frame(win, bg=BG_COLOR)
        btn_bar.pack(pady=(0, 14), padx=16, fill="x")

        def copy():
            win.clipboard_clear()
            win.clipboard_append(report)
            copy_btn.config(text="Copied!", fg=COLORS["productive"])
            win.after(1500, lambda: copy_btn.config(text="Copy Report", fg=DIM_COLOR))

        copy_btn = _btn(btn_bar, "Copy Report", copy, fg=DIM_COLOR, padx=10, pady=5)
        copy_btn.pack(side="left", padx=(0, 6))
        _btn(btn_bar, "Close", win.destroy, fg=DIM_COLOR, padx=10, pady=5).pack(side="left")


# ── Utility ───────────────────────────────────────────────────────────────────

def _darken(hex_color: str, factor: float = 0.3) -> str:
    """Return a darkened version of a hex color for pulse animation."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#1a1a2e"
