"""Tests for the live alarm monitor and the alarm journal."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from analytics.monitor import MODEL_SOURCE, THRESHOLD_SOURCE, AlarmMonitor
from historian.database import connect, fetch_alarms, format_timestamp

START = datetime(2026, 11, 24, 9, 0, 0, tzinfo=UTC)
NORMAL = {
    "rotor_speed": 14.0,
    "power_output": 1500.0,
    "gearbox_temperature": 65.0,
    "vibration": 2.2,
}
HOT = dict(NORMAL, gearbox_temperature=85.0)


class FakeDetector:
    def __init__(self) -> None:
        self.anomalous = False

    def is_anomalous(self, rows: list) -> np.ndarray:
        return np.array([self.anomalous] * len(rows))


@pytest.fixture
def monitor(tmp_path: Path) -> AlarmMonitor:
    return AlarmMonitor(connect(tmp_path / "historian.db"), FakeDetector())


def feed(monitor: AlarmMonitor, values: dict, seconds: int, offset: int = 0) -> None:
    for second in range(offset, offset + seconds):
        moment = START + timedelta(seconds=second)
        monitor.process({"timestamp": format_timestamp(moment), **values})


def test_normal_operation_raises_no_alarm(monitor: AlarmMonitor) -> None:
    feed(monitor, NORMAL, 30)
    assert fetch_alarms(monitor.connection, 10) == []


def test_threshold_alarm_is_raised_then_cleared(monitor: AlarmMonitor) -> None:
    feed(monitor, HOT, 10)
    feed(monitor, NORMAL, 1, offset=10)
    [alarm] = fetch_alarms(monitor.connection, 10)
    assert alarm["source"] == THRESHOLD_SOURCE
    assert alarm["raised_at"] == "2026-11-24T09:00:09.000Z"
    assert alarm["cleared_at"] == "2026-11-24T09:00:10.000Z"


def test_alarm_is_recorded_once_while_active(monitor: AlarmMonitor) -> None:
    feed(monitor, HOT, 60)
    alarms = fetch_alarms(monitor.connection, 10)
    assert len(alarms) == 1
    assert alarms[0]["cleared_at"] is None


def test_model_alarm_is_raised(monitor: AlarmMonitor) -> None:
    monitor.detector.anomalous = True
    feed(monitor, NORMAL, 10)
    [alarm] = fetch_alarms(monitor.connection, 10)
    assert alarm["source"] == MODEL_SOURCE
