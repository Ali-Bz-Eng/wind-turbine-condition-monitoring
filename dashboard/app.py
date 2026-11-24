"""Operator dashboard serving live values, trends and the alarm journal."""

import argparse
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template

import config
from analytics.rules import HIGH_LIMITS
from historian.database import (
    connect,
    fetch_alarms,
    fetch_latest,
    fetch_since,
    format_timestamp,
)
from register_map import INPUT_REGISTERS

TREND_WINDOW_S = 600
ALARM_COUNT = 20
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000


def trend_window(connection: sqlite3.Connection) -> list[dict]:
    """Measurements from the last trend window, ending at the newest reading.

    Anchoring the window to the newest reading keeps older runs out of the
    trend and still shows the last recorded period when data has stopped.
    """
    latest = fetch_latest(connection, 1)
    if not latest:
        return []
    newest = datetime.fromisoformat(latest[0]["timestamp"])
    start = newest - timedelta(seconds=TREND_WINDOW_S)
    return fetch_since(connection, format_timestamp(start))


def signal_settings() -> list[dict]:
    """Display settings for each signal, derived from the register map and rules."""
    limits = {limit.signal: limit.limit for limit in HIGH_LIMITS}
    return [
        {
            "name": register.name,
            "label": register.name.replace("_", " ").capitalize(),
            "unit": register.unit,
            "decimals": register.decimals,
            "alarm_limit": limits.get(register.name),
        }
        for register in INPUT_REGISTERS
    ]


def create_app(database_path: Path = config.DATABASE_PATH) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = database_path

    def database() -> sqlite3.Connection:
        if "database" not in g:
            g.database = connect(app.config["DATABASE_PATH"])
        return g.database

    @app.teardown_appcontext
    def close_database(_error: BaseException | None) -> None:
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    @app.get("/")
    def index() -> str:
        return render_template("index.html", signals=signal_settings())

    @app.get("/api/measurements")
    def measurements() -> Response:
        return jsonify(
            server_time=format_timestamp(datetime.now(UTC)),
            measurements=trend_window(database()),
        )

    @app.get("/api/alarms")
    def alarms() -> Response:
        return jsonify(alarms=fetch_alarms(database(), ALARM_COUNT))

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turbine operator dashboard")
    parser.add_argument("--host", default=DEFAULT_HOST, help="listening address")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="listening TCP port"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    create_app().run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
