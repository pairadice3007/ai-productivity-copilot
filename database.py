import sqlite3
from datetime import datetime, date
from pathlib import Path
from config import DB_PATH


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT NOT NULL,
            started_at      TEXT NOT NULL,
            ended_at        TEXT,
            state           TEXT NOT NULL DEFAULT 'active',
            next_commitment TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES sessions(id),
            name         TEXT NOT NULL,
            position     INTEGER NOT NULL,
            completed_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES sessions(id),
            timestamp           TEXT NOT NULL,
            claude_summary      TEXT,
            nudge_text          TEXT,
            inferred_task       TEXT,
            category            TEXT,
            confidence          REAL,
            user_corrected_task TEXT,
            tokens_used         INTEGER,
            skip_reason         TEXT
        );

        CREATE TABLE IF NOT EXISTS task_transitions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            task_name   TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            source      TEXT NOT NULL
        );
    """)
    conn.commit()


# ── Sessions ──────────────────────────────────────────────────────────────────

def start_session(conn: sqlite3.Connection, next_commitment: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO sessions (date, started_at, state, next_commitment) VALUES (?, ?, 'active', ?)",
        (date.today().isoformat(), _now(), next_commitment),
    )
    conn.commit()
    return cur.lastrowid


def update_session_state(conn: sqlite3.Connection, session_id: int, state: str) -> None:
    ended_at = _now() if state in ("closed", "crashed") else None
    conn.execute(
        "UPDATE sessions SET state=?, ended_at=COALESCE(?, ended_at) WHERE id=?",
        (state, ended_at, session_id),
    )
    conn.commit()


def find_open_session_today(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM sessions WHERE date=? AND state='active' ORDER BY id DESC LIMIT 1",
        (date.today().isoformat(),),
    ).fetchone()


# ── Tasks ─────────────────────────────────────────────────────────────────────

def save_tasks(conn: sqlite3.Connection, session_id: int, tasks: list[str]) -> None:
    conn.execute("DELETE FROM tasks WHERE session_id=?", (session_id,))
    conn.executemany(
        "INSERT INTO tasks (session_id, name, position) VALUES (?, ?, ?)",
        [(session_id, t.strip(), i) for i, t in enumerate(tasks) if t.strip()],
    )
    conn.commit()


def get_tasks(conn: sqlite3.Connection, session_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM tasks WHERE session_id=? AND completed_at IS NULL ORDER BY position",
        (session_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def get_completed_tasks(conn: sqlite3.Connection, session_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM tasks WHERE session_id=? AND completed_at IS NOT NULL ORDER BY completed_at",
        (session_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def complete_task(conn: sqlite3.Connection, session_id: int, task_name: str) -> None:
    conn.execute(
        "UPDATE tasks SET completed_at=? WHERE session_id=? AND name=? AND completed_at IS NULL",
        (_now(), session_id, task_name),
    )
    conn.commit()


# ── Activity log ──────────────────────────────────────────────────────────────

def log_activity(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    claude_summary: str = "",
    nudge_text: str = "",
    inferred_task: str = "",
    category: str = "unknown",
    confidence: float = 0.0,
    tokens_used: int = 0,
    skip_reason: str = "",
) -> None:
    conn.execute(
        """INSERT INTO activity_log
           (session_id, timestamp, claude_summary, nudge_text, inferred_task,
            category, confidence, tokens_used, skip_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, _now(), claude_summary, nudge_text, inferred_task,
         category, confidence, tokens_used, skip_reason),
    )
    conn.commit()


def correct_last_activity(conn: sqlite3.Connection, session_id: int, corrected_task: str) -> None:
    conn.execute(
        """UPDATE activity_log SET user_corrected_task=?
           WHERE session_id=? AND id=(SELECT MAX(id) FROM activity_log WHERE session_id=?)""",
        (corrected_task, session_id, session_id),
    )
    conn.commit()


def get_recent_log(conn: sqlite3.Connection, session_id: int, n: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT timestamp, claude_summary, inferred_task, category, skip_reason
           FROM activity_log WHERE session_id=? ORDER BY id DESC LIMIT ?""",
        (session_id, n),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Task transitions ──────────────────────────────────────────────────────────

def record_transition(conn: sqlite3.Connection, session_id: int, task_name: str, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO task_transitions (session_id, task_name, started_at, source) VALUES (?, ?, ?, ?)",
        (session_id, task_name, _now(), source),
    )
    conn.commit()
    return cur.lastrowid


def close_transition(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        """UPDATE task_transitions SET ended_at=?
           WHERE session_id=? AND ended_at IS NULL""",
        (_now(), session_id),
    )
    conn.commit()


def get_open_transition(conn: sqlite3.Connection, session_id: int):
    return conn.execute(
        "SELECT * FROM task_transitions WHERE session_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()


# ── Summary ───────────────────────────────────────────────────────────────────

def get_time_summary(conn: sqlite3.Connection, session_id: int) -> dict[str, int]:
    """Returns {task_name: total_seconds} derived from closed transitions."""
    rows = conn.execute(
        """SELECT task_name,
                  SUM(CAST((julianday(COALESCE(ended_at, datetime('now','localtime')))
                           - julianday(started_at)) * 86400 AS INTEGER)) AS secs
           FROM task_transitions WHERE session_id=?
           GROUP BY task_name""",
        (session_id,),
    ).fetchall()
    return {r["task_name"]: r["secs"] or 0 for r in rows}


def get_token_total(conn: sqlite3.Connection, session_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) AS total FROM activity_log WHERE session_id=?",
        (session_id,),
    ).fetchone()
    return row["total"]
