from __future__ import annotations

import pytest

from cr1000a_mcp.shape import compact_devices, compact_port_forwards, compact_record

DEVICES = [
    {"hostname": "Laptop", "ip": "192.168.1.10", "mac": "aa:bb", "extra": {"x": 1}, "note": ""},
    {"hostname": "NAS", "ip": "192.168.1.20", "mac": "cc:dd", "tags": [1, 2]},
    {"hostname": "Phone", "ip": "192.168.1.30", "mac": "ee:ff"},
]


def test_compact_record_drops_nested_and_empty() -> None:
    assert compact_record(DEVICES[0]) == {
        "hostname": "Laptop",
        "ip": "192.168.1.10",
        "mac": "aa:bb",
    }


def test_compact_record_keeps_zero_and_false() -> None:
    assert compact_record({"n": 0, "b": False, "e": None, "s": ""}) == {"n": 0, "b": False}


def test_filter_is_case_insensitive_across_fields() -> None:
    assert compact_devices(DEVICES, name_contains="nas")["matched"] == 1
    assert (
        compact_devices(DEVICES, name_contains="192.168.1.3")["devices"][0]["hostname"] == "Phone"
    )
    assert compact_devices(DEVICES, name_contains="EE:FF")["matched"] == 1


def test_limit_and_truncation() -> None:
    out = compact_devices(DEVICES, limit=2)
    assert (out["total"], out["matched"], out["returned"], out["truncated"]) == (3, 3, 2, True)


def test_verbose_keeps_raw_records() -> None:
    assert compact_devices(DEVICES, verbose=True)["devices"][0]["extra"] == {"x": 1}


def test_invalid_limit() -> None:
    with pytest.raises(ValueError):
        compact_devices(DEVICES, limit=0)


def test_port_forwards_drop_unneeded_blobs() -> None:
    settings = {
        "portforwardings": [{"id": 1}],
        "upnpportforwardings": [{"id": 2}],
        "readonly_portforwardings": [{"id": 3}, {"id": 4}],
        "portrules": {"big": "x"},
        "schedulerules": {"big": "y"},
        "reservePort": [1, 2, 3],
    }
    out = compact_port_forwards(settings)
    assert out == {"rules": [{"id": 1}], "upnp_rules": [{"id": 2}], "readonly_rule_count": 2}
    assert "readonly_rules" in compact_port_forwards(settings, include_readonly=True)
