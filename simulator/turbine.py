"""Simplified physical model of a 2 MW wind turbine with injectable faults."""

import math
import random
from dataclasses import asdict, dataclass
from enum import Enum


class Fault(Enum):
    NONE = "none"
    GEARBOX = "gearbox"
    BEARING = "bearing"


@dataclass(frozen=True)
class TurbineReading:
    rotor_speed: float
    power_output: float
    gearbox_temperature: float
    vibration: float


class WindTurbine:
    """Turbine state advanced in one-second steps."""

    RATED_POWER_KW = 2000.0
    CUT_IN_WIND_SPEED_M_S = 3.0
    RATED_WIND_SPEED_M_S = 12.0
    CUT_OUT_WIND_SPEED_M_S = 25.0
    RATED_ROTOR_SPEED_RPM = 16.0

    MEAN_WIND_SPEED_M_S = 9.0
    WIND_SWING_M_S = 3.0
    WIND_PERIOD_S = 360.0
    GUST_STD_M_S = 0.4

    IDLE_OIL_TEMPERATURE_C = 45.0
    FULL_LOAD_TEMPERATURE_RISE_C = 30.0
    THERMAL_TIME_CONSTANT_S = 60.0

    BASE_VIBRATION_MM_S = 1.0
    VIBRATION_PER_RPM_MM_S = 0.08

    GEARBOX_FAULT_HEATING_C_PER_S = 0.08
    GEARBOX_FAULT_VIBRATION_MM_S_PER_S = 0.003
    BEARING_FAULT_VIBRATION_MM_S_PER_S = 0.01

    ROTOR_SPEED_NOISE_RPM = 0.1
    POWER_NOISE_KW = 15.0
    TEMPERATURE_NOISE_C = 0.3
    VIBRATION_NOISE_MM_S = 0.08

    def __init__(
        self,
        fault: Fault = Fault.NONE,
        fault_start_s: int = 0,
        seed: int | None = None,
    ) -> None:
        self.fault = fault
        self.fault_start_s = fault_start_s
        self.time_s = 0
        self._rng = random.Random(seed)
        self._oil_temperature_c: float | None = None

    def step(self) -> TurbineReading:
        """Advance the model by one second and return the new measurements."""
        self.time_s += 1
        wind_speed = self._wind_speed()
        power = self.power_curve(wind_speed)
        rotor_speed = self.rotor_speed(wind_speed)
        fault_age_s = max(0, self.time_s - self.fault_start_s)

        target_temperature = (
            self.IDLE_OIL_TEMPERATURE_C
            + self.FULL_LOAD_TEMPERATURE_RISE_C * power / self.RATED_POWER_KW
        )
        vibration = self.BASE_VIBRATION_MM_S + self.VIBRATION_PER_RPM_MM_S * rotor_speed

        if self.fault is Fault.GEARBOX:
            target_temperature += self.GEARBOX_FAULT_HEATING_C_PER_S * fault_age_s
            vibration += self.GEARBOX_FAULT_VIBRATION_MM_S_PER_S * fault_age_s
        elif self.fault is Fault.BEARING:
            vibration += self.BEARING_FAULT_VIBRATION_MM_S_PER_S * fault_age_s

        if self._oil_temperature_c is None:
            self._oil_temperature_c = target_temperature
        # First-order lag: each second the oil closes part of the gap to its target.
        self._oil_temperature_c += (
            target_temperature - self._oil_temperature_c
        ) / self.THERMAL_TIME_CONSTANT_S

        return TurbineReading(
            rotor_speed=max(0.0, rotor_speed + self._noise(self.ROTOR_SPEED_NOISE_RPM)),
            power_output=max(0.0, power + self._noise(self.POWER_NOISE_KW)),
            gearbox_temperature=self._oil_temperature_c
            + self._noise(self.TEMPERATURE_NOISE_C),
            vibration=max(0.0, vibration + self._noise(self.VIBRATION_NOISE_MM_S)),
        )

    def _noise(self, std: float) -> float:
        return self._rng.gauss(0, std)

    def _wind_speed(self) -> float:
        slow_variation = self.WIND_SWING_M_S * math.sin(
            2 * math.pi * self.time_s / self.WIND_PERIOD_S
        )
        gust = self._noise(self.GUST_STD_M_S)
        return max(0.0, self.MEAN_WIND_SPEED_M_S + slow_variation + gust)

    @classmethod
    def power_curve(cls, wind_speed: float) -> float:
        """Electrical power in kW for a given wind speed in m/s."""
        if (
            wind_speed < cls.CUT_IN_WIND_SPEED_M_S
            or wind_speed >= cls.CUT_OUT_WIND_SPEED_M_S
        ):
            return 0.0
        if wind_speed >= cls.RATED_WIND_SPEED_M_S:
            return cls.RATED_POWER_KW
        return cls.RATED_POWER_KW * (wind_speed / cls.RATED_WIND_SPEED_M_S) ** 3

    @classmethod
    def rotor_speed(cls, wind_speed: float) -> float:
        """Rotor speed in rpm for a given wind speed in m/s."""
        if (
            wind_speed < cls.CUT_IN_WIND_SPEED_M_S
            or wind_speed >= cls.CUT_OUT_WIND_SPEED_M_S
        ):
            return 0.0
        ratio = min(1.0, wind_speed / cls.RATED_WIND_SPEED_M_S)
        return cls.RATED_ROTOR_SPEED_RPM * ratio



def simulate(
    duration_s: int,
    fault: Fault = Fault.NONE,
    fault_start_s: int = 0,
    seed: int | None = None,
) -> list[dict[str, float]]:
    """Run the model offline and return the signal values for every second."""
    turbine = WindTurbine(fault=fault, fault_start_s=fault_start_s, seed=seed)
    return [asdict(turbine.step()) for _ in range(duration_s)]


    