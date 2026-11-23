"""Poll the turbine over Modbus TCP and archive every reading in SQLite."""

import argparse
import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

import config
from historian.database import connect, insert_measurement
from register_map import INPUT_REGISTERS, decode

RECONNECT_DELAY_S = 5.0
SUMMARY_INTERVAL = 60

log = logging.getLogger(__name__)


def poll_once(client: ModbusTcpClient, connection: sqlite3.Connection) -> bool:
    """Read the input registers once and store the decoded values."""
    response = client.read_input_registers(
        INPUT_REGISTERS[0].address,
        count=len(INPUT_REGISTERS),
        device_id=config.MODBUS_DEVICE_ID,
    )
    if response.isError():
        log.warning("Read failed: %s", response)
        return False
    insert_measurement(connection, datetime.now(UTC), decode(response.registers))
    return True


def run(client: ModbusTcpClient, connection: sqlite3.Connection) -> None:
    """Poll on a fixed schedule, reconnecting whenever the server is unreachable."""
    connected = False
    stored = 0
    next_poll = time.monotonic()
    while True:
        if not connected:
            connected = client.connect()
            if not connected:
                log.warning("Server unreachable, retrying in %.0f s", RECONNECT_DELAY_S)
                time.sleep(RECONNECT_DELAY_S)
                next_poll = time.monotonic()
                continue
            log.info("Connected to the Modbus server")

        try:
            if poll_once(client, connection):
                stored += 1
                if stored % SUMMARY_INTERVAL == 0:
                    log.info("%d measurements stored", stored)
        except (ModbusException, OSError) as error:
            log.warning("Connection lost: %s", error)
            client.close()
            connected = False
            continue

        # Schedule from the previous target time so the period does not drift.
        next_poll += config.UPDATE_PERIOD_S
        time.sleep(max(0.0, next_poll - time.monotonic()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turbine historian")
    parser.add_argument("--host", default=config.MODBUS_HOST, help="server address")
    parser.add_argument(
        "--port", type=int, default=config.MODBUS_PORT, help="server TCP port"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=config.DATABASE_PATH,
        help="SQLite database file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

    connection = connect(args.database)
    client = ModbusTcpClient(args.host, port=args.port)
    log.info("Polling %s:%d, archiving to %s", args.host, args.port, args.database)
    try:
        run(client, connection)
    except KeyboardInterrupt:
        log.info("Historian stopped")
    finally:
        client.close()
        connection.close()


if __name__ == "__main__":
    main()
