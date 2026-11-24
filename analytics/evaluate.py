"""Compare threshold alarms and the anomaly model on simulated fault scenarios."""

import logging
from collections.abc import Mapping, Sequence

import numpy as np

import config
from analytics.anomaly import AnomalyDetector
from analytics.rules import ON_DELAY_SAMPLES, OnDelay, ThresholdRules
from simulator.turbine import Fault, simulate

SCENARIO_DURATION_S = 1800
FAULT_START_S = 300
SCENARIO_SEED = 3
FALSE_ALARM_DURATION_S = 24 * 3600
FALSE_ALARM_SEED = 4

log = logging.getLogger(__name__)


def threshold_alarms(rows: Sequence[Mapping[str, float]]) -> np.ndarray:
    """Return, for every second, whether any threshold alarm is active."""
    rules = ThresholdRules()
    return np.array([bool(rules.update(row)) for row in rows])


def model_alarms(
    detector: AnomalyDetector, rows: Sequence[Mapping[str, float]]
) -> np.ndarray:
    """Return, for every second, whether the anomaly alarm is active."""
    delay = OnDelay(ON_DELAY_SAMPLES)
    return np.array([delay.update(flag) for flag in detector.is_anomalous(rows)])


def detection_delay_s(active: np.ndarray, fault_start_s: int) -> int | None:
    """Seconds from fault start to the first alarm, or None if never raised."""
    alarm_seconds = np.flatnonzero(active[fault_start_s:])
    return int(alarm_seconds[0]) if alarm_seconds.size else None


def count_alarm_events(active: np.ndarray) -> int:
    """Number of times an alarm switched from inactive to active."""
    return int(np.count_nonzero(active[1:] & ~active[:-1]) + active[0])


def format_delay(delay_s: int | None) -> str:
    return "not detected" if delay_s is None else f"{delay_s} s"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if not config.MODEL_PATH.exists():
        log.error("No model at %s. Run: python -m analytics.anomaly", config.MODEL_PATH)
        return
    detector = AnomalyDetector.load(config.MODEL_PATH)

    results = []
    for fault in (Fault.GEARBOX, Fault.BEARING):
        rows = simulate(
            SCENARIO_DURATION_S,
            fault=fault,
            fault_start_s=FAULT_START_S,
            seed=SCENARIO_SEED,
        )
        results.append(
            (
                f"{fault.value.capitalize()} fault, detection delay",
                format_delay(detection_delay_s(threshold_alarms(rows), FAULT_START_S)),
                format_delay(
                    detection_delay_s(model_alarms(detector, rows), FAULT_START_S)
                ),
            )
        )

    log.info("Simulating %d healthy hours", FALSE_ALARM_DURATION_S // 3600)
    healthy = simulate(FALSE_ALARM_DURATION_S, seed=FALSE_ALARM_SEED)
    results.append(
        (
            "Healthy 24 h, false alarms",
            str(count_alarm_events(threshold_alarms(healthy))),
            str(count_alarm_events(model_alarms(detector, healthy))),
        )
    )

    header = ("Scenario", "Threshold alarms", "Isolation Forest")
    widths = [max(len(row[i]) for row in (header, *results)) for i in range(3)]
    for row in (header, tuple("-" * width for width in widths), *results):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        print("  ".join(cells).rstrip())


if __name__ == "__main__":
    main()
