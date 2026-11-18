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


IP_ENV = ("VZ_ROUTER_IP", "ROUTER_IP", "VZ_ROUTER_BASE_URL")


@pytest.fixture
def no_ip_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in IP_ENV:
        monkeypatch.delenv(name, raising=False)


def base_url() -> str:
    return load_settings().base_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.1.1", "https://192.168.1.1"),
        (" 192.168.1.254 ", "https://192.168.1.254"),
        ("192.168.1.1:8443", "https://192.168.1.1:8443"),
        ("router.lan", "https://router.lan"),
        ("https://192.168.1.1/", "https://192.168.1.1"),
        ("fe80::1", "https://[fe80::1]"),
        ("[fe80::1]:8443", "https://[fe80::1]:8443"),
    ],
)
def test_router_url_accepts(value: str, expected: str) -> None:
    from cr1000a_mcp.server import router_url

    assert router_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "http://192.168.1.1",
        "192.168.1.1/admin",
        "user@192.168.1.1",
        "192.168.1.1:99999",
        "192.168.1.1:abc",
        "bad host",
        "-bad.example",
        "[fe80::1",
        "[nonsense]",
        "a:b:c",
    ],
)
def test_router_url_rejects(value: str) -> None:
    from cr1000a_mcp.server import router_url

    with pytest.raises(ValueError):
        router_url(value)


def test_default_base_url_unchanged(no_ip_env: None) -> None:
    assert base_url() == "https://192.168.1.1"


def test_vz_router_ip_from_env(no_ip_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VZ_ROUTER_IP", "10.0.0.1")
    assert base_url() == "https://10.0.0.1"


def test_router_ip_alias_from_dotenv(no_ip_env: None, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ROUTER_IP=10.0.0.2\n")
    assert base_url() == "https://10.0.0.2"


def test_vz_router_ip_beats_alias(no_ip_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VZ_ROUTER_IP", "10.0.0.1")
    monkeypatch.setenv("ROUTER_IP", "10.0.0.9")
    assert base_url() == "https://10.0.0.1"


def test_explicit_base_url_wins(no_ip_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VZ_ROUTER_BASE_URL", "https://192.168.5.5")
    monkeypatch.setenv("VZ_ROUTER_IP", "10.0.0.1")
    assert base_url() == "https://192.168.5.5"


def test_invalid_ip_is_a_clear_error(no_ip_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VZ_ROUTER_IP", "http://10.0.0.1")
    with pytest.raises(ValueError, match="HTTPS"):
        load_settings()
