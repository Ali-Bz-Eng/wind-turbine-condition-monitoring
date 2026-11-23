"""Tests for a single historian polling cycle."""

from pathlib import Path

from historian.database import connect, fetch_latest
from historian.poller import poll_once


class FakeResponse:
    def __init__(self, registers: list[int], error: bool = False) -> None:
        self.registers = registers
        self._error = error

    def isError(self) -> bool:  # noqa: N802
        return self._error


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def read_input_registers(
        self, address: int, *, count: int, device_id: int
    ) -> FakeResponse:
        return self.response


def test_successful_read_is_stored(tmp_path: Path) -> None:
    connection = connect(tmp_path / "historian.db")
    client = FakeClient(FakeResponse([145, 1830, 762, 254]))
    assert poll_once(client, connection) is True
    rows = fetch_latest(connection, 10)
    connection.close()
    assert len(rows) == 1
    assert rows[0]["gearbox_temperature"] == 76.2


def test_failed_read_is_not_stored(tmp_path: Path) -> None:
    connection = connect(tmp_path / "historian.db")
    client = FakeClient(FakeResponse([], error=True))
    assert poll_once(client, connection) is False
    rows = fetch_latest(connection, 10)
    connection.close()
    assert rows == []
