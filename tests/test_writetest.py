from __future__ import annotations

from typing import Any

import pytest

from cr1000a_mcp import RouterConnection, build_server
from cr1000a_mcp.server import main as cli_main
from cr1000a_mcp.writetest import TEST_IP, TEST_NAME, format_steps, run


class StatefulRouter:
    """In-memory router that stores DNS records and port forwards."""

    def __init__(self) -> None:
        self.dns: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self.next_rule = 100
        self.hide_added_dns = False  # simulate a router that does not show the new record
        self.fail_dns_remove = False
        self.calls: list[str] = []

    def get_dns_entries_v4(self) -> list[dict[str, Any]]:
        return [d for d in self.dns if not (self.hide_added_dns and d["name"] == TEST_NAME)]

    def add_dns_ipv4(self, hostname: str, ip: str) -> int:
        self.calls.append("add_dns")
        self.dns.append({"idx": len(self.dns), "name": hostname, "ip": ip})
        return len(self.dns) - 1

    def remove_dns_ipv4_by_hostname(self, hostname: str, *, remove_all: bool) -> list[int]:
        self.calls.append("remove_dns")
        if self.fail_dns_remove:
            raise RuntimeError("router refused")
        removed = [d["idx"] for d in self.dns if d["name"] == hostname]
        self.dns = [d for d in self.dns if d["name"] != hostname]
        return removed

    def get_port_forwarding_settings(self) -> dict[str, Any]:
        return {"portforwardings": list(self.rules)}

    def add_port_forward(self, **kw: Any) -> int:
        self.calls.append("add_pf")
        self.next_rule += 1
        self.rules.append({"id": self.next_rule, "name": kw["name"], "privateIP": kw["private_ip"]})
        return self.next_rule

    def remove_port_forward(self, *, rule_id: int) -> None:
        self.calls.append("remove_pf")
        self.rules = [r for r in self.rules if r["id"] != rule_id]


def server(router: StatefulRouter) -> Any:
    return build_server(RouterConnection(lambda: router), allow_write=True)


async def test_dns_stage_passes_and_leaves_router_clean() -> None:
    router = StatefulRouter()
    steps = await run(server(router))
    assert all(s.ok for s in steps), format_steps(steps)
    assert router.dns == []
    assert router.calls == ["add_dns", "remove_dns"]


async def test_port_forward_stage_passes_and_leaves_router_clean() -> None:
    router = StatefulRouter()
    steps = await run(server(router), port_forward=True)
    assert all(s.ok for s in steps), format_steps(steps)
    assert router.dns == [] and router.rules == []
    assert router.calls == ["add_dns", "remove_dns", "add_pf", "remove_pf"]


async def test_leftover_record_aborts_without_touching_the_router() -> None:
    router = StatefulRouter()
    router.dns.append({"idx": 0, "name": TEST_NAME, "ip": "10.9.9.9"})
    steps = await run(server(router))
    assert not steps[0].ok and "already exists" in steps[0].detail
    assert router.calls == []
    assert router.dns[0]["ip"] == "10.9.9.9"  # someone else's record is left alone


async def test_cleanup_still_runs_when_verification_fails() -> None:
    router = StatefulRouter()
    router.hide_added_dns = True  # add succeeds but list never shows it
    steps = await run(server(router))
    assert any(not s.ok and "appears" in s.name for s in steps)
    assert "remove_dns" in router.calls  # cleanup was attempted anyway


async def test_failed_removal_is_reported_with_manual_instructions() -> None:
    router = StatefulRouter()
    router.fail_dns_remove = True
    steps = await run(server(router))
    last = steps[-1]
    assert not last.ok and TEST_NAME in last.detail and "manually" in last.detail


async def test_only_one_throwaway_record_is_ever_written() -> None:
    router = StatefulRouter()
    await run(server(router))
    assert router.dns == [] and TEST_IP not in str(router.rules)


def test_flags_are_rejected_outside_write_test(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_main(["check", "--yes"])
    assert exc.value.code == 2
    assert "write-test" in capsys.readouterr().err


def test_write_test_aborts_without_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda _="": "no")
    with pytest.raises(SystemExit) as exc:
        cli_main(["write-test"])
    assert exc.value.code == 2
    assert "nothing was changed" in capsys.readouterr().out
