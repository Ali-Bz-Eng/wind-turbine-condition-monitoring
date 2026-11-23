"""Tests for the wind turbine model."""

from itertools import pairwise

import pytest

from simulator.turbine import Fault, TurbineReading, WindTurbine

RUN_LENGTH_S = 600
FAULT_START_S = 120
SEED = 42
LAST_MINUTE = slice(-60, None)


def run(fault: Fault) -> list[TurbineReading]:
    turbine = WindTurbine(fault=fault, fault_start_s=FAULT_START_S, seed=SEED)
    return [turbine.step() for _ in range(RUN_LENGTH_S)]


def last_minute_mean(readings: list[TurbineReading], field: str) -> float:
    values = [getattr(reading, field) for reading in readings[LAST_MINUTE]]
    return sum(values) / len(values)


@pytest.mark.parametrize("wind_speed", [0.0, 2.9, 25.0, 30.0])
def test_no_power_outside_operating_range(wind_speed: float) -> None:
    assert WindTurbine.power_curve(wind_speed) == 0.0
    assert WindTurbine.rotor_speed(wind_speed) == 0.0


@pytest.mark.parametrize("wind_speed", [12.0, 18.0, 24.9])
def test_power_and_rotor_speed_capped_at_rated(wind_speed: float) -> None:
    assert WindTurbine.power_curve(wind_speed) == WindTurbine.RATED_POWER_KW
    assert WindTurbine.rotor_speed(wind_speed) == WindTurbine.RATED_ROTOR_SPEED_RPM


def test_power_increases_with_wind_below_rated() -> None:
    powers = [WindTurbine.power_curve(speed) for speed in (4.0, 6.0, 8.0, 10.0, 11.9)]
    assert all(lower < higher for lower, higher in pairwise(powers))


def test_same_seed_gives_identical_runs() -> None:
    assert run(Fault.NONE) == run(Fault.NONE)


def test_readings_are_never_negative() -> None:
    for reading in run(Fault.BEARING):
        assert reading.rotor_speed >= 0
        assert reading.power_output >= 0
        assert reading.vibration >= 0


def test_no_fault_effect_before_fault_start() -> None:
    healthy = run(Fault.NONE)
    faulty = run(Fault.GEARBOX)
    assert healthy[:FAULT_START_S] == faulty[:FAULT_START_S]


def test_gearbox_fault_raises_temperature() -> None:
    healthy = run(Fault.NONE)
    faulty = run(Fault.GEARBOX)
    assert last_minute_mean(faulty, "gearbox_temperature") > (
        last_minute_mean(healthy, "gearbox_temperature") + 20
    )


def test_bearing_fault_raises_vibration_only() -> None:
    healthy = run(Fault.NONE)
    faulty = run(Fault.BEARING)
    assert last_minute_mean(faulty, "vibration") > 2 * last_minute_mean(
        healthy, "vibration"
    )
    assert last_minute_mean(faulty, "gearbox_temperature") == pytest.approx(
        last_minute_mean(healthy, "gearbox_temperature"), abs=0.5
    )
