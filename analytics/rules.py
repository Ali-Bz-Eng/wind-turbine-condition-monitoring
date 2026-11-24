"""Threshold alarm rules with an on-delay and a deadband against noisy readings."""

from collections.abc import Mapping
from dataclasses import dataclass

from register_map import INPUT_REGISTERS

ON_DELAY_SAMPLES = 10

UNITS = {register.name: register.unit for register in INPUT_REGISTERS}


@dataclass(frozen=True)
class HighLimit:
    """Alarm condition on one signal exceeding a fixed limit.

    The alarm clears only once the signal falls below the limit minus the
    deadband, so a value hovering around the limit does not toggle it.
    """

    signal: str
    limit: float
    deadband: float
    label: str

    @property
    def message(self) -> str:
        return f"{self.label} above {self.limit:g} {UNITS[self.signal]}"


HIGH_LIMITS = (
    HighLimit(
        signal="gearbox_temperature",
        limit=80.0,
        deadband=2.0,
        label="Gearbox temperature",
    ),
    HighLimit(signal="vibration", limit=3.5, deadband=0.2, label="Vibration"),
)


class OnDelay:
    """Report a condition only after it has held for consecutive samples."""

    def __init__(self, samples: int = ON_DELAY_SAMPLES) -> None:
        self.samples = samples
        self._count = 0

    def update(self, condition: bool) -> bool:
        self._count = self._count + 1 if condition else 0
        return self._count >= self.samples


class ThresholdRules:
    """Evaluate every high limit on each new set of signal values."""

    def __init__(
        self,
        limits: tuple[HighLimit, ...] = HIGH_LIMITS,
        samples: int = ON_DELAY_SAMPLES,
    ) -> None:
        self.limits = limits
        self._delays = [OnDelay(samples) for _ in limits]
        self._active = [False for _ in limits]

    def update(self, values: Mapping[str, float]) -> list[str]:
        """Return the messages of the alarms active after this sample."""
        messages = []
        for index, limit in enumerate(self.limits):
            value = values[limit.signal]
            if self._active[index]:
                self._active[index] = value > limit.limit - limit.deadband
                if not self._active[index]:
                    self._delays[index].update(False)
            else:
                self._active[index] = self._delays[index].update(value > limit.limit)
            if self._active[index]:
                messages.append(limit.message)
        return messages
