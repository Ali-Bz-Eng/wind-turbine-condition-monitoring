"""Isolation Forest anomaly detector trained on healthy turbine data."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

import config
from register_map import SIGNAL_NAMES
from simulator.turbine import simulate

N_ESTIMATORS = 200
FALSE_ALARM_QUANTILE = 0.005
TRAINING_DURATION_S = 3600
TRAINING_SEED = 1
VALIDATION_SEED = 2
MODEL_SEED = 0

ROTOR_SPEED = SIGNAL_NAMES.index("rotor_speed")
POWER_OUTPUT = SIGNAL_NAMES.index("power_output")
GEARBOX_TEMPERATURE = SIGNAL_NAMES.index("gearbox_temperature")
VIBRATION = SIGNAL_NAMES.index("vibration")

log = logging.getLogger(__name__)


def to_matrix(rows: Sequence[Mapping[str, float]]) -> np.ndarray:
    """Arrange signal values as one row per sample, one column per signal."""
    return np.array([[row[name] for name in SIGNAL_NAMES] for row in rows])


@dataclass
class AnomalyDetector:
    """Isolation Forest on raw signals and on deviations from normal behaviour.

    Two linear models learn the healthy relationships between gearbox
    temperature and power output, and between vibration and rotor speed.
    Their residuals let the forest spot readings that are unusual for the
    current operating point, not only values outside the usual range.
    """

    temperature_model: LinearRegression
    vibration_model: LinearRegression
    forest: IsolationForest
    threshold: float

    @classmethod
    def train(
        cls,
        training_rows: Sequence[Mapping[str, float]],
        validation_rows: Sequence[Mapping[str, float]],
    ) -> "AnomalyDetector":
        """Fit on healthy data, then set the threshold on separate healthy data."""
        signals = to_matrix(training_rows)
        temperature_model = LinearRegression().fit(
            signals[:, [POWER_OUTPUT]], signals[:, GEARBOX_TEMPERATURE]
        )
        vibration_model = LinearRegression().fit(
            signals[:, [ROTOR_SPEED]], signals[:, VIBRATION]
        )
        detector = cls(
            temperature_model=temperature_model,
            vibration_model=vibration_model,
            forest=IsolationForest(n_estimators=N_ESTIMATORS, random_state=MODEL_SEED),
            threshold=0.0,
        )
        detector.forest.fit(detector.features(signals))
        validation_scores = detector.scores(validation_rows)
        detector.threshold = float(np.quantile(validation_scores, FALSE_ALARM_QUANTILE))
        return detector

    def features(self, signals: np.ndarray) -> np.ndarray:
        """Raw signals plus the deviation of temperature and vibration from normal."""
        temperature_residual = signals[:, GEARBOX_TEMPERATURE] - (
            self.temperature_model.predict(signals[:, [POWER_OUTPUT]])
        )
        vibration_residual = signals[:, VIBRATION] - (
            self.vibration_model.predict(signals[:, [ROTOR_SPEED]])
        )
        return np.column_stack([signals, temperature_residual, vibration_residual])

    def scores(self, rows: Sequence[Mapping[str, float]]) -> np.ndarray:
        """Anomaly score per sample: the lower, the more abnormal."""
        return self.forest.score_samples(self.features(to_matrix(rows)))

    def is_anomalous(self, rows: Sequence[Mapping[str, float]]) -> np.ndarray:
        """Return one flag per sample: True where the sample looks abnormal."""
        return self.scores(rows) < self.threshold

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "AnomalyDetector":
        # joblib files can execute code when loaded: only load files you created.
        return joblib.load(path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    training = simulate(TRAINING_DURATION_S, seed=TRAINING_SEED)
    validation = simulate(TRAINING_DURATION_S, seed=VALIDATION_SEED)
    detector = AnomalyDetector.train(training, validation)
    detector.save(config.MODEL_PATH)
    log.info(
        "Model trained on %d healthy samples, threshold %.4f, saved to %s",
        len(training),
        detector.threshold,
        config.MODEL_PATH,
    )


if __name__ == "__main__":
    main()
