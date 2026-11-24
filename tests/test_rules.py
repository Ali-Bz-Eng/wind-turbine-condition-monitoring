"""Tests for the threshold alarm rules."""

from analytics.rules import OnDelay, ThresholdRules

NORMAL = {
    "rotor_speed": 14.0,
    "power_output": 1500.0,
    "gearbox_temperature": 65.0,
    "vibration": 2.2,
}
HOT = dict(NORMAL, gearbox_temperature=85.0)

def test_on_delay_waits_for_consecutive_samples() -> None:
    delay = OnDelay(samples=3)
    assert [delay.update(True) for _ in range(4)] == [False, False, True, True]

def test_on_delay_resets_when_condition_clears() -> None:
    delay = OnDelay(samples=3)
    delay.update(True)
    delay.update(True)
    delay.update(False)
    assert delay.update(True) is False

def test_normal_values_raise_no_alarm() -> None:
    rules = ThresholdRules()
    assert all(rules.update(NORMAL) == [] for _ in range(30))

def test_sustained_high_temperature_raises_alarm() -> None:
    rules = ThresholdRules(samples=10)
    results = [rules.update(HOT) for _ in range(10)]
    assert results[8] == []
    assert results[9] == ["Gearbox temperature above 80 °C"]

def test_single_spike_is_ignored() -> None:
    rules = ThresholdRules(samples=10)
    rules.update(HOT)
    assert all(rules.update(NORMAL) == [] for _ in range(20))


def test_alarm_holds_inside_deadband() -> None:
    rules = ThresholdRules(samples=10)
    for _ in range(10):
        rules.update(HOT)
    just_below_limit = dict(NORMAL, gearbox_temperature=79.0)
    assert rules.update(just_below_limit) == ["Gearbox temperature above 80 °C"]

def test_alarm_clears_below_deadband() -> None:
    rules = ThresholdRules(samples=10)
    for _ in range(10):
        rules.update(HOT)
    assert rules.update(NORMAL) == []
    assert rules.update(HOT) == []
