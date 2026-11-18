from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from verizon_router_client.cr1000a import VerizonRouterClient

from cr1000a_mcp import RouterConnection, build_server
from cr1000a_mcp.pages import SAFE_PAGES, cap, fetch_page

SCRIPT = (
    'addROD("arp_table", [{"ip":"192.168.1.10","mac":"aa:bb"},'
    '{"ip":"192.168.1.20","mac":"cc:dd"}]);\n'
    'addROD("count", "2");\n'
    'addCfg("fw_version", "enc123", "1.2.3");\n'
)


@dataclass
class Resp:
    text: str


class PageClient:
    """Fake client that reuses the real parsers."""

    _parse_addrod = staticmethod(VerizonRouterClient._parse_addrod)
    _parse_addcfg = staticmethod(VerizonRouterClient._parse_addcfg)

    def __init__(self, text: str = SCRIPT) -> None:
        self.text = text
        self.paths: list[str] = []

    def _get(self, path: str) -> Resp:
        self.paths.append(path)
        return Resp(self.text)


def test_fetch_page_parses_rod_and_cfg() -> None:
    client = PageClient()
    out = fetch_page(client, "arp")
    assert client.paths == ["/cgi/cgi_arp.js"]
    assert out["page"] == "arp"
    assert out["data"]["arp_table"][0] == {"ip": "192.168.1.10", "mac": "aa:bb"}
    assert out["settings"] == {"fw_version": "1.2.3"}


@pytest.mark.parametrize("bad", ["cgi_upload", "lan_restore", "../status", "eng", "wifi_primary"])
def test_non_allowlisted_pages_are_rejected_without_a_request(bad: str) -> None:
    client = PageClient()
    with pytest.raises(ValueError):
        fetch_page(client, bad)
    assert client.paths == []


def test_empty_page_is_an_error() -> None:
    with pytest.raises(RuntimeError):
        fetch_page(PageClient("<html>login</html>"), "log")


def test_cap_truncates_lists_and_strings() -> None:
    out = cap({"a": list(range(5)), "s": "x" * 20}, limit=2, max_str=10)
    assert out["a"] == [0, 1, "...[3 more items truncated]"]
    assert out["s"].endswith("...[truncated]")


def test_allowlist_excludes_dangerous_pages() -> None:
    for name in ("lan_restore", "diagnostics", "eng", "odm", "ui_admin", "wifi_primary"):
        assert name not in SAFE_PAGES


async def test_tool_registered_and_calls_client() -> None:
    client = PageClient()
    server = build_server(RouterConnection(lambda: client), allow_write=False)
    async with Client(server) as c:
        names = {t.name for t in await c.list_tools()}
        result = await c.call_tool("get_router_page", {"page": "firmware"})
        with pytest.raises(ToolError):
            await c.call_tool("get_router_page", {"page": "lan_restore"})
    assert "get_router_page" in names
    assert result.data["settings"]["fw_version"] == "1.2.3"
