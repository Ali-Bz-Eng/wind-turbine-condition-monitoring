"""Tests for the dashboard API."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from dashboard.app import create_app
from historian.database import connect, insert_measurement, raise_alarm

START = datetime(2026, 11, 24, 9, 0, 0, tzinfo=UTC)
SAMPLE = {
    "rotor_speed": 14.5,
    "power_output": 1830.0,
    "gearbox_temperature": 76.2,
    "vibration": 2.54,
}


@pytest.fixture
def client(tmp_path: Path) -> FlaskClient:
    database_path = tmp_path / "historian.db"
    connection = connect(database_path)
    for second in range(3):
        insert_measurement(connection, START + timedelta(seconds=second), SAMPLE)
    raise_alarm(connection, "2026-11-24T09:00:02.000Z", "model", "Test alarm")
    connection.close()
    return create_app(database_path).test_client()


def test_measurements_are_returned_oldest_first(client: FlaskClient) -> None:
    body = client.get("/api/measurements").get_json()
    timestamps = [row["timestamp"] for row in body["measurements"]]
    assert timestamps == sorted(timestamps)
    assert len(timestamps) == 3
    assert body["measurements"][-1]["gearbox_temperature"] == 76.2
    assert body["server_time"].endswith("Z")


def test_alarms_are_returned(client: FlaskClient) -> None:
    [alarm] = client.get("/api/alarms").get_json()["alarms"]
    assert alarm["message"] == "Test alarm"
    assert alarm["cleared_at"] is None

def test_page_lists_every_signal_with_its_unit(client: FlaskClient) -> None:
    page = client.get("/").get_data(as_text=True)
    assert "Gearbox temperature" in page
    assert "Alarm limit 80 °C" in page
    assert "Vibration" in page


def test_trend_excludes_readings_older_than_the_window(tmp_path: Path) -> None:
    database_path = tmp_path / "historian.db"
    connection = connect(database_path)
    insert_measurement(connection, START - timedelta(hours=12), SAMPLE)
    insert_measurement(connection, START, SAMPLE)
    connection.close()
    client = create_app(database_path).test_client()
    measurements = client.get("/api/measurements").get_json()["measurements"]
    assert [row["timestamp"] for row in measurements] == ["2026-11-24T09:00:00.000Z"]
