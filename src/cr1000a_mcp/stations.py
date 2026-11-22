"""Wi-Fi station records: PHY mode, band, width and rates per connected device.

The router publishes one record per associated station in the
``dump_toplogy_station_info`` variable (sic) of ``cgi_owl.js`` and ``cgi_basic.js``.
The router does not label the numeric ``mode`` and ``bandwidth`` fields; the tables
below were decoded from a real CR1000A (firmware 3.6.0.5_BD) by comparing them with
band and maximum PHY rate. Codes not seen there are reported as ``unknown`` along with
the raw code, never guessed.
"""

from __future__ import annotations

import re
from typing import Any

# Fields added to a device that has a station record, and kept in the default view.
DEFAULT_STATION_FIELDS: tuple[str, ...] = ("band", "phy_mode")

_VARIABLE = "dump_toplogy_station_info"
_PAGES = ("owl", "basic")

# (mode code, band is 6 GHz) -> label. Code 11 is 802.11ax everywhere.
_MODES = {
    "5": "802.11n (Wi-Fi 4)",
    "7": "802.11n (Wi-Fi 4)",
    "8": "802.11ac (Wi-Fi 5)",
}
# bandwidth code -> MHz. Only codes observed against known PHY rates.
_WIDTH_MHZ = {"0": 20, "3": 80, "5": 160}
_RATE = re.compile(r"(\d+)")


def decode_mode(code: Any, band: str) -> str:
    """Human label for a station's ``mode`` code on ``band`` (``connect_type``)."""
    code = str(code)
    if band == "Ether":
        return "wired"
    if code == "11":
        return "802.11ax (Wi-Fi 6E)" if band == "6G" else "802.11ax (Wi-Fi 6)"
    return _MODES.get(code, f"unknown (mode {code})")


def _rate(value: Any) -> int | None:
    match = _RATE.match(str(value))
    return int(match.group(1)) if match else None


def summarize_station(station: dict[str, Any]) -> dict[str, Any]:
    """The PHY-related fields of one raw station record, with empty values dropped."""
    band = str(station.get("connect_type", ""))
    code = station.get("mode", "")
    max_rates = [
        r
        for r in (_rate(station.get("max_rx_phy_rate")), _rate(station.get("max_tx_phy_rate")))
        if r
    ]
    summary = {
        "band": band,
        "channel": station.get("channel"),
        "phy_mode": decode_mode(code, band),
        "phy_mode_code": str(code),
        "channel_width_mhz": _WIDTH_MHZ.get(str(station.get("bandwidth", ""))),
        "max_phy_rate_mbps": max(max_rates) if max_rates else None,
        "link_rate_mbps": _rate(station.get("link_rate")),
        "tx_link_rate_mbps": _rate(station.get("tx_link_rate")),
    }
    return {k: v for k, v in summary.items() if v not in ("", None)}


def stations_by_mac(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map lower-case MAC -> summary from a parsed ``addROD`` payload."""
    stations = (raw.get(_VARIABLE) or {}).get("stations") or []
    out: dict[str, dict[str, Any]] = {}
    for station in stations:
        mac = str(station.get("station_mac", "")).lower()
        if mac:
            out[mac] = summarize_station(station)
    return out


def fetch_stations(client: Any) -> dict[str, dict[str, Any]]:
    """Station summaries keyed by MAC, or ``{}`` if no page carries the variable."""
    for page in _PAGES:
        text = client._get(f"/cgi/cgi_{page}.js").text
        found = stations_by_mac(client._parse_addrod(text))
        if found:
            return found
    return {}


def attach_phy(devices: list[Any], stations: dict[str, dict[str, Any]]) -> list[Any]:
    """Copy of ``devices`` with PHY fields added to each one that is on Wi-Fi or wired now."""
    out = []
    for device in devices:
        mac = str(device.get("mac", "")).lower() if isinstance(device, dict) else ""
        out.append({**device, **stations[mac]} if mac in stations else device)
    return out
