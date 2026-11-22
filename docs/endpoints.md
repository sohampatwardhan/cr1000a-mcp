# CR1000A web API endpoints

Verizon does not document this API. Everything below was read from the router web
UI's own JavaScript bundles (served without login) and from the
[`verizon-router-client`](https://pypi.org/project/verizon-router-client/) source.

**Status legend**

- **client**: used by `verizon-router-client` and therefore exercised by this server
- **tool**: exposed through `get_router_page` (read-only allowlist)
- **seen**: referenced by the UI, never called by us. Response shapes are unknown.
- **verified**: called against a real CR1000A with `cr1000a-mcp check`; shape recorded below

Run `cr1000a-mcp check` (see the README) against a router to verify more pages.

## Data pages: `GET /cgi/cgi_<name>.js` (login required)

Each page is a script of `addROD("key", value);` and `addCfg("key", "enc", "value");`
calls.

| Area | Pages | Status |
| --- | --- | --- |
| Used by client | `status`, `owl` (known devices), `bandwith` (sic), `firewall_port_forward`, `firewall_pinholes`, `dns_server` | client, verified |
| Read-only tools | `arp`, `net_connections`, `log`, `upnp`, `firmware` | tool, verified |
| Status and clients | `home`, `known_devices`, `ndp`, `bh_log`, `cellular_signal`, `diagnostics` | seen |
| Firewall and NAT | `firewall_general`, `firewall_port_trigger`, `firewall_static_nat`, `firewall_access_control`, `port_conf`, `port_rule`, `dmz`, `sipalg`, `parental`, `scheduler`, `network_object` | seen |
| LAN and WAN | `ip_distribution`, `ipv6`, `ipv6_distribution`, `dynamic_dns`, `routing`, `ntp`, `wan_mac_clone`, `lan_restore` | seen |
| Wi-Fi | `wifi_primary`, `wifi_channel_settings` (mode and width keys read, see below), `wifi_guest`, `wifi_iot`, `wifi_channel`, `wifi_channel_history`, `wifi_qos`, `wifi_wps`, `wifi_add_dev_modal` | seen |
| Admin and misc | `ui_admin`, `ui_remote_admin`, `router_led`, `basic`, `zenreach`, `eng`, `odm` | seen |

## Action endpoints

| Endpoint | Purpose | Status |
| --- | --- | --- |
| `loginStatus.cgi` | login token and session state | client |
| `login.cgi` | log in (sets `sysauth` cookie) | client |
| `logout.cgi` | log out | seen |
| `db.cgi` | structured writes; targets `forwardrule`, `portrule`, `pinholerule`, `staticnat`, `triggerrule`, `routes6`, `schedulerule`, `parentalrule`, `multi_parentalrule`, `netobj`, `multi_netobj`, `accesscontrol` | client (`forwardrule`, `pinholerule`) |
| `apply_abstract.cgi` | form-style writes (for example DNS via `dnsmasq_reload`) | client |
| `quick_setup.cgi`, `quick_setup_status.cgi` | setup wizard | seen |
| `diagnostics.cgi` | run diagnostics | seen |
| `clearlog.cgi` | clear logs | seen |
| `analysis.cgi` | analytics | seen |
| `cgi_upload.cgi`, `cgi_config_file.js` | firmware and config upload or export | seen |

## Deliberately not exposed

These can change or wipe the device, or may leak secrets, so no tool reaches them:

- `cgi_upload.cgi`, `lan_restore`, `clearlog.cgi`, `diagnostics.cgi`, `quick_setup.cgi`
- `eng`, `odm` (engineering pages)
- `wifi_*` and `ui_admin` pages until confirmed free of Wi-Fi passphrases and admin
  settings; if exposed later they must redact secrets

`get_router_page` enforces this with an allowlist (`src/cr1000a_mcp/pages.py`) and
rejects any other name before making a request.

## Verified shapes

From live `cr1000a-mcp check` runs on 2026-11-17: **13 of 13 read checks passed** against a
CR1000A running firmware **3.6.0.5_BD (May 13, 2026)**. Reports contain shapes and field
names only (no values). Counts are from one household and will vary. Recorded names live in
`tests/fixtures/live_cr1000a_3.6.0.5_BD.json` and are checked by `tests/test_live_contract.py`.

| Check | Shape |
| --- | --- |
| `status` (`fetch_status`) | dict of 15 keys, each a list of lists of strings (the `addROD` payload; uptime and WAN fields are read from it by the client) |
| `known_devices` (`owl`) | list of 76 records, 41 fields each: `activity`, `activity_ip`, `activity_ipv6`, `activity_ipv6_ll`, `bridge_port`, `dev_class`, `device`, `device_firmware`, `device_manufacturer`, `device_model`, `device_os`, `device_product`, `device_sub_model`, `dhcpv6_rq_list`, `dhcpv6_vendor_class`, `display`, `hostname`, `icon_id`, `ip`, `ipv6`, `ipv6_ll`, `is_dhcp`, `location`, `mac`, `mac_vendor`, `mobility`, `name`, `os`, `port`, `pre_port`, `request_list`, `suggested_name`, `time_first_seen`, `time_last_active`, `ui_manufacturer`, `ui_model`, `ui_os`, `ui_type`, `uptime`, `user_agent`, `vendor_id` |
| `bandwidth_history` | 3 series of 16 integers |
| `host_traffic` | 5 periods, each keyed by MAC; per host `packets_tx`, `bytes_tx`, `packets_rx`, `bytes_rx` (ints) |
| `dns_v4`, `dns_v6` | list of `{idx, name, ip}` rows (empty on this router) |
| `port_forwarding` | `portforwardings`: `id`, `enable`, `name`, `privateIP`, `port_rule_id`, `forward_port`, `schedule_rule_id`, `snat_enable`, `snat_id`. `upnpportforwardings`: `ip`, `proto`, `eport`, `iport`. `readonly_portforwardings`: `enable`, `privateIP`, `proto`, `publicPort`, `privatePort`. Plus `portrules` (16 entries), `schedulerules`, `reservePort` (2 ints) |
| `ipv6_pinholes` | `pinholes` (empty here), `portrules` (16 entries: `id`, `name`, `description`, `used`, `ports`), `schedulerules` |
| `page:arp` | `data.dump_arp_list` (list of dicts, 32 here); `settings`: `net_name`, `broad_name` |
| `page:net_connections` | `data` keys: `eth_status_list`, `get_interface_rate`, `get_ipv6_link_local_addr`, `get_moca_lan_coordinator`, `get_moca_lan_devcie`, `get_moca_state`, `get_wlan_used_5g`, `ipv6_active_rules`, `known_device_list`, `rTable`, `routes6_Table`, `wan_lease_time`, `wan_phy_status`, `wan_state`, `wifi_bh`. `settings`: 219 keys (LAN/DHCP, WAN, IPv6, MoCA, routing table), **including `moca_password0`, `moca_password1` and `moca_manual_pw1`, which `get_router_page` redacts** |
| `page:log` | `data`: `szLocalTime`, `cfglogTime`; `settings`: 16 firewall logging toggles (`log_all`, `log_in`, `log_out`, `log_syn`, ...). **No log lines**: the entries must come from another page (candidate: `bh_log`) |
| `page:upnp` | `data` empty; `settings`: `upnp_enable`, `upnp_autoclean`. The live UPnP mappings are in `port_forwarding.upnpportforwardings` |
| `page:firmware` | `data`: `router_version`, `router_date`, `router_driver`, `router_commit`; `settings` empty |

### Station records (PHY mode)

`cgi_owl.js` (and `cgi_basic.js`) carry `dump_toplogy_station_info` (sic), whose `stations`
list has one record per associated device. Verified live on 2026-11-22, firmware 3.6.0.5_BD.
Fields: `airtime_util`, `alias_name`, `ant_r_num`, `ant_s_num`, `ant_t_num`, `ap_ant_rssi`,
`as`, `assoc_time`, `bandwidth`, `br`, `bs`, `channel`, `connect_bssid`, `connect_intf`,
`connect_type`, `es`, `frc`, `ipv6_ip`, `last_connect`, `lddr`, `ldur`, `link_rate`,
`link_rate_max`, `max_rx_phy_rate`, `max_tx_phy_rate`, `mode`, `mrc`, `node_id`, `note`,
`online`, `parent_id`, `parent_mac`, `pid`, `rc`, `rt`, `rtc`, `rxc`, `rxmo`, `rxmo_max`,
`signal_strength`, `signal_strength_max`, `signal_strength_min`, `snr`, `spl_airtime`,
`spl_ap_ant_rssi`, `spl_rx_rate`, `spl_tx_rate`, `station_ip`, `station_mac`, `station_name`,
`tx_link_rate`, `tx_link_rate_max`, `txc`, `txmo`, `txmo_max`, `txop`. Join to known devices on
`station_mac` = `mac`.

The router does not label `mode` or `bandwidth`. Decoded by comparing with band and maximum PHY
rate (`src/cr1000a_mcp/stations.py`):

| `mode` | Seen on | Max PHY rates seen | Decoded as |
| --- | --- | --- | --- |
| `0` | Ether | 100 Mbps | wired |
| `5` | 2.4G | 72-260 Mbps | 802.11n |
| `7` | 5G, 20 MHz | 65-72 Mbps | 802.11n |
| `8` | 5G, 80 MHz | 866, 1300 Mbps | 802.11ac |
| `11` | 2.4G, 5G, 6G | 143-2401 Mbps | 802.11ax (6E on 6G) |

`bandwidth`: `0` = 20 MHz, `3` = 80 MHz, `5` = 160 MHz. Other codes are reported as unknown.
Note that `ha-verizonFiOS` counts mode `7` as Wi-Fi 5, which this data contradicts.

### Wi-Fi mode and width settings

Which standards each radio accepts is a setting, readable from `cgi_wifi_primary.js` and
`cgi_wifi_channel_settings.js` (both carry the same `Wireless_mode*` keys). Read on 2026-11-22,
firmware 3.6.0.5_BD. These pages are **not** on the allowlist: they also hold SSIDs and other
settings that may include passphrases. Only the keys below were read, and any secret-named key
was skipped.

| Key | Value seen | Reading |
| --- | --- | --- |
| `Wireless_mode24G` | `bgnhe` | 2.4 GHz accepts 802.11b, g, n and ax |
| `Wireless_mode5G_H` | `anvhe` | 5 GHz accepts 802.11a, n, ac and ax |
| `Wireless_mode6G` | `he` | 6 GHz accepts ax only |
| `Wireless_mode24G_he`, `Wireless_mode5G_H_he`, `Wireless_mode6G_he` | `1` | high-efficiency (Wi-Fi 6) enabled per band |
| `Wireless_mode24G_turboqam`, `Wireless_mode5G_H_turboqam`, `Wireless_mode6G_turboqam` | `1` | meaning not confirmed (likely 1024-QAM) |
| `channel_width24G`, `channel_width5G_H`, `channel_width6G` | `40`, `80`, `160` | configured channel width in MHz |
| `triband_mode` | `2` | meaning not confirmed |

The letters are read as `b`/`g`/`a`/`n` = the legacy standards, `v` = VHT (ac), `he` = ax; the
router does not document them. The router accepts legacy clients by configuration, but none was
connected during the station check above, so the `mode` codes a b, g or a client reports are
unknown. `decode_mode` shows `unknown (mode N)` with the raw code if one appears.

### Findings that changed the design

- **Secrets in data pages.** `net_connections.settings` carries MoCA passwords. Every value
  returned by `get_router_page` passes through `redact()` (`src/cr1000a_mcp/pages.py`), which
  replaces the value of any secret-named field (`password`, `passwd`, `passphrase`, `psk`,
  `secret`, `token`, `api_key`, trailing `_pw`/`_pw<n>`) with `[redacted]` and keeps the key.
  This is why `wifi_*` and `ui_admin` stay off the allowlist: they very likely hold more.
- `get_router_page("log")` returns only the firewall logging toggles and times, not log
  entries. Check `bh_log` before promising a log tool.
- `get_router_page("upnp")` returns only enable flags; use `list_port_forwards`, which
  reports the `upnp_rules`.
- Device records have 41 fields. `list_devices` now returns a 13-field default
  (`name`, `hostname`, `ip`, `ipv6`, `mac`, `mac_vendor`, `ui_type`, `ui_manufacturer`,
  `ui_model`, `activity`, `port`, `is_dhcp`, `time_last_active`); use `fields=[...]` for
  others (for example `user_agent`, `os`, `time_first_seen`) or `verbose=True` for all.
- `net_connections` is large (219 settings) even with the list cap.

## Write paths: verification status

Verified with `cr1000a-mcp write-test` on a real CR1000A, firmware 3.6.0.5_BD, 2026-11-17.

| Tool | Endpoint | Status |
| --- | --- | --- |
| `add_dns_record`, `remove_dns_record` | `apply_abstract.cgi` (`dnsmasq_reload`) | verified live |
| `add_port_forward`, `remove_port_forward` | `db.cgi` (`forwardrule`) | verified live (`write-test --port-forward`) |
| `remove_dns_record_v6` | `apply_abstract.cgi` | not verified (the client cannot add IPv6 records, so there is no round trip to test) |
| `add_ipv6_pinhole`, `remove_ipv6_pinhole` | `db.cgi` (`pinholerule`) | not verified; no live test yet |
