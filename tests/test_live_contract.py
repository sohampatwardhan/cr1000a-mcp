"""Contract tests against field names recorded from a real CR1000A.

The fixture holds names only (no values). If a firmware update renames fields,
re-run ``cr1000a-mcp check`` and refresh the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

from cr1000a_mcp.pages import REDACTED, redact
from cr1000a_mcp.shape import DEFAULT_DEVICE_FIELDS, compact_devices

LIVE = json.loads((Path(__file__).parent / "fixtures" / "live_cr1000a_3.6.0.5_BD.json").read_text())
FIELDS = LIVE["known_device_record_fields"]


def fake_device(i: int) -> dict[str, str]:
    return {name: f"{name}-{i}" for name in FIELDS}


def test_recorded_firmware_version() -> None:
    assert LIVE["firmware"]["router_version"] == "3.6.0.5_BD"


def test_device_records_have_41_fields() -> None:
    assert len(FIELDS) == 41 and len(set(FIELDS)) == 41


def test_default_device_fields_exist_on_the_live_router() -> None:
    missing = [f for f in DEFAULT_DEVICE_FIELDS if f not in FIELDS]
    assert missing == []


def test_default_view_is_much_smaller_than_the_raw_record() -> None:
    out = compact_devices([fake_device(1)])["devices"][0]
    assert set(out) == set(DEFAULT_DEVICE_FIELDS)
    assert len(out) < len(FIELDS) / 2
    assert "user_agent" not in out


def test_custom_fields_and_verbose() -> None:
    custom = compact_devices([fake_device(1)], fields=["hostname", "user_agent"])["devices"][0]
    assert set(custom) == {"hostname", "user_agent"}
    assert set(compact_devices([fake_device(1)], verbose=True)["devices"][0]) == set(FIELDS)


def test_falls_back_to_scalar_fields_if_firmware_renames_everything() -> None:
    renamed = [{"new_name": "x", "new_ip": "y", "nested": {"a": 1}}]
    assert compact_devices(renamed)["devices"] == [{"new_name": "x", "new_ip": "y"}]


def test_every_live_secret_named_setting_is_redacted() -> None:
    settings = {name: "super-secret" for name in LIVE["net_connections_secret_named_settings"]}
    settings["dhcp_enable0"] = "1"
    out = redact(settings)
    assert "super-secret" not in json.dumps(out)
    assert all(out[n] == REDACTED for n in LIVE["net_connections_secret_named_settings"])
    assert out["dhcp_enable0"] == "1"


def test_log_page_has_only_firewall_log_flags_no_entries() -> None:
    assert LIVE["log_page_settings"][0] == "log_all"
    assert not any("entry" in k or "line" in k for k in LIVE["log_page_settings"])
