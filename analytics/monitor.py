"""Apply both detection methods to new historian data and keep an alarm journal."""

import logging
import sqlite3
import time
from collections.abc import Mapping
from datetime import UTC, datetime

import config
from analytics.anomaly import AnomalyDetector
from analytics.rules import ON_DELAY_SAMPLES, OnDelay, ThresholdRules
from historian.database import (
    clear_alarm,
    clear_open_alarms,
    connect,
    fetch_after,
    format_timestamp,
    raise_alarm,
)

THRESHOLD_SOURCE = "threshold"
MODEL_SOURCE = "model"
MODEL_MESSAGE = "Abnormal turbine behaviour detected by the anomaly model"
BATCH_SIZE = 100

log = logging.getLogger(__name__)


class AlarmMonitor:
    """Turn active alarm conditions into raise and clear events in the journal."""

    def __init__(
        self, connection: sqlite3.Connection, detector: AnomalyDetector
    ) -> None:
        self.connection = connection
        self.detector = detector
        self.rules = ThresholdRules()
        self.model_delay = OnDelay(ON_DELAY_SAMPLES)
        self.active: dict[tuple[str, str], int] = {}

    def process(self, row: Mapping[str, float | str]) -> None:
        """Evaluate one measurement and update the alarm journal."""
        conditions = {(THRESHOLD_SOURCE, message) for message in self.rules.update(row)}
        if self.model_delay.update(bool(self.detector.is_anomalous([row])[0])):
            conditions.add((MODEL_SOURCE, MODEL_MESSAGE))

        timestamp = str(row["timestamp"])
        for source, message in conditions - self.active.keys():
            self.active[(source, message)] = raise_alarm(
                self.connection, timestamp, source, message
            )
            log.warning("Alarm raised [%s]: %s", source, message)
        for key in self.active.keys() - conditions:
            clear_alarm(self.connection, self.active.pop(key), timestamp)
            log.info("Alarm cleared [%s]: %s", *key)


def run(monitor: AlarmMonitor) -> None:
    """Process new measurements as the historian stores them."""
    last_timestamp = None
    while True:
        rows = fetch_after(monitor.connection, last_timestamp, BATCH_SIZE)
        for row in rows:
            monitor.process(row)
        if rows:
            last_timestamp = rows[-1]["timestamp"]
        time.sleep(config.UPDATE_PERIOD_S)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if not config.MODEL_PATH.exists():
        log.error("No model at %s. Run: python -m analytics.anomaly", config.MODEL_PATH)
        return
    connection = connect(config.DATABASE_PATH)
    closed = clear_open_alarms(connection, format_timestamp(datetime.now(UTC)))
    if closed:
        log.info("Closed %d alarms left open by a previous run", closed)
    monitor = AlarmMonitor(connection, AnomalyDetector.load(config.MODEL_PATH))
    log.info("Monitoring %s", config.DATABASE_PATH)
    try:
        run(monitor)
    except KeyboardInterrupt:
        log.info("Monitor stopped")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
