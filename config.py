"""Shared settings for the simulator and its clients"""

from dataclasses import dataclass

MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020
MODBUS_DEVICE_ID = 1

INPUT_REGISTERS_FUNCTION_CODE = 4
UPDATE_PERIOD_S = 1.0


@dataclass(frozen=True)
class Register:
    """One entry of the Modbus register map"""

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
