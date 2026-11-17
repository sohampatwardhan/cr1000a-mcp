from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cr1000a_mcp import RouterConnection, build_server

READ_TOOLS = {
    "router_status",
    "list_devices",
    "get_bandwidth_history",
    "get_host_traffic",
    "list_dns_records",
    "list_port_forwards",
}
WRITE_TOOLS = {
    "add_dns_record",
    "remove_dns_record",
    "add_port_forward",
    "remove_port_forward",
}


@dataclass
class Cfg:
    val: str


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_next = False

    def _maybe_fail(self) -> None:
        if self.fail_next:
            self.fail_next = False
            raise requests.ConnectionError("session expired")

    def fetch_status(self) -> tuple[dict[str, Any], dict[str, Cfg]]:
        self._maybe_fail()
        return (
            {"uptime": "3600", "get_wan4_ip": "203.0.113.5", "cgi_wan_ip6_addr": ""},
            {"wan_ip4_dns": Cfg("1.1.1.1 8.8.8.8")},
        )

    def fetch_known_devices(self) -> list[dict[str, Any]]:
        return [{"hostname": "laptop", "ip": "192.168.1.10"}]

    def get_bandwidth_history_rates(self) -> list[list[int]]:
        return [[1, 2, 3]]

    def get_host_traffic_stats(self) -> dict[int, dict[str, dict[str, int]]]:
        return {3600: {"aa:bb:cc:dd:ee:ff": {"bytes_rx": 5}}}

    def get_dns_entries_v4(self) -> list[dict[str, Any]]:
        return [{"idx": 0, "name": "nas", "ip": "192.168.1.20"}]

    def get_port_forwarding_settings(self) -> dict[str, Any]:
        return {"portforwardings": {}}

    def add_dns_ipv4(self, hostname: str, ip: str) -> int:
        self.calls.append(f"add_dns {hostname} {ip}")
        return 3

    def remove_dns_ipv4_by_hostname(self, hostname: str, *, remove_all: bool) -> list[int]:
        self.calls.append(f"rm_dns {hostname} {remove_all}")
        return [3]

    def add_port_forward(self, **kwargs: Any) -> int:
        self.calls.append(f"add_pf {sorted(kwargs.items())}")
        return 7

    def remove_port_forward(self, *, rule_id: int) -> None:
        self.calls.append(f"rm_pf {rule_id}")


def make(allow_write: bool) -> tuple[Any, FakeClient, list[int]]:
    fake = FakeClient()
    logins: list[int] = []

    def factory() -> FakeClient:
        logins.append(1)
        return fake

    server = build_server(RouterConnection(factory), allow_write=allow_write)
    return server, fake, logins


async def tool_names(server: Any) -> set[str]:
    async with Client(server) as c:
        return {t.name for t in await c.list_tools()}


async def test_read_only_by_default() -> None:
    server, _, _ = make(False)
    assert await tool_names(server) == READ_TOOLS


async def test_write_tools_registered_when_enabled() -> None:
    server, _, _ = make(True)
    assert await tool_names(server) == READ_TOOLS | WRITE_TOOLS


async def test_write_flag_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CR1000A_MCP_ALLOW_WRITE", "1")
    server = build_server(RouterConnection(FakeClient))
    assert WRITE_TOOLS <= await tool_names(server)


async def test_router_status() -> None:
    server, _, _ = make(False)
    async with Client(server) as c:
        result = await c.call_tool("router_status", {})
    assert result.data == {
        "uptime_seconds": 3600,
        "wan_ipv4": "203.0.113.5",
        "wan_ipv6": None,
        "wan_dns_servers": ["1.1.1.1", "8.8.8.8"],
    }


async def test_host_traffic_keys_are_strings() -> None:
    server, _, _ = make(False)
    async with Client(server) as c:
        result = await c.call_tool("get_host_traffic", {})
    assert list(result.data) == ["3600"]


async def test_read_retries_once_with_fresh_login() -> None:
    server, fake, logins = make(False)
    fake.fail_next = True
    async with Client(server) as c:
        result = await c.call_tool("router_status", {})
    assert result.data["wan_ipv4"] == "203.0.113.5"
    assert len(logins) == 2


async def test_add_dns_record() -> None:
    server, fake, _ = make(True)
    async with Client(server) as c:
        result = await c.call_tool("add_dns_record", {"hostname": "nas", "ip": "192.168.1.20"})
    assert result.data == {"slot": 3, "hostname": "nas", "ip": "192.168.1.20"}
    assert fake.calls == ["add_dns nas 192.168.1.20"]


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("add_dns_record", {"hostname": "x", "ip": "999.1.1.1"}),
        ("add_dns_record", {"hostname": " ", "ip": "192.168.1.2"}),
        (
            "add_port_forward",
            {"name": "x", "private_ip": "192.168.1.2", "forward_port": 0, "dest_port": 80},
        ),
        (
            "add_port_forward",
            {
                "name": "x",
                "private_ip": "192.168.1.2",
                "forward_port": 80,
                "dest_port": 80,
                "protocol": "icmp",
            },
        ),
    ],
)
async def test_invalid_write_input_is_rejected_before_router_call(
    tool: str, args: dict[str, Any]
) -> None:
    server, fake, _ = make(True)
    async with Client(server) as c:
        with pytest.raises(ToolError):
            await c.call_tool(tool, args)
    assert fake.calls == []


async def test_write_is_not_retried() -> None:
    server, fake, logins = make(True)

    def boom(**_: Any) -> int:
        raise requests.ConnectionError("down")

    fake.add_port_forward = boom  # type: ignore[method-assign]
    async with Client(server) as c:
        with pytest.raises(ToolError):
            await c.call_tool(
                "add_port_forward",
                {"name": "x", "private_ip": "192.168.1.2", "forward_port": 80, "dest_port": 80},
            )
    assert len(logins) == 1
