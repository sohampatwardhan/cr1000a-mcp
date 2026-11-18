# Contributing to cr1000a-mcp

Thanks for helping. This is a small project that talks to an undocumented router API, so the
main risks are firmware drift and leaking something private. The rules below exist for those
two reasons.

## Scope

In scope: the MCP server, its tools, the `check` and `write-test` commands, and the docs in
`docs/endpoints.md`.

Out of scope: a Home Assistant integration or any other consumer of the router API. That is a
separate project with its own release cycle (the research notes are in the closed issue
about it). Keep this repository focused on the MCP server.

## Workflow

1. **Open an issue first.** Describe the problem or feature and what "done" means.
2. **Branch per issue**, named for it (for example `feat/26-router-ip-env`, `fix/28-redact-secrets`).
3. **Open a pull request that links the issue** with a closing keyword on its own line
   (`Closes #26`). Use closing keywords only when the PR really finishes the issue; for partial
   work write `Refs #26`. Beware accidental keywords: a phrase such as "to close #6" or
   "closed: #6" in a PR description closes the issue when it merges.
4. Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for any user-visible change
   (Added, Changed, Fixed, Security).
5. CI must pass (lint, tests on Python 3.12 and 3.13, build). Keep PRs small enough to review.

## Development setup

You need [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sohampatwardhan/cr1000a-mcp && cd cr1000a-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

To run your working copy as the MCP server, use
`uv run --directory /path/to/cr1000a-mcp cr1000a-mcp` in place of `uvx cr1000a-mcp`.

Tests never touch a real router. Tool tests use in-memory fakes through FastMCP's `Client`;
`tests/fixtures/` holds **names only** recorded from a real router.

## Adding or changing a tool

- **Reads** are always registered and carry `readOnlyHint`. **Writes** are registered only with
  `CR1000A_MCP_ALLOW_WRITE=1`, validate their input before any router call, and are never
  retried (a retry could repeat a half-applied change).
- Keep output small. Routers return large blobs; trim to what a model needs and cap lists.
- Anything that can change or wipe the device (firmware upload, restore, clear-log,
  diagnostics, engineering pages) must not be exposed as a tool.
- New data pages go through the allowlist in `src/cr1000a_mcp/pages.py` and through
  `redact()`. Do not add `wifi_*` or `ui_admin` pages without confirming they hold no secrets.
- Add tests, update the tool table in the README, and record verified shapes in
  `docs/endpoints.md`.

## Privacy and secrets

- Never commit `.env`, a password, a WAN address, MAC addresses, device names or Wi-Fi
  details. Check issue and PR text too: GitHub keeps it public.
- Reports produced by `cr1000a-mcp check` contain shapes and field names only, so they are
  safe to paste into an issue. Do not paste raw router responses.
- Values of secret-named fields (`password`, `psk`, `secret`, `token`, a trailing `_pw`) are
  redacted by `get_router_page`. If you find a field that leaks, open an issue describing the
  field **name**, not its value.

## The MCPB bundle

`mcpb/` holds the manifest and launcher for the Claude Desktop bundle; `scripts/build_mcpb.py`
stages it, pins `cr1000a-mcp==<version>` from PyPI in a generated `pyproject.toml`, and packs
it with the official `mcpb` CLI. When you add, rename or remove a tool, update the `tools`
list in `mcpb/manifest.json`: `tests/test_mcpb.py` compares it with the real server.
Never give the password field a default.

## Testing against a real router

Only the maintainers' router is covered by the recorded fixtures (firmware **3.6.0.5_BD**). If
you have a CR1000A:

```bash
uvx cr1000a-mcp check        # read-only; prints shapes and the firmware version
uvx cr1000a-mcp write-test   # adds then removes a throwaway DNS record; asks first
```

Log out of the router's web UI first (it may allow one session). After a firmware update,
re-run `check`, compare with `tests/fixtures/live_cr1000a_3.6.0.5_BD.json`, and open an issue or
PR with the differences. When you record a new firmware, add a fixture file named for it and
extend `tests/test_live_contract.py`.

## Releasing (maintainers)

Publishing uses PyPI trusted publishing (no API token); the publisher is registered for this
repository's `release.yml` workflow and the `pypi` environment.

1. Bump `version` in `pyproject.toml` **and** `mcpb/manifest.json` (a test fails if they
   differ) and move the **Unreleased** entries in `CHANGELOG.md` under the new version heading
   with its date; merge the PR.
2. Tag and push:

   ```bash
   git tag -a v0.1.1 -m "v0.1.1" && git push origin v0.1.1
   ```

The workflow checks that the tag matches the package version, runs lint and tests, builds, and
publishes to PyPI. Then it builds the MCPB bundle and attaches it to a GitHub Release, using that
version's changelog section as the notes. Before tagging, install the bundle from the CI
`mcpb` artifact (or `uv run python scripts/build_mcpb.py`) into Claude Desktop once: CI can
validate and launch the bundle's command but cannot click through Claude Desktop. A published version can never be re-uploaded, so fixes ship as a new version.
Third-party actions in the release workflow are pinned to commit SHAs; Dependabot proposes
updates, which should be reviewed because that job holds the publish permission.

## License

By contributing you agree that your contributions are licensed under the MIT license.
