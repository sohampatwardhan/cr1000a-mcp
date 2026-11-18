from __future__ import annotations

import json
from typing import Any

import requests

from cr1000a_mcp.check import describe, run_checks


def test_describe_never_includes_values() -> None:
    value = {"hostname": "my-secret-laptop", "mac": "aa:bb:cc:dd:ee:ff", "n": 3, "ok": True}
    shape = describe(value)
    assert shape == {"hostname": "str", "mac": "str", "n": "int", "ok": "bool"}
    assert "secret" not in json.dumps(shape)


def test_describe_collapses_large_dicts_so_mac_keys_do_not_leak() -> None:
    value = {f"aa:bb:cc:dd:ee:{i:02x}": {"bytes_rx": i} for i in range(30)}
    shape = describe(value)
    assert shape == {"dict_keys": 30, "value": {"bytes_rx": "int"}}
    assert "aa:bb" not in json.dumps(shape)


def test_describe_lists() -> None:
    assert describe([{"a": 1}, {"a": 2}]) == {"list": 2, "item": {"a": "int"}}
    assert describe([]) == {"list": 0, "item": None}


class OkClient:
    def fetch_status(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return {"uptime": "10"}, {}

    def fetch_known_devices(self) -> list[Any]:
        return [{"hostname": "x"}]

    def get_bandwidth_history_rates(self) -> list[list[int]]:
        return [[1, 2]]

    def get_host_traffic_stats(self) -> dict[int, Any]:
        return {3600: {"aa:bb": {"bytes_rx": 1}}}

    def get_dns_entries_v4(self) -> list[Any]:
        return []

    def get_dns_entries_v6(self) -> list[Any]:
        return []

    def get_port_forwarding_settings(self) -> dict[str, Any]:
        return {"portforwardings": []}

    def get_pinhole_settings(self) -> dict[str, Any]:
        return {"pinholes": []}


def test_run_checks_records_failures_without_raising() -> None:
    # OkClient has no page support, so the five page checks fail, the rest pass.
    report = run_checks(OkClient())
    assert report["passed"] == 8
    assert report["failed"] == 5
    assert report["results"]["status"] == {"ok": True, "shape": {"uptime": "str"}}
    assert report["results"]["page:arp"] == {"ok": False, "error": "AttributeError"}


def test_http_status_is_reported_but_not_the_message() -> None:
    class Forbidden(OkClient):
        def fetch_known_devices(self) -> list[Any]:
            resp = requests.Response()
            resp.status_code = 403
            raise requests.HTTPError("403 for url https://192.168.1.1/secret", response=resp)

    entry = run_checks(Forbidden())["results"]["known_devices"]
    assert entry == {"ok": False, "error": "HTTPError", "http_status": 403}
