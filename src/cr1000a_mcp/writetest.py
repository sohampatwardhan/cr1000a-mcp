"""``cr1000a-mcp write-test``: exercise the write tools on a real router, safely.

Adds one throwaway DNS record (and, with ``--port-forward``, one throwaway port
forward to an unused LAN address), checks it shows up, removes it, and checks it
is gone. Cleanup is always attempted, even when a verification step fails.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastmcp import Client

TEST_NAME = "cr1000a-mcp-test"
TEST_IP = "192.168.1.250"  # nothing needs to live here; a DNS record is just a name
TEST_PORT = 54321


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


async def _call(client: Client, tool: str, args: dict[str, Any]) -> Any:
    return (await client.call_tool(tool, args)).data


def _has_dns(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("name") == TEST_NAME]


def _test_rules(listing: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in listing.get("rules", []) if r.get("name") == TEST_NAME]


async def dns_stage(client: Client, steps: list[Step]) -> None:
    if _has_dns(await _call(client, "list_dns_records", {})):
        steps.append(
            Step(
                "no leftover test DNS record",
                False,
                f"a record named {TEST_NAME} already exists; delete it in the router web UI "
                "(Network Settings > DNS Server) and re-run",
            )
        )
        return
    steps.append(Step("no leftover test DNS record", True))
    try:
        await _call(client, "add_dns_record", {"hostname": TEST_NAME, "ip": TEST_IP})
        after = _has_dns(await _call(client, "list_dns_records", {}))
        shown = any(r.get("ip") == TEST_IP for r in after)
        steps.append(Step("add_dns_record: record appears in list_dns_records", shown))
    except Exception as exc:
        steps.append(Step("add_dns_record", False, type(exc).__name__))
    finally:
        try:
            await _call(client, "remove_dns_record", {"hostname": TEST_NAME, "remove_all": True})
            gone = not _has_dns(await _call(client, "list_dns_records", {}))
            steps.append(
                Step(
                    "remove_dns_record: record is gone",
                    gone,
                    "" if gone else f"delete {TEST_NAME} manually in the web UI (DNS Server)",
                )
            )
        except Exception as exc:
            steps.append(
                Step(
                    "remove_dns_record",
                    False,
                    f"{type(exc).__name__}; delete {TEST_NAME} manually in the web UI (DNS Server)",
                )
            )


async def port_forward_stage(client: Client, steps: list[Step]) -> None:
    if _test_rules(await _call(client, "list_port_forwards", {})):
        steps.append(
            Step(
                "no leftover test port forward",
                False,
                f"a port forward named {TEST_NAME} already exists; delete it in the web UI "
                "(Firewall > Port Forwarding) and re-run",
            )
        )
        return
    steps.append(Step("no leftover test port forward", True))
    try:
        added = await _call(
            client,
            "add_port_forward",
            {
                "name": TEST_NAME,
                "private_ip": TEST_IP,
                "forward_port": TEST_PORT,
                "dest_port": TEST_PORT,
                "protocol": "tcp",
            },
        )
        rule_id = added.get("rule_id")
        rules = _test_rules(await _call(client, "list_port_forwards", {}))
        shown = any(r.get("id") == rule_id for r in rules)
        steps.append(Step("add_port_forward: rule appears in list_port_forwards", shown))
    except Exception as exc:
        steps.append(Step("add_port_forward", False, type(exc).__name__))
    finally:
        try:
            for rule in _test_rules(await _call(client, "list_port_forwards", {})):
                await _call(client, "remove_port_forward", {"rule_id": rule["id"]})
            gone = not _test_rules(await _call(client, "list_port_forwards", {}))
            steps.append(
                Step(
                    "remove_port_forward: rule is gone",
                    gone,
                    "" if gone else f"delete {TEST_NAME} manually in the web UI (Port Forwarding)",
                )
            )
        except Exception as exc:
            steps.append(
                Step(
                    "remove_port_forward",
                    False,
                    f"{type(exc).__name__}; delete {TEST_NAME} manually in the web UI "
                    "(Port Forwarding)",
                )
            )


async def run(server: Any, *, port_forward: bool = False) -> list[Step]:
    steps: list[Step] = []
    async with Client(server) as client:
        await dns_stage(client, steps)
        if port_forward:
            await port_forward_stage(client, steps)
    return steps


def format_steps(steps: list[Step]) -> str:
    lines = []
    for s in steps:
        mark = "PASS" if s.ok else "FAIL"
        lines.append(f"[{mark}] {s.name}" + (f" -- {s.detail}" if s.detail else ""))
    return "\n".join(lines)


def main(*, yes: bool = False, port_forward: bool = False) -> int:
    from cr1000a_mcp.server import build_server, load_settings

    base_url = load_settings().base_url
    plan = [f"add then remove DNS record {TEST_NAME} -> {TEST_IP}"]
    if port_forward:
        plan.append(f"add then remove TCP port forward {TEST_PORT} -> {TEST_IP}:{TEST_PORT}")
    print(f"Router: {base_url}")
    print("This will change the router's configuration, then undo it:")
    for item in plan:
        print(f"  - {item}")
    if not yes and input("Type 'yes' to continue: ").strip().lower() != "yes":
        print("Aborted; nothing was changed.")
        return 2

    steps = asyncio.run(run(build_server(allow_write=True), port_forward=port_forward))
    print(format_steps(steps))
    ok = all(s.ok for s in steps)
    print("\nAll steps passed." if ok else "\nSome steps failed; see above for cleanup.")
    return 0 if ok else 1
