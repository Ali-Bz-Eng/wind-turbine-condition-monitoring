"""SQLite storage for timestamped turbine measurements."""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from register_map import SIGNAL_NAMES

TABLE_NAME = "measurements"


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
