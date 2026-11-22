from __future__ import annotations

import pytest

from cr1000a_mcp.stations import attach_phy, decode_mode, stations_by_mac, summarize_station

# (band, mode code, bandwidth code, max PHY rate) combinations recorded from a real
# CR1000A (firmware 3.6.0.5_BD), with the label they decode to.
LIVE_COMBOS = [
    ("2.4G", "5", "0", "72Mbps", "802.11n (Wi-Fi 4)", 20),
    ("2.4G", "11", "0", "143Mbps", "802.11ax (Wi-Fi 6)", 20),
    ("5G", "7", "0", "65Mbps", "802.11n (Wi-Fi 4)", 20),
    ("5G", "8", "3", "866Mbps", "802.11ac (Wi-Fi 5)", 80),
    ("5G", "11", "3", "1201Mbps", "802.11ax (Wi-Fi 6)", 80),
    ("6G", "11", "5", "2401Mbps", "802.11ax (Wi-Fi 6E)", 160),
    ("Ether", "0", "0", "100Mbps", "wired", 20),
]


@pytest.mark.parametrize(("band", "mode", "bw", "rate", "label", "width"), LIVE_COMBOS)
def test_recorded_combinations_decode(band, mode, bw, rate, label, width) -> None:
    out = summarize_station(
        {
            "connect_type": band,
            "mode": mode,
            "bandwidth": bw,
            "max_rx_phy_rate": rate,
            "max_tx_phy_rate": rate,
        }
    )
    assert out["phy_mode"] == label
    assert out["channel_width_mhz"] == width
    assert out["max_phy_rate_mbps"] == int(rate.removesuffix("Mbps"))


def test_unseen_mode_is_reported_not_guessed() -> None:
    assert decode_mode("9", "5G") == "unknown (mode 9)"
    out = summarize_station({"connect_type": "5G", "mode": "9", "bandwidth": "7"})
    assert out["phy_mode_code"] == "9"
    assert "channel_width_mhz" not in out


def test_empty_and_malformed_values_are_dropped() -> None:
    out = summarize_station({"connect_type": "5G", "mode": "8", "link_rate": "n/a", "channel": ""})
    assert "link_rate_mbps" not in out and "channel" not in out


def test_station_lookup_is_case_insensitive_and_tolerates_missing_variable() -> None:
    raw = {
        "dump_toplogy_station_info": {
            "stations": [{"station_mac": "AA:BB", "mode": "8", "connect_type": "5G"}]
        }
    }
    assert stations_by_mac(raw)["aa:bb"]["phy_mode"] == "802.11ac (Wi-Fi 5)"
    assert stations_by_mac({}) == {}


def test_attach_phy_leaves_unmatched_and_non_dict_devices_alone() -> None:
    devices = [{"mac": "AA:BB"}, {"mac": "CC:DD"}, "odd"]
    out = attach_phy(devices, {"aa:bb": {"phy_mode": "wired"}})
    assert out == [{"mac": "AA:BB", "phy_mode": "wired"}, {"mac": "CC:DD"}, "odd"]
    assert devices[0] == {"mac": "AA:BB"}
