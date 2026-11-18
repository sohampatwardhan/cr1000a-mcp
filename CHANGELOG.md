# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may change behaviour).

## [Unreleased]

## [0.2.0] - 2026-11-17

### Added

- `cr1000a-mcp write-test`: adds then removes a throwaway DNS record (and, with
  `--port-forward`, a throwaway port forward) to prove the write tools work on your router.
  Asks for confirmation, refuses to start if a leftover test entry exists, always attempts
  cleanup, and exits non-zero if any step fails.
- `CONTRIBUTING.md` and this changelog.

### Changed

- README rewritten for end users: `uvx` install, current client configs, full tool and
  configuration reference. Developer and release material moved to `CONTRIBUTING.md`. This is
  now the description shown on PyPI (the 0.1.0 page showed an outdated README).
- README links to repository files are absolute so they work on PyPI.
- PyPI sidebar gains Changelog and Documentation links.

### Notes

- The write tools (DNS, port forwards, IPv6 pinholes) are still tested with fakes only in CI;
  run `cr1000a-mcp write-test` to verify them on your router.

## [0.1.0] - 2026-11-17

First release, published to PyPI.

### Added

- MCP server for the Verizon CR1000A over stdio, built on FastMCP and the community
  `verizon-router-client` library.
- Read tools: `router_status`, `list_devices`, `get_bandwidth_history`, `get_host_traffic`,
  `list_dns_records`, `list_dns_records_v6`, `list_port_forwards`, `list_ipv6_pinholes`, and
  `get_router_page` (allowlist: `arp`, `net_connections`, `log`, `upnp`, `firmware`).
- Write tools, registered only with `CR1000A_MCP_ALLOW_WRITE=1`: `add_dns_record`,
  `remove_dns_record`, `remove_dns_record_v6`, `add_port_forward`, `remove_port_forward`,
  `add_ipv6_pinhole`, `remove_ipv6_pinhole`. Inputs are validated before any router call and
  failed writes are never retried.
- `cr1000a-mcp check`: logs in once, runs every read-only call and prints response shapes and
  the firmware version, never values.
- Settings: `VZ_ROUTER_IP` (alias `ROUTER_IP`) for the router address and
  `NETWORK_SETTINGS_PASSWORD` as an alias for `VZ_ROUTER_PASSWORD`, each read from the
  environment or a `.env` file. `VZ_ROUTER_BASE_URL` still wins when set.
- `docs/endpoints.md`: every endpoint found in the router's web UI, with verified response
  shapes, and recorded field names with contract tests for firmware 3.6.0.5_BD.
- CI (lint, tests on Python 3.12 and 3.13, build) and a tag-triggered release workflow using
  PyPI trusted publishing.

### Changed

- `list_devices` returns a 13-field default per device (the router sends 41) with
  `name_contains`, `limit`, `fields` and `verbose` options; `list_port_forwards` returns only
  user and UPnP rules.

### Security

- `get_router_page` redacts the values of secret-named fields. The `net_connections` page
  includes `moca_password0`, `moca_password1` and `moca_manual_pw1`, which would otherwise
  have been returned.
- `http://` router addresses are rejected so the password is never sent in clear text.
- `check` prints shapes only, and never dict keys that could be MAC addresses, IPs or
  hostnames.

### Verified

- All read paths against a real CR1000A on firmware 3.6.0.5_BD. The write tools were tested
  with fakes only at this release.

[Unreleased]: https://github.com/sohampatwardhan/cr1000a-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sohampatwardhan/cr1000a-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sohampatwardhan/cr1000a-mcp/releases/tag/v0.1.0
