"""``cr1000a-mcp check``: run every read-only call against a live router.

Logs in once, runs each read path, and prints a JSON report of response
*shapes* (types, counts, key names). It never prints values, so the report is
safe to paste into an issue. It never calls a write endpoint.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cr1000a_mcp.pages import SAFE_PAGES, fetch_page

MAX_KEYS = 12  # dicts with more keys are summarised (keys may be MAC addresses)


def describe(value: Any, depth: int = 3) -> Any:
    """Describe the shape of ``value`` without including any scalar value."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if value is None:
        return "null"
    if depth <= 0:
        return type(value).__name__
    if isinstance(value, list):
        first = describe(value[0], depth - 1) if value else None
        return {"list": len(value), "item": first}
    if isinstance(value, dict):
        if len(value) > MAX_KEYS:
            first = describe(next(iter(value.values())), depth - 1)
            return {"dict_keys": len(value), "value": first}
        return {str(k): describe(v, depth - 1) for k, v in value.items()}
    return type(value).__name__


def _checks() -> dict[str, Callable[[Any], Any]]:
    checks: dict[str, Callable[[Any], Any]] = {
        "status": lambda c: c.fetch_status()[0],
        "known_devices": lambda c: c.fetch_known_devices(),
        "bandwidth_history": lambda c: c.get_bandwidth_history_rates(),
        "host_traffic": lambda c: {str(k): v for k, v in c.get_host_traffic_stats().items()},
        "dns_v4": lambda c: c.get_dns_entries_v4(),
        "dns_v6": lambda c: c.get_dns_entries_v6(),
        "port_forwarding": lambda c: c.get_port_forwarding_settings(),
        "ipv6_pinholes": lambda c: c.get_pinhole_settings(),
    }
    for page in SAFE_PAGES:
        checks[f"page:{page}"] = lambda c, p=page: fetch_page(c, p)
    return checks


def run_checks(client: Any) -> dict[str, Any]:
    """Run every read check; failures are recorded, not raised."""
    results: dict[str, Any] = {}
    for name, fn in _checks().items():
        try:
            results[name] = {"ok": True, "shape": describe(fn(client))}
        except Exception as exc:  # report and continue; messages may hold data
            entry: dict[str, Any] = {"ok": False, "error": type(exc).__name__}
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None:
                entry["http_status"] = status
            results[name] = entry
    ok = sum(1 for r in results.values() if r["ok"])
    return {"passed": ok, "failed": len(results) - ok, "results": results}


def main() -> int:
    from verizon_router_client.config import connect

    from cr1000a_mcp.server import load_settings

    client = connect(load_settings())
    report = run_checks(client)
    print(json.dumps(report, indent=2))
    return 0 if report["failed"] == 0 else 1
