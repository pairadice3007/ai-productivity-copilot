import random
import threading
import time
from datetime import datetime

import database as db
import screenshotter
import local_context
import claude_client
from config import (
    SCREENSHOT_INTERVAL,
    DIFF_THRESHOLD,
    IDLE_THRESHOLD_SECONDS,
)


class AppState:
    """Shared mutable state between scheduler and UI threads."""

    def __init__(self):
        self.session_id: int = 0
        self.tasks: list[str] = []
        self.next_commitment: str = ""
        self.current_task: str = "none"
        self.category: str = "unknown"
        self.nudge_text: str = "Starting up…"
        self.is_paused: bool = False
        self.is_working_away: bool = False   # replaces snooze — no timeout, user toggles
        self.conn = None  # set by main after DB connect
        self._lock = threading.Lock()

    def set_nudge(self, task: str, category: str, nudge: str):
        with self._lock:
            self.current_task = task
            self.category = category
            self.nudge_text = nudge

    def get_nudge(self) -> tuple[str, str, str]:
        with self._lock:
            return self.current_task, self.category, self.nudge_text


class SchedulerThread(threading.Thread):

    def __init__(self, state: AppState, ui_callback, stop_event: threading.Event):
        super().__init__(daemon=True, name="SchedulerThread")
        self._state = state
        self._ui_callback = ui_callback   # callable(task, category, nudge, indicator)
        self._stop = stop_event
        self._skip_cycles = 0             # for rate-limit backoff

    def run(self):
        # Small delay so the UI finishes rendering, then fire immediately
        self._stop.wait(timeout=3)
        while not self._stop.is_set():
            try:
                self._cycle()
            except Exception as e:
                self._ui_callback("error", "unknown", f"Scheduler error: {e}", "error")
            jitter = random.randint(-5, 5)
            self._stop.wait(timeout=max(10, SCREENSHOT_INTERVAL + jitter))

    def _cycle(self):
        state = self._state

        # 1. Paused by user
        if state.is_paused:
            self._ui_callback(state.current_task, state.category, state.nudge_text, "paused")
            return

        # 2. Rate-limit backoff
        if self._skip_cycles > 0:
            self._skip_cycles -= 1
            return

        # 3. Working away (on a call, other computer, etc.) — track time, skip screenshots
        if state.is_working_away:
            self._ui_callback(state.current_task, state.category,
                              "Working away — time tracking continues. Click 'I'm Back' when done.", "away")
            return

        # 4. Idle check
        idle_secs = local_context.get_idle_seconds()
        if idle_secs > IDLE_THRESHOLD_SECONDS:
            db.log_activity(state.conn, state.session_id, skip_reason="idle")
            self._ui_callback(state.current_task, "break", "Away from keyboard — not tracking.", "idle")
            return

        # 5. Active window
        app_name, win_title = local_context.get_active_window()

        # 6. Sensitive app suppression
        if local_context.is_sensitive_app(app_name, win_title):
            db.log_activity(state.conn, state.session_id, skip_reason="sensitive_app")
            self._ui_callback(state.current_task, state.category, "Private app — monitoring paused.", "sensitive")
            return

        # 7. Screenshot + diff
        b64, diff = screenshotter.get_screenshot_b64()
        if diff < DIFF_THRESHOLD:
            db.log_activity(state.conn, state.session_id,
                            inferred_task=state.current_task,
                            category=state.category,
                            skip_reason="no_diff")
            self._ui_callback(state.current_task, state.category, state.nudge_text, "monitoring")
            return

        # 8. Call Claude
        recent_log = db.get_recent_log(state.conn, state.session_id)
        result = claude_client.analyze_screen(
            b64, app_name, win_title,
            state.tasks, recent_log, state.next_commitment,
        )

        # Handle auth error: stop scheduler
        if result.error and result.error.startswith("auth_error"):
            self._ui_callback("error", "unknown", result.nudge_text, "error")
            self._stop.set()
            return

        # Handle rate limit: back off 2 cycles
        if result.error == "rate_limit":
            self._skip_cycles = 2
            self._ui_callback(state.current_task, state.category, result.nudge_text, "monitoring")
            return

        # 9. Log activity
        db.log_activity(
            state.conn, state.session_id,
            claude_summary=result.doing,
            nudge_text=result.nudge_text,
            inferred_task=result.inferred_task,
            category=result.category,
            confidence=result.confidence,
            tokens_used=result.tokens_used,
        )

        # 10. Task transition tracking
        if result.inferred_task and result.inferred_task != state.current_task:
            db.close_transition(state.conn, state.session_id)
            db.record_transition(state.conn, state.session_id, result.inferred_task, "claude")

        # 11. Update shared state + UI
        state.set_nudge(result.inferred_task, result.category, result.nudge_text)
        self._ui_callback(result.inferred_task, result.category, result.nudge_text, "monitoring")
