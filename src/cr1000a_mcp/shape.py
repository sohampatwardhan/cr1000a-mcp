"""Helpers that shrink router payloads to what an LLM actually needs.

The router returns large, firmware-specific blobs. These helpers are shape-based
(they do not depend on exact field names) so they keep working across firmware.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DEFAULT_LIMIT = 50

# Fields kept per device by default. Chosen from the 41 fields a real CR1000A
# (firmware 3.6.0.5_BD) returns per device; pass ``fields`` or ``verbose`` for more.
DEFAULT_DEVICE_FIELDS: tuple[str, ...] = (
    "name",
    "hostname",
    "ip",
    "ipv6",
    "mac",
    "mac_vendor",
    "ui_type",
    "ui_manufacturer",
    "ui_model",
    "activity",
    "port",
    "is_dhcp",
    "time_last_active",
)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def compact_record(record: Any) -> Any:
    """Keep scalar, non-empty fields of a dict; pass non-dicts through."""
    if not isinstance(record, dict):
        return record
    return {k: v for k, v in record.items() if _is_scalar(v) and v != "" and v is not None}


def _matches(record: Any, needle: str) -> bool:
    needle = needle.lower()
    if isinstance(record, dict):
        return any(needle in str(v).lower() for v in record.values() if _is_scalar(v))
    return needle in str(record).lower()


def select_fields(record: Any, fields: Sequence[str]) -> Any:
    """Keep only ``fields`` (when present and non-empty).

    If none of the wanted fields exist (for example after a firmware change
    renames them) fall back to every scalar field rather than returning nothing.
    """
    if not isinstance(record, dict):
        return record
    picked = {k: record[k] for k in fields if k in record and record[k] not in ("", None)}
    return picked or compact_record(record)


def compact_devices(
    devices: list[Any],
    *,
    name_contains: str = "",
    limit: int = DEFAULT_LIMIT,
    verbose: bool = False,
    fields: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Filter, trim and cap a device list.

    ``name_contains`` matches case-insensitively against any scalar field
    (hostname, IP, MAC, ...). Records are cut to ``fields`` (default
    ``DEFAULT_DEVICE_FIELDS``); ``verbose`` keeps the raw records.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    matched = [d for d in devices if not name_contains or _matches(d, name_contains)]
    page = matched[:limit]
    return {
        "total": len(devices),
        "matched": len(matched),
        "returned": len(page),
        "truncated": len(matched) > len(page),
        "devices": page
        if verbose
        else [select_fields(d, fields or DEFAULT_DEVICE_FIELDS) for d in page],
    }


def compact_port_forwards(
    settings: dict[str, Any], *, include_readonly: bool = False
) -> dict[str, Any]:
    """Keep only the port-forward rules; drop schedule and reserved-port data."""
    rules = settings.get("portforwardings") or []
    upnp = settings.get("upnpportforwardings") or []
    readonly = settings.get("readonly_portforwardings") or []
    out: dict[str, Any] = {
        "rules": rules,
        "upnp_rules": upnp,
        "readonly_rule_count": len(readonly),
    }
    if include_readonly:
        out["readonly_rules"] = readonly
    return out
