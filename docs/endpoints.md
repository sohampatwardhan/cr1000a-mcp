# CR1000A web API endpoints

Verizon does not document this API. Everything below was read from the router web
UI's own JavaScript bundles (served without login) and from the
[`verizon-router-client`](https://pypi.org/project/verizon-router-client/) source.

**Status legend**

- **client**: used by `verizon-router-client` and therefore exercised by this server
- **tool**: exposed through `get_router_page` (read-only allowlist)
- **seen**: referenced by the UI, never called by us. Response shapes are unknown.

Run `cr1000a-mcp check` (see the README) against a real router to turn "seen" into
verified shapes.

## Data pages: `GET /cgi/cgi_<name>.js` (login required)

Each page is a script of `addROD("key", value);` and `addCfg("key", "enc", "value");`
calls.

| Area | Pages | Status |
| --- | --- | --- |
| Used by client | `status`, `owl` (known devices), `bandwith` (sic), `firewall_port_forward`, `firewall_pinholes`, `dns_server` | client |
| Read-only tools | `arp`, `net_connections`, `log`, `upnp`, `firmware` | tool |
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
