"""Exercise installation without changing a real client's settings or credentials."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/tazo/scripts/install_zcode_mcp.py"
spec = importlib.util.spec_from_file_location("install_zcode_mcp", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_first_install_creates_a_private_production_entry(tmp_path):
    config = tmp_path / ".zcode/cli/config.json"
    result = installer.install(config)
    assert result["status"] == "configured"
    assert json.loads(config.read_text()) == {
        "mcp": {
            "servers": {
                "Tazo-MCP": {
                    "type": "http",
                    "url": installer.PRODUCTION_URL,
                }
            }
        }
    }
    if os.name != "nt":
        assert config.stat().st_mode & 0o777 == 0o600


def test_merge_preserves_settings_and_makes_an_exact_private_backup(tmp_path):
    config = tmp_path / "config.json"
    value = {
        "theme": "dark",
        "mcp": {
            "enabled": True,
            "servers": {
                "another": {
                    "type": "http",
                    "url": "https://other.example/mcp",
                    "headers": {
                        "Authorization": "private-existing-key",
                    },
                },
            },
        },
        "hooks": {"enabled": True},
    }
    write(config, value)
    original = config.read_bytes()
    result = installer.install(config)
    updated = json.loads(config.read_text())
    updated["mcp"]["servers"].pop("Tazo-MCP")
    assert updated == value
    backup = Path(result["backup_path"])
    assert backup.read_bytes() == original
    if os.name != "nt":
        assert backup.stat().st_mode & 0o777 == 0o600
    assert "private-existing-key" not in json.dumps(result)


def test_first_native_entry_preserves_active_compatibility_servers(tmp_path):
    config = tmp_path / ".zcode/cli/config.json"
    fallback = tmp_path / ".agents/mcp.json"
    inherited = {"files": {"command": "file-tool", "args": ["--read-only"]}}
    write(fallback, {"mcpServers": inherited})
    fallback_bytes = fallback.read_bytes()
    result = installer.install(config)
    assert result["preserved_fallback_servers"] == 1
    assert json.loads(config.read_text())["mcp"]["servers"]["files"] == inherited["files"]
    assert fallback.read_bytes() == fallback_bytes


def test_already_shadowed_fallback_is_not_enabled(tmp_path):
    config = tmp_path / ".zcode/cli/config.json"
    write(config, {"mcp": {"servers": {"native": {"command": "native-tool"}}}})
    write(tmp_path / ".agents/mcp.json", {"mcpServers": {"inactive": {"command": "unused"}}})
    installer.install(config)
    assert "inactive" not in json.loads(config.read_text())["mcp"]["servers"]


def test_repeat_install_does_not_rewrite_settings_or_make_a_backup(tmp_path):
    config = tmp_path / "config.json"
    installer.install(config)
    before = config.stat().st_mtime_ns, config.read_bytes()
    assert installer.install(config)["status"] == "already_configured"
    assert (config.stat().st_mtime_ns, config.read_bytes()) == before
    assert not list(tmp_path.glob("*.bak"))


def test_empty_initial_settings_are_backed_up_and_initialized(tmp_path):
    config = tmp_path / "config.json"
    config.write_bytes(b"\n")
    result = installer.install(config)
    assert Path(result["backup_path"]).read_bytes() == b"\n"
    assert "Tazo-MCP" in json.loads(config.read_text())["mcp"]["servers"]


def test_name_collision_preserves_existing_connection(tmp_path):
    config = tmp_path / "config.json"
    write(
        config,
        {"mcp": {"servers": {"Tazo-MCP": {"type": "http", "url": "https://other.example/mcp"}}}},
    )
    before = config.read_bytes()
    with pytest.raises(installer.SetupError, match="name is already used"):
        installer.install(config)
    assert config.read_bytes() == before
    assert not list(tmp_path.glob("*.bak"))


@pytest.mark.parametrize("body", ["not json", "[]", '{"mcp": []}', '{"mcp":{"servers":[]}}'])
def test_invalid_settings_are_never_replaced(tmp_path, body):
    config = tmp_path / "config.json"
    config.write_text(body)
    with pytest.raises(installer.SetupError):
        installer.install(config)
    assert config.read_text() == body


def test_invalid_active_fallback_stops_before_writing(tmp_path):
    config = tmp_path / ".zcode/cli/config.json"
    write(tmp_path / ".agents/mcp.json", {"mcpServers": []})
    with pytest.raises(installer.SetupError):
        installer.install(config)
    assert not config.exists()


def test_preview_does_not_create_directories_or_files(tmp_path):
    config = tmp_path / "new/config.json"
    assert installer.install(config, dry_run=True)["status"] == "preview"
    assert not config.parent.exists()


@pytest.mark.skipif(os.name == "nt", reason="Creating a symlink needs Windows privileges")
def test_config_symlink_and_active_fallback_are_preserved(tmp_path):
    config = tmp_path / ".zcode/cli/config.json"
    target = tmp_path / "dotfiles/zcode.json"
    write(target, {"theme": "dark"})
    config.parent.mkdir(parents=True)
    config.symlink_to(target)
    write(tmp_path / ".agents/mcp.json", {"mcpServers": {"other": {"command": "other"}}})
    installer.install(config)
    assert config.is_symlink()
    updated = json.loads(target.read_text())
    assert updated["theme"] == "dark"
    assert "other" in updated["mcp"]["servers"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "https://key@example.com/mcp",
        "https://example.com/mcp?token=secret",
        "https://example.com/mcp#secret",
    ],
)
def test_unsafe_endpoint_does_not_enter_settings(tmp_path, url):
    config = tmp_path / "config.json"
    with pytest.raises(installer.SetupError):
        installer.install(config, url=url)
    assert not config.exists()


def test_cli_runs_from_any_directory_and_keeps_custom_endpoint(tmp_path):
    config = tmp_path / "settings.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--url",
            "https://custom.example/mcp",
            "--name",
            "custom-tazo",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["status"] == "configured"
    assert (
        json.loads(config.read_text())["mcp"]["servers"]["custom-tazo"]["url"]
        == "https://custom.example/mcp"
    )
