"""The MCPB manifest must stay in step with the real server and the package version."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from typing import Any

from fastmcp import Client

from cr1000a_mcp import RouterConnection, build_server
from cr1000a_mcp.server import IP_VARS, PASSWORD_ALIAS, WRITE_ENV

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "mcpb" / "manifest.json").read_text())


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_mcpb = load_script("build_mcpb")
changelog_section = load_script("changelog_section")


def test_manifest_version_matches_package_version() -> None:
    with (ROOT / "pyproject.toml").open("rb") as f:
        assert MANIFEST["version"] == tomllib.load(f)["project"]["version"]


async def test_declared_tools_match_the_real_server() -> None:
    server = build_server(RouterConnection(lambda: object()), allow_write=True)
    async with Client(server) as client:
        real = {t.name for t in await client.list_tools()}
    declared = [t["name"] for t in MANIFEST["tools"]]
    assert sorted(declared) == sorted(set(declared)), "duplicate tool names"
    assert set(declared) == real
    assert MANIFEST["tools_generated"] is False


def test_env_vars_are_ones_the_server_reads_and_config_keys_exist() -> None:
    env = MANIFEST["server"]["mcp_config"]["env"]
    assert set(env) == {IP_VARS[1], PASSWORD_ALIAS, WRITE_ENV}
    for value in env.values():
        key = value.removeprefix("${user_config.").removesuffix("}")
        assert key in MANIFEST["user_config"], value


def test_password_is_a_required_sensitive_field_and_writes_default_off() -> None:
    config = MANIFEST["user_config"]
    password = config["network_settings_password"]
    assert password["sensitive"] is True and password["required"] is True
    assert "default" not in password  # never ship a default password
    assert config["allow_changes"]["default"] is False
    assert config["router_ip"]["default"] == "192.168.1.1"


def test_launch_command_follows_the_official_uv_example() -> None:
    server = MANIFEST["server"]
    assert MANIFEST["manifest_version"] == "0.4" and server["type"] == "uv"
    assert server["mcp_config"]["command"] == "uv"
    assert server["mcp_config"]["args"] == [
        "run",
        "--directory",
        "${__dirname}",
        server["entry_point"],
    ]
    assert (ROOT / "mcpb" / server["entry_point"]).is_file()


def test_staged_bundle_pins_the_published_package(tmp_path: Path) -> None:
    stage = build_mcpb.stage_bundle(tmp_path / "bundle", "9.9.9")
    manifest = json.loads((stage / "manifest.json").read_text())
    assert manifest["version"] == "9.9.9"
    pyproject = tomllib.loads((stage / "pyproject.toml").read_text())
    assert pyproject["project"]["dependencies"] == ["cr1000a-mcp==9.9.9"]
    assert pyproject["tool"]["uv"]["package"] is False
    assert (stage / "server" / "main.py").is_file()
    assert not (stage / ".env").exists()


def test_launcher_calls_the_package_entry_point() -> None:
    source = (ROOT / "mcpb" / "server" / "main.py").read_text()
    compile(source, "main.py", "exec")
    assert "from cr1000a_mcp import main" in source


CHANGELOG = """# Changelog

## [Unreleased]

## [0.3.0] - 2026-01-01

### Added

- Thing.

## [0.2.0] - 2025-12-01

- Older.

[Unreleased]: https://example.invalid/compare
"""


def test_changelog_section_extracts_only_that_version() -> None:
    assert changelog_section.section(CHANGELOG, "0.3.0") == "### Added\n\n- Thing.\n"
    assert changelog_section.section(CHANGELOG, "0.2.0") == "- Older.\n"


def test_real_changelog_has_a_section_for_the_current_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text()
    with (ROOT / "pyproject.toml").open("rb") as f:
        version = tomllib.load(f)["project"]["version"]
    assert changelog_section.section(text, version).strip()


# --- workflow policy: build tooling must never run next to a write token ------------------

WORKFLOWS = ROOT / ".github" / "workflows"
RISKY_COMMANDS = ("npx", "npm ", "uv run", "uv sync", "uv build", "pip ", "python")


def _load_workflows() -> dict[str, dict[str, Any]]:
    import yaml

    return {p.name: yaml.safe_load(p.read_text()) for p in WORKFLOWS.glob("*.yml")}


def test_write_token_jobs_run_no_checkout_and_no_build_tooling() -> None:
    offenders = []
    for name, wf in _load_workflows().items():
        for job_name, job in wf["jobs"].items():
            perms = job.get("permissions") or {}
            if perms.get("contents") != "write":
                continue
            for step in job["steps"]:
                if str(step.get("uses", "")).startswith("actions/checkout"):
                    offenders.append(f"{name}:{job_name} checks out code")
                run = str(step.get("run", ""))
                for bad in RISKY_COMMANDS:
                    if bad in run:
                        offenders.append(f"{name}:{job_name} runs {bad!r}")
    assert offenders == []


def test_mcpb_build_jobs_checkout_without_persisting_credentials() -> None:
    for name, wf in _load_workflows().items():
        job = wf["jobs"].get("mcpb")
        if not job:
            continue
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout"):
                assert step["with"]["persist-credentials"] is False, name


def test_release_bundle_job_is_read_only_and_feeds_the_write_job() -> None:
    release = _load_workflows()["release.yml"]["jobs"]
    assert release["mcpb"]["permissions"] == {"contents": "read"}
    assert release["github-release"]["needs"] == "mcpb"


def test_mcpb_cli_is_pinned_exactly_and_locked_with_hashes() -> None:
    cli_dir = ROOT / "scripts" / "mcpb-cli"
    pkg = json.loads((cli_dir / "package.json").read_text())
    pinned = pkg["dependencies"]["@anthropic-ai/mcpb"]
    assert pinned[0].isdigit(), f"must be an exact version, got {pinned}"
    lock = json.loads((cli_dir / "package-lock.json").read_text())["packages"]
    entry = lock["node_modules/@anthropic-ai/mcpb"]
    assert entry["version"] == pinned and entry["integrity"].startswith("sha512-")
    assert all("integrity" in v for k, v in lock.items() if k)  # every dependency is hash-pinned
    assert not any(v.get("hasInstallScript") for v in lock.values())
