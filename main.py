"""
AI Productivity Co-Pilot — Phase 1 MVP
Run: python main.py
"""
import os
import sys
import threading
import tkinter as tk
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import database as db
from config import LOCK_FILE
import scheduler as sched
from ui import show_startup_dialog, NudgeWindow

# ── Constants ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"


# ── Single-instance lock ──────────────────────────────────────────────────────

def _acquire_lock() -> bool:
    import psutil
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            if psutil.pid_exists(pid):
                print(f"Co-Pilot is already running (PID {pid}). Exiting.")
                return False
        except Exception:
            pass
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


# ── API key setup ─────────────────────────────────────────────────────────────

def _ensure_api_key(root: tk.Tk) -> bool:
    if os.environ.get(ANTHROPIC_API_KEY_ENV):
        return True

    key = {"value": None}
    dialog = tk.Toplevel(root)
    dialog.title("Setup — API Key Required")
    dialog.configure(bg="#1e1e2e")
    dialog.resizable(False, False)
    dialog.geometry("380x180+200+200")
    dialog.grab_set()

    import tkinter.ttk as ttk
    tk.Label(dialog, text="Enter your Anthropic API key:",
             bg="#1e1e2e", fg="#cdd6f4").pack(pady=(20, 4), padx=20, anchor="w")
    var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=var, show="*", bg="#313244", fg="#cdd6f4",
                     insertbackground="#cdd6f4", relief="flat", width=42)
    entry.pack(padx=20, pady=4)

    def save():
        k = var.get().strip()
        if not k:
            return
        key["value"] = k
        os.environ[ANTHROPIC_API_KEY_ENV] = k
        env_path = Path(".env")
        existing = env_path.read_text() if env_path.exists() else ""
        if ANTHROPIC_API_KEY_ENV not in existing:
            with open(env_path, "a") as f:
                f.write(f"\n{ANTHROPIC_API_KEY_ENV}={k}\n")
        dialog.destroy()

    tk.Button(dialog, text="Save & Continue", command=save,
              bg="#6272a4", fg="white", relief="flat", padx=10, pady=4).pack(pady=12)
    tk.Label(dialog, text="Your key is saved locally in .env and never uploaded.",
             bg="#1e1e2e", fg="#6c7086", font=("TkDefaultFont", 8)).pack()

    root.wait_window(dialog)
    return key["value"] is not None


# ── Crash recovery ────────────────────────────────────────────────────────────

def _handle_crash_recovery(conn, root: tk.Tk) -> int | None:
    """If an open session from today exists, offer to resume. Returns session_id or None."""
    open_session = db.find_open_session_today(conn)
    if not open_session:
        return None

    result = {"resume": None}
    dialog = tk.Toplevel(root)
    dialog.title("Resume Session?")
    dialog.configure(bg="#1e1e2e")
    dialog.resizable(False, False)
    dialog.geometry("340x140+200+200")
    dialog.grab_set()

    tk.Label(dialog, text=f"An open session from today was found\n(started {open_session['started_at']}).",
             bg="#1e1e2e", fg="#cdd6f4", justify="center").pack(pady=(16, 8))

    btn_bar = tk.Frame(dialog, bg="#1e1e2e")
    btn_bar.pack()

    def do_resume():
        result["resume"] = True
        dialog.destroy()

    def do_fresh():
        result["resume"] = False
        dialog.destroy()

    tk.Button(btn_bar, text="Resume", command=do_resume,
              bg="#6272a4", fg="white", relief="flat", padx=10).pack(side="left", padx=8)
    tk.Button(btn_bar, text="Start Fresh", command=do_fresh,
              bg="#313244", fg="#cdd6f4", relief="flat", padx=10).pack(side="left", padx=8)

    root.wait_window(dialog)

    if result["resume"]:
        db.log_activity(conn, open_session["id"], skip_reason="crash_gap",
                        nudge_text="Resumed after gap — previous time unaccounted.")
        return open_session["id"]
    else:
        db.update_session_state(conn, open_session["id"], "crashed")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not _acquire_lock():
        sys.exit(0)

    root = tk.Tk()
    root.withdraw()  # hidden until nudge window is ready

    try:
        if not _ensure_api_key(root):
            print("No API key provided. Exiting.")
            return

        conn = db.connect()
        db.init_db(conn)

        # Crash recovery check
        session_id = _handle_crash_recovery(conn, root)
        resumed = session_id is not None

        # Startup dialog
        result = show_startup_dialog(root)
        if result is None:
            return  # user closed dialog
        tasks, next_commitment = result

        # Session
        if not resumed:
            session_id = db.start_session(conn, next_commitment)
        db.save_tasks(conn, session_id, tasks)

        # Shared state
        state = sched.AppState()
        state.session_id = session_id
        state.tasks = tasks
        state.next_commitment = next_commitment
        state.conn = conn

        # Stop event
        stop_event = threading.Event()

        # Build nudge window
        def on_quit():
            stop_event.set()
            db.close_transition(conn, session_id)
            db.update_session_state(conn, session_id, "closed")
            conn.close()
            _release_lock()
            root.quit()

        nudge_win = NudgeWindow(
            root, state, conn, session_id,
            on_correct=None,  # handled internally by NudgeWindow
            on_pause=None,
            on_quit=on_quit,
        )

        # Start scheduler
        scheduler = sched.SchedulerThread(
            state=state,
            ui_callback=nudge_win.update_nudge,
            stop_event=stop_event,
        )
        scheduler.start()

        # Show window and run
        root.deiconify()
        root.protocol("WM_DELETE_WINDOW", on_quit)
        root.mainloop()

    finally:
        _release_lock()


if __name__ == "__main__":
    main()
