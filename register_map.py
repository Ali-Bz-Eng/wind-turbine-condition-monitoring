"""Modbus input register map of the turbine and value conversion."""

from collections.abc import Mapping
from dataclasses import dataclass

REGISTER_MAX_VALUE = 0xFFFF


@dataclass(frozen=True)
class Register:
    """One entry of the Modbus register map."""

    address: int
    name: str
    unit: str
    scale: int

    @property
    def decimals(self) -> int:
        """Number of decimal places kept by the scale."""
        return len(str(self.scale)) - 1


INPUT_REGISTERS = (
    Register(address=0, name="rotor_speed", unit="rpm", scale=10),
    Register(address=1, name="power_output", unit="kW", scale=1),
    Register(address=2, name="gearbox_temperature", unit="°C", scale=10),
    Register(address=3, name="vibration", unit="mm/s", scale=100),
)

SIGNAL_NAMES = tuple(register.name for register in INPUT_REGISTERS)


def encode(values: Mapping[str, float]) -> list[int]:
    """Scale measurements to unsigned 16-bit register values, clamped to range."""
    registers = []
    for register in INPUT_REGISTERS:
        scaled = round(values[register.name] * register.scale)
        registers.append(min(max(scaled, 0), REGISTER_MAX_VALUE))
    return registers


def decode(registers: list[int]) -> dict[str, float]:
    """Convert raw register values back to engineering units."""
    return {
        register.name: value / register.scale
        for register, value in zip(INPUT_REGISTERS, registers, strict=True)
    }
