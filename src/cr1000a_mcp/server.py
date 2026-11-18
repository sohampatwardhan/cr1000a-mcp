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
import re
import threading
from collections.abc import Callable
from typing import Any, TypeVar

import requests
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from cr1000a_mcp.pages import DEFAULT_ITEM_LIMIT, PageName, fetch_page
from cr1000a_mcp.shape import DEFAULT_LIMIT, compact_devices, compact_port_forwards

T = TypeVar("T")

WRITE_ENV = "CR1000A_MCP_ALLOW_WRITE"
_TRUTHY = {"1", "true", "yes", "on"}


def writes_enabled() -> bool:
    return os.environ.get(WRITE_ENV, "").strip().lower() in _TRUTHY


PASSWORD_ALIAS = "NETWORK_SETTINGS_PASSWORD"
IP_VARS = ("VZ_ROUTER_IP", "ROUTER_IP")
_HOSTNAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")


def router_url(value: str) -> str:
    """Turn a router IP or hostname (optionally with a port) into an https URL.

    Accepts ``192.168.1.1``, ``192.168.1.1:8443``, ``router.lan``, ``fe80::1`` or
    ``[fe80::1]:8443``. The router is always reached over HTTPS: an ``http://``
    value is rejected so the password is never sent in clear text.
    """
    raw = value.strip()
    if not raw:
        raise ValueError("router IP must not be empty")
    if raw.lower().startswith("http://"):
        raise ValueError("router IP must not use http://; the router is reached over HTTPS")
    if raw.lower().startswith("https://"):
        raw = raw[len("https://") :].rstrip("/")
    if not raw or any(c in raw for c in " \t/@?#\\"):
        raise ValueError(f"Not a valid router address: {value!r}")

    port = ""
    if raw.startswith("["):
        host, sep, rest = raw[1:].partition("]")
        if not sep or (rest and not rest.startswith(":")):
            raise ValueError(f"Not a valid router address: {value!r}")
        try:
            ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise ValueError(f"Not a valid router address: {value!r}") from exc
        port = rest[1:] if rest else ""
        host = f"[{host}]"
    else:
        try:
            ipaddress.IPv6Address(raw)  # bare IPv6 literal, no port
            host = f"[{raw}]"
        except ValueError:
            host, _, port = raw.partition(":") if raw.count(":") == 1 else (raw, "", "")
            if raw.count(":") > 1 or not _HOSTNAME.match(host):
                raise ValueError(f"Not a valid router address: {value!r}") from None
    if port and not (port.isdigit() and 1 <= int(port) <= 65535):
        raise ValueError(f"Not a valid port in router address: {value!r}")
    return f"https://{host}" + (f":{port}" if port else "")


def _lookup(*names: str) -> str | None:
    """First non-empty value among ``names`` from the environment, then ``.env``."""
    from dotenv import dotenv_values

    file_values = dotenv_values(".env")
    for name in names:
        value = os.environ.get(name) or file_values.get(name)
        if value:
            return value
    return None


def load_settings() -> Any:
    """Router settings from ``VZ_ROUTER_*`` plus two friendlier aliases.

    - password: ``NETWORK_SETTINGS_PASSWORD`` when ``VZ_ROUTER_PASSWORD`` is empty
    - address: ``VZ_ROUTER_IP`` or ``ROUTER_IP`` when ``VZ_ROUTER_BASE_URL`` is not set

    Each is read from the environment, then ``.env``.
    """
    from pydantic import SecretStr
    from verizon_router_client.config import RouterSettings

    settings = RouterSettings()
    update: dict[str, Any] = {}
    if not settings.password.get_secret_value():
        alias = _lookup(PASSWORD_ALIAS)
        if alias:
            update["password"] = SecretStr(alias)
    if "base_url" not in settings.model_fields_set:
        ip = _lookup(*IP_VARS)
        if ip:
            update["base_url"] = router_url(ip)
    return settings.model_copy(update=update) if update else settings


def _default_connect() -> Any:
    from verizon_router_client.config import connect

    return connect(load_settings())


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


def _valid_ipv6(value: str) -> str:
    try:
        return str(ipaddress.IPv6Address(value))
    except ValueError as exc:
        raise ValueError(f"Not a valid IPv6 address: {value!r}") from exc


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
    def list_devices(
        name_contains: str = "",
        limit: int = DEFAULT_LIMIT,
        verbose: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Devices the router knows about (connected and previously seen).

        ``name_contains`` filters case-insensitively on any field (hostname, IP,
        MAC). Results are capped at ``limit``. By default each device keeps a short
        field set (name, hostname, ip, ipv6, mac, mac_vendor, ui_type, ui_manufacturer,
        ui_model, activity, port, is_dhcp, time_last_active); pass ``fields`` to choose
        others (the router returns 41, for example ``user_agent``, ``os``,
        ``time_first_seen``) or ``verbose`` for everything.
        """
        devices = conn.call(lambda c: c.fetch_known_devices())
        return compact_devices(
            devices, name_contains=name_contains, limit=limit, verbose=verbose, fields=fields
        )

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
    def list_port_forwards(include_readonly: bool = False) -> dict[str, Any]:
        """Configured port-forwarding rules (user rules and UPnP rules).

        Firmware-reserved read-only rules are only counted unless
        ``include_readonly`` is true.
        """
        settings = conn.call(lambda c: c.get_port_forwarding_settings())
        return compact_port_forwards(settings, include_readonly=include_readonly)

    @mcp.tool(annotations=READ)
    def list_dns_records_v6() -> list[dict[str, Any]]:
        """Local IPv6 DNS records as ``{idx, name, ip}`` rows."""
        return conn.call(lambda c: c.get_dns_entries_v6())

    @mcp.tool(annotations=READ)
    def list_ipv6_pinholes() -> dict[str, Any]:
        """Configured IPv6 pinhole (inbound firewall) rules."""
        return {"pinholes": conn.call(lambda c: c.get_pinhole_settings()["pinholes"])}

    @mcp.tool(annotations=READ)
    def get_router_page(page: PageName, limit: int = DEFAULT_ITEM_LIMIT) -> dict[str, Any]:
        """Read one allowlisted router data page: arp (ARP table), net_connections,
        log, upnp or firmware (version info). Long lists are truncated to ``limit``.
        Fields that look like secrets (passwords, keys, tokens) are returned as
        "[redacted]". Response shapes are firmware-specific; see docs/endpoints.md."""
        return conn.call(lambda c: fetch_page(c, page, limit=limit))

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

    @mcp.tool(annotations=DELETE)
    def remove_dns_record_v6(hostname: str, remove_all: bool = False) -> dict[str, Any]:
        """Remove the local IPv6 DNS record for ``hostname`` (first match unless
        ``remove_all``). Returns the cleared slots."""
        removed = conn.call(
            lambda c: c.remove_dns_ipv6_by_hostname(hostname, remove_all=remove_all),
            retry=False,
        )
        return {"removed_slots": removed}

    @mcp.tool(annotations=WRITE)
    def add_ipv6_pinhole(private_ip: str, dest_port: int, protocol: str = "both") -> dict[str, Any]:
        """Open an inbound IPv6 pinhole to ``private_ip`` on ``dest_port``.
        ``protocol`` is tcp, udp or both. Returns the rule id."""
        protocol = protocol.lower()
        if protocol not in {"tcp", "udp", "both"}:
            raise ValueError("protocol must be tcp, udp or both")
        private_ip = _valid_ipv6(private_ip)
        _valid_port(dest_port, "dest_port")
        rule_id = conn.call(
            lambda c: c.add_ipv6_pinhole(
                private_ip=private_ip, dest_port=dest_port, protocol=protocol
            ),
            retry=False,
        )
        return {"rule_id": rule_id}

    @mcp.tool(annotations=DELETE)
    def remove_ipv6_pinhole(rule_id: int) -> dict[str, Any]:
        """Delete the IPv6 pinhole with the given id (see list_ipv6_pinholes)."""
        conn.call(lambda c: c.remove_ipv6_pinhole(rule_id=rule_id), retry=False)
        return {"removed_rule_id": rule_id}

    return mcp


def main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="cr1000a-mcp", description=__doc__.split("\n")[0])
    parser.add_argument(
        "command",
        nargs="?",
        choices=["check"],
        help="'check' runs every read-only call against the router and prints a shape report; "
        "with no command the MCP server starts on stdio",
    )
    args = parser.parse_args(argv)
    if args.command == "check":
        from cr1000a_mcp.check import main as check_main

        sys.exit(check_main())
    build_server().run()
