"""
src/database.py
───────────────
SQLite-backed persistent storage for ATOM.

Stores:
  - User accounts (managed by streamlit-authenticator, not here)
  - Analysis history  per user  (question, answer, plan, chart type, timestamp)
  - Finance chat history per user
  - RAG chat history per user

Tables are created automatically on first run.
Database file: data/atom.db  (created next to the app)
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("atom.db")

# ── Path ──────────────────────────────────────────────────────────────────────
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "atom.db"
)


# ── Connection helper ─────────────────────────────────────────────────────────
@contextmanager
def _conn():
    """Yield a SQLite connection with row_factory set."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ── Schema bootstrap ──────────────────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every app start."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL,
                question    TEXT    NOT NULL,
                answer      TEXT    NOT NULL,
                chart_type  TEXT,
                plan_json   TEXT,
                dataset     TEXT,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS finance_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rag_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );
        """)
    logger.info(f"[DB] Initialised at {_DB_PATH}")


# ── Analysis history ──────────────────────────────────────────────────────────
def save_analysis(
    username:   str,
    question:   str,
    answer:     str,
    plan:       dict  = None,
    dataset:    str   = None,
):
    """Persist one analysis Q&A to the database."""
    with _conn() as con:
        con.execute(
            """
            INSERT INTO analysis_history
                (username, question, answer, chart_type, plan_json, dataset, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                question,
                answer,
                plan.get("chart") if plan else None,
                json.dumps(plan)  if plan else None,
                dataset,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )


def get_analysis_history(username: str, limit: int = 50) -> list[dict]:
    """Return the last `limit` analysis entries for this user, newest first."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT id, question, answer, chart_type, plan_json, dataset, created_at
            FROM   analysis_history
            WHERE  username = ?
            ORDER  BY id DESC
            LIMIT  ?
            """,
            (username, limit),
        ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row["plan_json"]:
            row["plan"] = json.loads(row["plan_json"])
        del row["plan_json"]
        result.append(row)
    return result


def delete_analysis_history(username: str):
    """Delete all analysis history for a user."""
    with _conn() as con:
        con.execute(
            "DELETE FROM analysis_history WHERE username = ?",
            (username,)
        )


# ── Finance history ───────────────────────────────────────────────────────────
def save_finance_message(username: str, role: str, content: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO finance_history (username, role, content, created_at) VALUES (?,?,?,?)",
            (username, role, content, datetime.utcnow().isoformat(timespec="seconds")),
        )


def get_finance_history(username: str, limit: int = 100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT role, content, created_at FROM finance_history
            WHERE  username = ?
            ORDER  BY id ASC
            LIMIT  ?
            """,
            (username, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_finance_history(username: str):
    with _conn() as con:
        con.execute("DELETE FROM finance_history WHERE username = ?", (username,))


# ── RAG history ───────────────────────────────────────────────────────────────
def save_rag_message(username: str, role: str, content: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO rag_history (username, role, content, created_at) VALUES (?,?,?,?)",
            (username, role, content, datetime.utcnow().isoformat(timespec="seconds")),
        )


def get_rag_history(username: str, limit: int = 100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT role, content, created_at FROM rag_history
            WHERE  username = ?
            ORDER  BY id ASC
            LIMIT  ?
            """,
            (username, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_rag_history(username: str):
    with _conn() as con:
        con.execute("DELETE FROM rag_history WHERE username = ?", (username,))