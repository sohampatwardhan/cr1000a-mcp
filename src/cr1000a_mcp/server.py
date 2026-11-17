"""MCP server for the Verizon CR1000A router.

Wraps the community ``verizon-router-client`` library, which speaks the router's
undocumented web-UI API. Read tools are always registered. Write tools (DNS
records, port forwards) are registered only when ``CR1000A_MCP_ALLOW_WRITE=1``.

Connection settings come from ``VZ_ROUTER_*`` environment variables (or a
``.env`` file in the working directory): ``VZ_ROUTER_BASE_URL``,
``VZ_ROUTER_USERNAME``, ``VZ_ROUTER_PASSWORD``.
"""

from __future__ import annotations

import ipaddress
import os
import threading
from collections.abc import Callable
from typing import Any, TypeVar

import requests
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

T = TypeVar("T")

WRITE_ENV = "CR1000A_MCP_ALLOW_WRITE"
_TRUTHY = {"1", "true", "yes", "on"}


def writes_enabled() -> bool:
    return os.environ.get(WRITE_ENV, "").strip().lower() in _TRUTHY


def _default_connect() -> Any:
    from verizon_router_client.config import connect

    return connect()


class RouterConnection:
    """Lazily logs in, serialises access, and re-logs in once if a read fails.

    The router allows few concurrent sessions, so all calls share one client
    guarded by a lock.
    """

    def __init__(self, factory: Callable[[], Any] = _default_connect) -> None:
        self._factory = factory
        self._client: Any | None = None
        self._lock = threading.Lock()

    def call(self, fn: Callable[[Any], T], *, retry: bool = True) -> T:
        """Run ``fn(client)``. Retries once after a fresh login when ``retry``.

        Writes pass ``retry=False`` so a half-applied change is never repeated.
        """
        with self._lock:
            if self._client is None:
                self._client = self._factory()
            try:
                return fn(self._client)
            except (requests.RequestException, RuntimeError):
                self._client = None
                if not retry:
                    raise
                self._client = self._factory()
                return fn(self._client)


def _valid_ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError as exc:
        raise ValueError(f"Not a valid IPv4 address: {value!r}") from exc


def _valid_port(value: int, label: str) -> int:
    if not 1 <= value <= 65535:
        raise ValueError(f"{label} must be between 1 and 65535, got {value}")
    return value


READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
DELETE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)


def build_server(
    connection: RouterConnection | None = None, *, allow_write: bool | None = None
) -> FastMCP:
    conn = connection or RouterConnection()
    write = writes_enabled() if allow_write is None else allow_write
    mcp = FastMCP("cr1000a")

    # ---- read tools -------------------------------------------------------

    @mcp.tool(annotations=READ)
    def router_status() -> dict[str, Any]:
        """Uptime (seconds), WAN IPv4/IPv6 addresses and WAN DNS servers."""

        def run(c: Any) -> dict[str, Any]:
            rod, cfg = c.fetch_status()
            uptime = rod.get("uptime")
            dns = cfg.get("wan_ip4_dns")
            return {
                "uptime_seconds": int(uptime) if str(uptime).isdigit() else None,
                "wan_ipv4": rod.get("get_wan4_ip") or None,
                "wan_ipv6": rod.get("cgi_wan_ip6_addr") or None,
                "wan_dns_servers": dns.val.split() if dns and dns.val.strip() else [],
            }

        return conn.call(run)

    @mcp.tool(annotations=READ)
    def list_devices() -> list[dict[str, Any]]:
        """Devices the router knows about (connected and previously seen)."""
        return conn.call(lambda c: c.fetch_known_devices())

    @mcp.tool(annotations=READ)
    def get_bandwidth_history() -> list[list[int]]:
        """Recent WAN throughput samples as a list of integer series."""
        return conn.call(lambda c: c.get_bandwidth_history_rates())

    @mcp.tool(annotations=READ)
    def get_host_traffic() -> dict[str, dict[str, dict[str, int]]]:
        """Per-device traffic counters, keyed by period in seconds then MAC."""

        def run(c: Any) -> dict[str, dict[str, dict[str, int]]]:
            return {str(k): v for k, v in c.get_host_traffic_stats().items()}

        return conn.call(run)

    @mcp.tool(annotations=READ)
    def list_dns_records() -> list[dict[str, Any]]:
        """Local IPv4 DNS records as ``{idx, name, ip}`` rows."""
        return conn.call(lambda c: c.get_dns_entries_v4())

    @mcp.tool(annotations=READ)
    def list_port_forwards() -> dict[str, Any]:
        """Configured port-forwarding rules."""
        return conn.call(lambda c: c.get_port_forwarding_settings())

    if not write:
        return mcp

    # ---- write tools (opt-in) --------------------------------------------

    @mcp.tool(annotations=WRITE)
    def add_dns_record(hostname: str, ip: str) -> dict[str, Any]:
        """Add a local IPv4 DNS record. Returns the slot used."""
        ip = _valid_ipv4(ip)
        if not hostname.strip():
            raise ValueError("hostname must not be empty")
        slot = conn.call(lambda c: c.add_dns_ipv4(hostname.strip(), ip), retry=False)
        return {"slot": slot, "hostname": hostname.strip(), "ip": ip}

    @mcp.tool(annotations=DELETE)
    def remove_dns_record(hostname: str, remove_all: bool = False) -> dict[str, Any]:
        """Remove the local IPv4 DNS record for ``hostname`` (first match unless
        ``remove_all``). Returns the cleared slots."""
        removed = conn.call(
            lambda c: c.remove_dns_ipv4_by_hostname(hostname, remove_all=remove_all),
            retry=False,
        )
        return {"removed_slots": removed}

    @mcp.tool(annotations=WRITE)
    def add_port_forward(
        name: str,
        private_ip: str,
        forward_port: int,
        dest_port: int,
        protocol: str = "both",
    ) -> dict[str, Any]:
        """Create a port-forward: external ``forward_port`` -> ``private_ip``:
        ``dest_port``. ``protocol`` is tcp, udp or both. Returns the rule id."""
        protocol = protocol.lower()
        if protocol not in {"tcp", "udp", "both"}:
            raise ValueError("protocol must be tcp, udp or both")
        private_ip = _valid_ipv4(private_ip)
        _valid_port(forward_port, "forward_port")
        _valid_port(dest_port, "dest_port")
        rule_id = conn.call(
            lambda c: c.add_port_forward(
                name=name,
                private_ip=private_ip,
                forward_port=forward_port,
                dest_port=dest_port,
                protocol=protocol,
            ),
            retry=False,
        )
        return {"rule_id": rule_id}

    @mcp.tool(annotations=DELETE)
    def remove_port_forward(rule_id: int) -> dict[str, Any]:
        """Delete the port-forward rule with the given id (see list_port_forwards)."""
        conn.call(lambda c: c.remove_port_forward(rule_id=rule_id), retry=False)
        return {"removed_rule_id": rule_id}

    return mcp


def main() -> None:
    build_server().run()
