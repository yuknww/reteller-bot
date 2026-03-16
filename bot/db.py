import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional


DB_PATH = "/data/chat.db"

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db() -> None:
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id      INTEGER,
            user_id         INTEGER,
            username        TEXT,
            full_name       TEXT,
            text            TEXT,
            timestamp       REAL NOT NULL,
            is_voice        INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def save_message(
    message_id: Optional[int],
    user_id: Optional[int],
    username: Optional[str],
    full_name: Optional[str],
    text: str,
    timestamp: Optional[datetime] = None,
    is_voice: bool = False,
) -> None:
    if not text or not text.strip():
        return
    ts = (timestamp or datetime.now(timezone.utc)).timestamp()
    get_conn().execute(
        """
        INSERT INTO messages (message_id, user_id, username, full_name, text, timestamp, is_voice)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, user_id, username, full_name, text.strip(), ts, int(is_voice)),
    )
    get_conn().commit()


def get_messages_since(since: datetime) -> list[dict]:
    ts = since.timestamp()
    rows = get_conn().execute(
        "SELECT * FROM messages WHERE timestamp >= ? ORDER BY timestamp ASC",
        (ts,),
    ).fetchall()
    return [dict(r) for r in rows]
