"""Poll the turbine input registers and print the decoded values."""

import argparse
import logging
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

import config

DEFAULT_READ_COUNT = 10

log = logging.getLogger(__name__)


def decode(registers: list[int]) -> dict[str, float]:
    """Convert raw register values back to engineering units."""
    return {
        register.name: value / register.scale
        for register, value in zip(config.INPUT_REGISTERS, registers, strict=True)
    }


def format_values(values: dict[str, float]) -> str:
    return "  ".join(
        f"{register.name}={values[register.name]:.{register.decimals}f} {register.unit}"
        for register in config.INPUT_REGISTERS
    )


def poll(client: ModbusTcpClient, read_count: int) -> None:
    first_address = config.INPUT_REGISTERS[0].address
    register_count = len(config.INPUT_REGISTERS)
    for _ in range(read_count):
        response = client.read_input_registers(
            first_address, count=register_count, device_id=config.MODBUS_DEVICE_ID
        )
        if response.isError():
            log.error("Read failed: %s", response)
        else:
            log.info(format_values(decode(response.registers)))
        time.sleep(config.UPDATE_PERIOD_S)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read the turbine input registers")
    parser.add_argument("--host", default=config.MODBUS_HOST, help="server address")
    parser.add_argument(
        "--port", type=int, default=config.MODBUS_PORT, help="server TCP port"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_READ_COUNT,
        help="number of reads before exiting",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

    client = ModbusTcpClient(args.host, port=args.port)
    if not client.connect():
        log.error(
            "Cannot connect to %s:%d. Is the simulator running?", args.host, args.port
        )
        return 1
    try:
        poll(client, args.count)
    except ModbusException as error:
        log.error("Connection lost: %s", error)
        return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
