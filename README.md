# cr1000a-mcp

An [MCP](https://modelcontextprotocol.io) server for the Verizon CR1000A (Fios) router.

Verizon publishes no API for this router. The server talks to the router's undocumented
web-UI API (`cgi/*.js` endpoints behind a `sysauth` cookie login) through the community
[`verizon-router-client`](https://pypi.org/project/verizon-router-client/) library.

## Tools

Read-only (always available):

| Tool | Returns |
| --- | --- |
| `router_status` | uptime, WAN IPv4/IPv6, WAN DNS servers |
| `list_devices` | known devices |
| `get_bandwidth_history` | recent WAN throughput series |
| `get_host_traffic` | per-device traffic counters by period |
| `list_dns_records` | local IPv4 DNS records |
| `list_port_forwards` | port-forwarding rules |
| `list_dns_records_v6` | local IPv6 DNS records |
| `list_ipv6_pinholes` | IPv6 pinhole rules |
| `get_router_page` | one allowlisted data page: `arp`, `net_connections`, `log`, `upnp`, `firmware` |

Write tools, registered only when `CR1000A_MCP_ALLOW_WRITE=1`:
`add_dns_record`, `remove_dns_record`, `remove_dns_record_v6`, `add_port_forward`,
`remove_port_forward`, `add_ipv6_pinhole`, `remove_ipv6_pinhole`. (Adding IPv6 DNS records is not
supported by the underlying client.)
Inputs are validated before the router is contacted, and failed writes are never retried.

## Configuration

Set via environment variables (or a `.env` file in the working directory):

| Variable | Default | Notes |
| --- | --- | --- |
| `VZ_ROUTER_BASE_URL` | `https://192.168.1.1` | full URL; wins over the IP variables below |
| `VZ_ROUTER_IP` | _(unset)_ | router IP or hostname, optionally `:port` (for example `192.168.1.1`); HTTPS is added. Alias: `ROUTER_IP`. `http://` is rejected |
| `VZ_ROUTER_USERNAME` | `admin` | |
| `VZ_ROUTER_PASSWORD` | _(empty)_ | router admin password ("Network Settings Password" on the router's sticker) |
| `NETWORK_SETTINGS_PASSWORD` | _(unset)_ | alias, used only when `VZ_ROUTER_PASSWORD` is empty; read from the environment or `.env` |
| `CR1000A_MCP_ALLOW_WRITE` | off | set to `1` to enable write tools |

The router's certificate is bound to `mynetworksettings.com`; the client sets SNI/Host
automatically when you connect by IP and bundles the Verizon root CA.

## Install

Once published to PyPI (see Releasing), run it without cloning:

```bash
uvx cr1000a-mcp          # start the MCP server
uvx cr1000a-mcp check    # live read-only validation
```

Until then, use `uv run --directory /path/to/cr1000a-mcp cr1000a-mcp` as shown below.

## Use with Claude Code

```bash
claude mcp add cr1000a \
  --env VZ_ROUTER_PASSWORD=your-admin-password \
  -- uv run --directory /path/to/cr1000a-mcp cr1000a-mcp
```

## Use with Claude Desktop

```json
{
  "mcpServers": {
    "cr1000a": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/cr1000a-mcp", "cr1000a-mcp"],
      "env": { "VZ_ROUTER_PASSWORD": "your-admin-password" }
    }
  }
}
```

## Live check

`cr1000a-mcp check` logs in once, runs every read-only call against your router and prints a
JSON report of response **shapes** (types, counts, key names; never values), so it is safe to
paste into an issue. It never calls a write endpoint.

```bash
uv run cr1000a-mcp check
```

Exit code is 0 when every check passes. Log out of the router's web UI first, since the
router may allow only one session.

## Caveats

- Unofficial: firmware updates can change the endpoints.
- Logging in may end an active web-UI session on the router.
- All read paths were validated against a real CR1000A (see `docs/endpoints.md`); write tools are tested with fakes only. Run `cr1000a-mcp check` to validate your own firmware.

## Releasing

Publishing uses PyPI trusted publishing (no API token). One-time setup, by the repo owner:

1. On PyPI, add a *pending publisher* for project `cr1000a-mcp`: owner `sohampatwardhan`,
   repository `cr1000a-mcp`, workflow `release.yml`, environment `pypi`.
2. In GitHub, create an environment named `pypi` (optionally require a reviewer).

To release: bump `version` in `pyproject.toml`, merge, then tag and push:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The workflow checks the tag matches the package version, runs lint and tests, builds, and
publishes.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```
