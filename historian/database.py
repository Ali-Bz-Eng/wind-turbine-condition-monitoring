"""SQLite storage for timestamped turbine measurements."""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from register_map import SIGNAL_NAMES

TABLE_NAME = "measurements"
ALARM_TABLE_NAME = "alarms"


def format_timestamp(moment: datetime) -> str:
    """Return an ISO 8601 UTC timestamp with millisecond precision."""
    utc = moment.astimezone(UTC).isoformat(timespec="milliseconds")
    return utc.replace("+00:00", "Z")


def connect(path: Path) -> sqlite3.Connection:
    """Open the database, creating the file and the table if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    # Column names come from the register map, never from external input.
    columns = ", ".join(f"{name} REAL NOT NULL" for name in SIGNAL_NAMES)
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} "
        f"(timestamp TEXT PRIMARY KEY, {columns})"
    )
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {ALARM_TABLE_NAME} ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "raised_at TEXT NOT NULL, "
        "cleared_at TEXT, "
        "source TEXT NOT NULL, "
        "message TEXT NOT NULL)"
    )
    return connection


def insert_measurement(
    connection: sqlite3.Connection, moment: datetime, values: Mapping[str, float]
) -> None:
    """Store one set of signal values under its timestamp."""
    columns = ", ".join(("timestamp", *SIGNAL_NAMES))
    placeholders = ", ".join("?" for _ in range(len(SIGNAL_NAMES) + 1))
    row = (format_timestamp(moment), *(values[name] for name in SIGNAL_NAMES))
    with connection:
        connection.execute(
            f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})", row
        )


def fetch_latest(connection: sqlite3.Connection, count: int) -> list[dict]:
    """Return the most recent measurements, oldest first."""
    rows = connection.execute(
        f"SELECT * FROM {TABLE_NAME} ORDER BY timestamp DESC LIMIT ?", (count,)
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def fetch_since(connection: sqlite3.Connection, timestamp: str) -> list[dict]:
    """Return measurements from a timestamp onwards, oldest first."""
    rows = connection.execute(
        f"SELECT * FROM {TABLE_NAME} WHERE timestamp >= ? ORDER BY timestamp",
        (timestamp,),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_after(
    connection: sqlite3.Connection, timestamp: str | None, limit: int
) -> list[dict]:
    """Return measurements newer than a timestamp, oldest first.

    Without a timestamp, only the latest measurement is returned, so a new
    reader starts from the present instead of replaying the whole history.
    """
    if timestamp is None:
        return fetch_latest(connection, 1)
    rows = connection.execute(
        f"SELECT * FROM {TABLE_NAME} WHERE timestamp > ? ORDER BY timestamp LIMIT ?",
        (timestamp, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def raise_alarm(
    connection: sqlite3.Connection, timestamp: str, source: str, message: str
) -> int:
    """Record a new active alarm and return its identifier."""
    with connection:
        cursor = connection.execute(
            f"INSERT INTO {ALARM_TABLE_NAME} (raised_at, source, message) "
            "VALUES (?, ?, ?)",
            (timestamp, source, message),
        )
    return cursor.lastrowid


def clear_alarm(connection: sqlite3.Connection, alarm_id: int, timestamp: str) -> None:
    """Mark an active alarm as cleared."""
    with connection:
        connection.execute(
            f"UPDATE {ALARM_TABLE_NAME} SET cleared_at = ? WHERE id = ?",
            (timestamp, alarm_id),
        )


def clear_open_alarms(connection: sqlite3.Connection, timestamp: str) -> int:
    """Close alarms left active by a previous run and return how many."""
    with connection:
        cursor = connection.execute(
            f"UPDATE {ALARM_TABLE_NAME} SET cleared_at = ? WHERE cleared_at IS NULL",
            (timestamp,),
        )
    return cursor.rowcount


def fetch_alarms(connection: sqlite3.Connection, count: int) -> list[dict]:
    """Return the most recent alarms, newest first."""
    rows = connection.execute(
        f"SELECT * FROM {ALARM_TABLE_NAME} ORDER BY id DESC LIMIT ?", (count,)
    ).fetchall()
    return [dict(row) for row in rows]
