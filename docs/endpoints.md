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
| Wi-Fi | `wifi_primary`, `wifi_guest`, `wifi_iot`, `wifi_channel`, `wifi_channel_history`, `wifi_channel_settings`, `wifi_qos`, `wifi_wps`, `wifi_add_dev_modal` | seen |
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

From a live `cr1000a-mcp check` on 2026-11-17: **13 of 13 read checks passed** against a
CR1000A. The report contains shapes only (no values). Counts are from one household and
will vary.

| Check | Shape |
| --- | --- |
| `status` (`fetch_status`) | dict of 15 keys, each a list of lists of strings (the `addROD` payload; uptime and WAN fields are read from it by the client) |
| `known_devices` (`owl`) | list of records; 41 fields per record (names recorded by the next `check` run) |
| `bandwidth_history` | 3 series of 16 integers |
| `host_traffic` | 5 periods, each keyed by MAC; per host `packets_tx`, `bytes_tx`, `packets_rx`, `bytes_rx` (ints) |
| `dns_v4`, `dns_v6` | list of `{idx, name, ip}` rows (empty on this router) |
| `port_forwarding` | `portforwardings`: `id`, `enable`, `name`, `privateIP`, `port_rule_id`, `forward_port`, `schedule_rule_id`, `snat_enable`, `snat_id`. `upnpportforwardings`: `ip`, `proto`, `eport`, `iport`. `readonly_portforwardings`: `enable`, `privateIP`, `proto`, `publicPort`, `privatePort`. Plus `portrules` (16 entries), `schedulerules`, `reservePort` (2 ints) |
| `ipv6_pinholes` | `pinholes` (empty here), `portrules` (16 entries: `id`, `name`, `description`, `used`, `ports`), `schedulerules` |
| `page:arp` | `data.dump_arp_list` (list of dicts, 32 here); `settings`: `net_name`, `broad_name` |
| `page:net_connections` | `data`: 15 keys; `settings`: 219 keys (large) |
| `page:log` | `data`: `szLocalTime`, `cfglogTime`; `settings`: 16 keys. **No log lines**: the entries must come from another page (candidate: `bh_log`) |
| `page:upnp` | `data` empty; `settings`: `upnp_enable`, `upnp_autoclean`. The live UPnP mappings are in `port_forwarding.upnpportforwardings` |
| `page:firmware` | `data`: `router_version`, `router_date`, `router_driver`, `router_commit`; `settings` empty |

### Findings that changed the design

- `get_router_page("log")` does not return log entries. Treat it as time metadata until
  `bh_log` (or similar) is checked.
- `get_router_page("upnp")` returns only the enable flags; use `list_port_forwards`, which
  reports the `upnp_rules`.
- `net_connections.settings` has 219 keys, so that page is large even with the list cap.
- Device records have 41 fields; `list_devices` still returns every scalar field per device.
  Field names are printed by the updated `check` so a curated subset can be chosen.
