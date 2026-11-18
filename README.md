# cr1000a-mcp

An [MCP](https://modelcontextprotocol.io) server for the Verizon CR1000A (Fios) router. Ask
your AI assistant who is on your network, what your WAN address is, or to add a local DNS
record.

Verizon publishes no API for this router. The server talks to the router's undocumented
web-UI API (`cgi/*.js` endpoints behind a `sysauth` cookie login) through the community
[`verizon-router-client`](https://pypi.org/project/verizon-router-client/) library. Read
paths were validated on a real CR1000A running firmware **3.6.0.5_BD**; see
[`docs/endpoints.md`](https://github.com/sohampatwardhan/cr1000a-mcp/blob/main/docs/endpoints.md) for every endpoint and verified response shape.

## Quick start

You need [`uv`](https://docs.astral.sh/uv/) and your router's **Network Settings Password**
(printed on the router's sticker).

```bash
# 1. Put your settings in a .env file (or export them)
cat > .env <<'EOF'
ROUTER_IP=192.168.1.1
NETWORK_SETTINGS_PASSWORD=the-password-from-the-sticker
EOF
chmod 600 .env

# 2. Check that everything works (read-only; prints response shapes, never values)
uvx cr1000a-mcp check
```

`uvx cr1000a-mcp` with no arguments starts the MCP server on stdio.

## Add it to your AI client

**Claude Code**

```bash
claude mcp add cr1000a \
  --env ROUTER_IP=192.168.1.1 \
  --env NETWORK_SETTINGS_PASSWORD=the-password-from-the-sticker \
  -- uvx cr1000a-mcp
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "cr1000a": {
      "command": "uvx",
      "args": ["cr1000a-mcp"],
      "env": {
        "ROUTER_IP": "192.168.1.1",
        "NETWORK_SETTINGS_PASSWORD": "the-password-from-the-sticker"
      }
    }
  }
}
```

The server is read-only until you also set `CR1000A_MCP_ALLOW_WRITE=1` (see below).

## Configuration

Set as environment variables, or in a `.env` file in the working directory.

| Variable | Default | Notes |
| --- | --- | --- |
| `VZ_ROUTER_IP` | _(unset)_ | Router IP or hostname, optionally with `:port` (`192.168.1.1`, `router.lan`, `[fe80::1]:8443`). HTTPS is added; `http://` is rejected. Alias: `ROUTER_IP`. `mynetworksettings.com` also works if it resolves on your network |
| `VZ_ROUTER_BASE_URL` | `https://192.168.1.1` | Full URL. If set, it wins over the IP variables |
| `VZ_ROUTER_USERNAME` | `admin` | The router's login page has no username field; leave the default |
| `VZ_ROUTER_PASSWORD` | _(empty)_ | Network Settings Password |
| `NETWORK_SETTINGS_PASSWORD` | _(unset)_ | Alias for the password, used only when `VZ_ROUTER_PASSWORD` is empty |
| `CR1000A_MCP_ALLOW_WRITE` | off | Set to `1` to register the write tools |

The router's TLS certificate is issued by Verizon's own CA for `mynetworksettings.com`. The
client bundles that CA and sets the right server name when you connect by IP, so leave
certificate verification on.

## Tools

Read-only (always available):

| Tool | Returns |
| --- | --- |
| `router_status` | uptime, WAN IPv4/IPv6, WAN DNS servers |
| `list_devices` | known devices. Default is 13 fields per device; options `name_contains`, `limit`, `fields`, `verbose` |
| `get_bandwidth_history` | recent WAN throughput series |
| `get_host_traffic` | per-device traffic counters by period |
| `list_dns_records` / `list_dns_records_v6` | local DNS records |
| `list_port_forwards` | port-forwarding rules (user and UPnP) |
| `list_ipv6_pinholes` | IPv6 pinhole rules |
| `get_router_page` | one allowlisted page: `arp`, `net_connections`, `log`, `upnp`, `firmware`. Secret-named fields (passwords, keys, tokens) are returned as `[redacted]` |

Write tools, registered only when `CR1000A_MCP_ALLOW_WRITE=1`:

| Tool | Effect |
| --- | --- |
| `add_dns_record`, `remove_dns_record`, `remove_dns_record_v6` | local DNS records (adding IPv6 records is not supported by the underlying client) |
| `add_port_forward`, `remove_port_forward` | port forwards. A forward opens a port to the internet |
| `add_ipv6_pinhole`, `remove_ipv6_pinhole` | inbound IPv6 firewall holes |

Inputs are validated before the router is contacted, and a failed write is never retried.

## Verify the write tools on your router

The write tools have not been verified against every firmware. To prove them on your own router, run the
self-cleaning write test. It adds a throwaway DNS record, checks it appears, removes it, and
checks it is gone:

```bash
uvx cr1000a-mcp write-test                  # DNS record only
uvx cr1000a-mcp write-test --port-forward   # also a throwaway port forward
```

It prints what it will change and asks for confirmation first (`--yes` skips the prompt). It
refuses to start if a leftover `cr1000a-mcp-test` entry exists, always tries to clean up even
when a check fails, and tells you where to delete the entry by hand if removal fails.

## Commands

| Command | What it does |
| --- | --- |
| `cr1000a-mcp` | start the MCP server (stdio) |
| `cr1000a-mcp check` | log in once and run every read-only call; prints response shapes and the firmware version, never values. Safe to paste into an issue |
| `cr1000a-mcp write-test` | live test of the write tools (see above) |

Log out of the router's web UI before running `check` or `write-test`: the router may allow
only one admin session.

## Caveats

- Unofficial: a firmware update can change the endpoints. Run `check` after updating.
- Logging in may end an active web-UI session on the router.
- Only firmware 3.6.0.5_BD has been verified.

## Changelog and contributing

Bug reports, firmware compatibility reports and pull requests are welcome. See
[CONTRIBUTING.md](https://github.com/sohampatwardhan/cr1000a-mcp/blob/main/CONTRIBUTING.md) for development setup, the issue-first workflow, how to
run the live checks, and how releases work. Release notes are in
[CHANGELOG.md](https://github.com/sohampatwardhan/cr1000a-mcp/blob/main/CHANGELOG.md).

## License

MIT
