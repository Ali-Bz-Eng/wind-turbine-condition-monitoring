"""Tests for the register map encoding and decoding."""

import pytest

from register_map import INPUT_REGISTERS, REGISTER_MAX_VALUE, decode, encode

SAMPLE = {
    "rotor_speed": 14.5,
    "power_output": 1830.0,
    "gearbox_temperature": 76.2,
    "vibration": 2.54,
}


def test_encode_applies_scales() -> None:
    assert encode(SAMPLE) == [145, 1830, 762, 254]


def test_decode_restores_values() -> None:
    decoded = decode(encode(SAMPLE))
    for name, value in SAMPLE.items():
        assert decoded[name] == pytest.approx(value)


def test_encode_clamps_to_register_range() -> None:
    out_of_range = dict(SAMPLE, rotor_speed=-3.0, power_output=1_000_000.0)
    registers = encode(out_of_range)
    assert registers[0] == 0
    assert registers[1] == REGISTER_MAX_VALUE


def test_decimals_follow_scale() -> None:
    assert [register.decimals for register in INPUT_REGISTERS] == [1, 0, 1, 2]
