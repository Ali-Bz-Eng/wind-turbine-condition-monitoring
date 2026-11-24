"""Tests for the Isolation Forest anomaly detector."""

from pathlib import Path

import pytest

from analytics.anomaly import AnomalyDetector
from simulator.turbine import Fault, simulate


@pytest.fixture(scope="module")
def detector() -> AnomalyDetector:
    return AnomalyDetector.train(simulate(1200, seed=1), simulate(1200, seed=2))


def test_healthy_data_is_rarely_flagged(detector: AnomalyDetector) -> None:
    flags = detector.is_anomalous(simulate(1200, seed=3))
    assert flags.mean() < 0.02


def test_hot_gearbox_at_low_power_is_flagged(detector: AnomalyDetector) -> None:
    sample = {
        "rotor_speed": 8.0,
        "power_output": 300.0,
        "gearbox_temperature": 75.0,
        "vibration": 1.7,
    }
    assert detector.is_anomalous([sample])[0]


def test_developed_gearbox_fault_is_flagged(detector: AnomalyDetector) -> None:
    run = simulate(900, fault=Fault.GEARBOX, fault_start_s=300, seed=4)
    assert detector.is_anomalous(run[-60:]).all()


def test_saved_model_gives_same_results(
    detector: AnomalyDetector, tmp_path: Path
) -> None:
    path = tmp_path / "model.joblib"
    detector.save(path)
    reloaded = AnomalyDetector.load(path)
    rows = simulate(100, seed=5)
    assert reloaded.threshold == detector.threshold
    assert (reloaded.is_anomalous(rows) == detector.is_anomalous(rows)).all()
