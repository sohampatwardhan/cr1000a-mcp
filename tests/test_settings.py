from __future__ import annotations

from pathlib import Path

import pytest

from cr1000a_mcp.server import load_settings

SECRET_ENV = ("VZ_ROUTER_PASSWORD", "NETWORK_SETTINGS_PASSWORD")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in SECRET_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env from the repo


def password() -> str:
    return load_settings().password.get_secret_value()


def test_no_password_is_empty() -> None:
    assert password() == ""


def test_alias_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETWORK_SETTINGS_PASSWORD", "from-env")
    assert password() == "from-env"


def test_alias_from_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("NETWORK_SETTINGS_PASSWORD=from-dotenv\n")
    assert password() == "from-dotenv"


def test_vz_router_password_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VZ_ROUTER_PASSWORD", "primary")
    monkeypatch.setenv("NETWORK_SETTINGS_PASSWORD", "alias")
    assert password() == "primary"


def test_vz_router_password_in_dotenv_wins(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("VZ_ROUTER_PASSWORD=primary\nNETWORK_SETTINGS_PASSWORD=alias\n")
    assert password() == "primary"


def test_password_never_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETWORK_SETTINGS_PASSWORD", "s3cret-value")
    assert "s3cret-value" not in repr(load_settings())
