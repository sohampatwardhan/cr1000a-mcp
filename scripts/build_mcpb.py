"""Build the MCPB bundle (a .mcpb file) for Claude Desktop.

The bundle holds ``manifest.json``, a tiny launcher and a generated ``pyproject.toml``
that pins ``cr1000a-mcp==<version>`` from PyPI; the host installs it with uv. Packing and
validation use the official ``mcpb`` CLI, installed from a committed lockfile with
``npm ci``. Standard library only.

    uv run python scripts/build_mcpb.py            # writes dist/cr1000a-mcp-<version>.mcpb
    uv run python scripts/build_mcpb.py --stage-only DIR   # just write the staged files
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCPB_DIR = ROOT / "mcpb"
CLI_DIR = ROOT / "scripts" / "mcpb-cli"  # package.json + package-lock.json pin the mcpb CLI


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def bundle_pyproject(version: str) -> str:
    return (
        "[project]\n"
        'name = "cr1000a-mcp-bundle"\n'
        f'version = "{version}"\n'
        'requires-python = ">=3.12"\n'
        f'dependencies = ["cr1000a-mcp=={version}"]\n'
        "\n"
        "[tool.uv]\n"
        "package = false\n"
    )


def stage_bundle(dest: Path, version: str) -> Path:
    """Write the bundle's files into ``dest`` (created if needed) and return it."""
    dest.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((MCPB_DIR / "manifest.json").read_text())
    manifest["version"] = version
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copytree(MCPB_DIR / "server", dest / "server", dirs_exist_ok=True)
    (dest / "pyproject.toml").write_text(bundle_pyproject(version))
    return dest


def ensure_cli() -> Path:
    """Install the pinned mcpb CLI from the lockfile (hashes verified, no install scripts)."""
    subprocess.run(
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=CLI_DIR, check=True
    )
    exe = "mcpb.cmd" if sys.platform == "win32" else "mcpb"
    return CLI_DIR / "node_modules" / ".bin" / exe


def run_mcpb(cli: Path, *args: str) -> None:
    subprocess.run([str(cli), *args], check=True)


def build(version: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cli = ensure_cli()
    with tempfile.TemporaryDirectory(prefix="cr1000a-mcpb-") as tmp:
        stage = stage_bundle(Path(tmp) / "bundle", version)
        run_mcpb(cli, "validate", str(stage / "manifest.json"))
        run_mcpb(cli, "pack", str(stage), str(out))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--version", default=None, help="default: version in pyproject.toml")
    parser.add_argument("--out", type=Path, default=None, help="output .mcpb path")
    parser.add_argument("--stage-only", type=Path, default=None, metavar="DIR")
    args = parser.parse_args(argv)
    version = args.version or project_version()
    if args.stage_only:
        print(stage_bundle(args.stage_only, version))
        return 0
    out = args.out or ROOT / "dist" / f"cr1000a-mcp-{version}.mcpb"
    print(build(version, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
