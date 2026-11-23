"""Modbus TCP server that exposes the simulated turbine as input registers."""

import argparse
import asyncio
import logging

from pymodbus.constants import ExcCodes
from pymodbus.server import StartAsyncTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

import config
from simulator.turbine import Fault, TurbineReading, WindTurbine

REGISTER_BLOCK_SIZE = 16
REGISTER_MAX_VALUE = 0xFFFF
DEFAULT_FAULT_START_S = 120

log = logging.getLogger(__name__)


def encode(reading: TurbineReading) -> list[int]:
    """Scale each measurement to an unsigned 16-bit register value."""
    values = []
    for register in config.INPUT_REGISTERS:
        scaled = round(getattr(reading, register.name) * register.scale)
        values.append(min(max(scaled, 0), REGISTER_MAX_VALUE))
    return values


def unused_bit_table() -> list[SimData]:
    """Read-only placeholder: pymodbus requires one block in every table."""
    return [SimData(address=0, datatype=DataType.BITS, readonly=True)]


def unused_register_table() -> list[SimData]:
    """Register table with no valid addresses; requests get an exception response."""
    return [SimData(address=0, datatype=DataType.INVALID)]


class InputRegisterImage:
    """Latest encoded turbine values, served to clients on every read request."""

    def __init__(self) -> None:
        self.values = [0] * len(config.INPUT_REGISTERS)

    async def on_request(
        self,
        function_code: int,
        start_address: int,
        address: int,
        count: int,
        current_registers: list[int],
        set_values: list[int] | list[bool] | None,
    ) -> ExcCodes | None:
        """Copy the latest values into the registers pymodbus is about to return."""
        if function_code != config.INPUT_REGISTERS_FUNCTION_CODE:
            return None
        for register, value in zip(config.INPUT_REGISTERS, self.values, strict=True):
            index = register.address - start_address
            if 0 <= index < len(current_registers):
                current_registers[index] = value
        return None


async def run_turbine(turbine: WindTurbine, image: InputRegisterImage) -> None:
    """Advance the turbine every update period and refresh the register image."""
    while True:
        reading = turbine.step()
        image.values = encode(reading)
        log.info(
            "t=%4ds  rotor=%5.1f rpm  power=%6.0f kW  gearbox=%5.1f °C  "
            "vibration=%5.2f mm/s",
            turbine.time_s,
            reading.rotor_speed,
            reading.power_output,
            reading.gearbox_temperature,
            reading.vibration,
        )
        await asyncio.sleep(config.UPDATE_PERIOD_S)


async def run(args: argparse.Namespace) -> None:
    turbine = WindTurbine(
        fault=Fault(args.fault), fault_start_s=args.fault_start, seed=args.seed
    )
    image = InputRegisterImage()
    input_registers = SimData(
        address=0,
        count=REGISTER_BLOCK_SIZE,
        datatype=DataType.REGISTERS,
        readonly=True,
    )
    device = SimDevice(
        id=config.MODBUS_DEVICE_ID,
        simdata=(
            unused_bit_table(),
            unused_bit_table(),
            unused_register_table(),
            [input_registers],
        ),
        action=image.on_request,
    )

    turbine_task = asyncio.create_task(run_turbine(turbine, image))
    log.info(
        "Modbus TCP server on %s:%d (fault=%s, fault start=%ds)",
        args.host,
        args.port,
        args.fault,
        args.fault_start,
    )
    try:
        await StartAsyncTcpServer(context=[device], address=(args.host, args.port))
    finally:
        turbine_task.cancel()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wind turbine Modbus TCP simulator")
    parser.add_argument("--host", default=config.MODBUS_HOST, help="listening address")
    parser.add_argument(
        "--port", type=int, default=config.MODBUS_PORT, help="listening TCP port"
    )
    parser.add_argument(
        "--fault",
        choices=[fault.value for fault in Fault],
        default=Fault.NONE.value,
        help="fault scenario to inject",
    )
    parser.add_argument(
        "--fault-start",
        type=int,
        default=DEFAULT_FAULT_START_S,
        help="seconds after start-up when the fault begins",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="random seed for repeatable runs"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("pymodbus").setLevel(logging.WARNING)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        log.info("Server stopped")


if __name__ == "__main__":
    main()
