"""Tests for the measurement database."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from historian.database import (
    clear_open_alarms,
    connect,
    fetch_after,
    fetch_alarms,
    fetch_latest,
    format_timestamp,
    insert_measurement,
    raise_alarm,
)

START = datetime(2026, 11, 23, 21, 30, 0, tzinfo=UTC)
SAMPLE = {
    "rotor_speed": 14.5,
    "power_output": 1830.0,
    "gearbox_temperature": 76.2,
    "vibration": 2.54,
}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "historian.db"


def test_timestamp_is_utc_iso_8601() -> None:
    tunis = timezone(timedelta(hours=1))
    local_time = datetime(2026, 11, 23, 22, 30, 0, 125000, tzinfo=tunis)
    assert format_timestamp(local_time) == "2026-11-23T21:30:00.125Z"


def test_connect_creates_file_and_enables_wal(database_path: Path) -> None:
    connection = connect(database_path)
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    connection.close()
    assert database_path.exists()
    assert mode == "wal"


def test_inserted_measurement_is_returned(database_path: Path) -> None:
    connection = connect(database_path)
    insert_measurement(connection, START, SAMPLE)
    rows = fetch_latest(connection, 1)
    connection.close()
    assert rows == [{"timestamp": "2026-11-23T21:30:00.000Z", **SAMPLE}]


def test_fetch_latest_returns_most_recent_in_time_order(database_path: Path) -> None:
    connection = connect(database_path)
    for second in range(5):
        values = dict(SAMPLE, rotor_speed=float(second))
        insert_measurement(connection, START + timedelta(seconds=second), values)
    rows = fetch_latest(connection, 3)
    connection.close()
    assert [row["rotor_speed"] for row in rows] == [2.0, 3.0, 4.0]


def test_data_persists_after_reconnect(database_path: Path) -> None:
    connection = connect(database_path)
    insert_measurement(connection, START, SAMPLE)
    connection.close()
    reopened = connect(database_path)
    rows = fetch_latest(reopened, 10)
    reopened.close()
    assert len(rows) == 1


def test_fetch_after_returns_only_newer_rows(database_path: Path) -> None:
    connection = connect(database_path)
    for second in range(5):
        insert_measurement(connection, START + timedelta(seconds=second), SAMPLE)
    rows = fetch_after(connection, "2026-11-23T21:30:02.000Z", limit=10)
    connection.close()
    assert [row["timestamp"][17:19] for row in rows] == ["03", "04"]


def test_open_alarms_are_closed_on_restart(database_path: Path) -> None:
    connection = connect(database_path)
    raise_alarm(connection, "2026-11-23T21:30:00.000Z", "threshold", "Test alarm")
    closed = clear_open_alarms(connection, "2026-11-23T21:31:00.000Z")
    [alarm] = fetch_alarms(connection, 10)
    connection.close()
    assert closed == 1
    assert alarm["cleared_at"] == "2026-11-23T21:31:00.000Z"
