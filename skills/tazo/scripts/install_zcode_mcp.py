"""Add a hosted Tazo-MCP connection; leave sign-in to ZCode's native OAuth UI."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

PRODUCTION_URL = "https://mcp.tazolabs.com/mcp"


class SetupError(Exception):
    pass


def read_config(path: Path) -> tuple[bytes | None, dict]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, {}
    if not raw.strip():
        return raw, {}
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return raw, value
    except (ValueError, UnicodeError):
        raise SetupError(f"Settings are not a JSON object; left unchanged: {path}") from None


def fallback_for(path: Path) -> Path | None:
    if path.parent.name == "cli" and path.parent.parent.name == ".zcode":
        return path.parents[2] / ".agents/mcp.json"
    if path.parent.name == ".zcode":
        return path.parents[1] / ".agents/mcp.json"
    return None


def install(config: Path, *, url=PRODUCTION_URL, name="Tazo-MCP", fallback=None, dry_run=False):
    try:
        endpoint = urlsplit(url)
        valid = (
            endpoint.scheme == "https"
            and endpoint.hostname
            and not endpoint.username
            and not endpoint.password
            and not endpoint.query
            and not endpoint.fragment
            and not any(ord(character) < 33 for character in url)
        )
    except ValueError:
        valid = False
    if not valid:
        raise SetupError(
            "Use an HTTPS MCP URL without credentials, query parameters, or fragments."
        )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise SetupError("Use a server name of 1–64 letters, digits, underscores, or hyphens.")

    # Resolve a user's config symlink and update its target without replacing the link.
    config = config.expanduser()
    fallback = fallback or fallback_for(config)
    config = config.resolve()
    original, value = read_config(config)
    updated = copy.deepcopy(value)
    mcp = updated.setdefault("mcp", {})
    if not isinstance(mcp, dict) or not isinstance(mcp.get("servers", {}), dict):
        raise SetupError("Existing MCP settings have an unsupported shape; left unchanged.")
    servers = mcp.setdefault("servers", {})
    inherited = 0
    if not servers and fallback is not None:
        _, compatibility = read_config(Path(fallback).expanduser())
        active = compatibility.get("mcpServers", {})
        if not isinstance(active, dict):
            raise SetupError("The active .agents MCP fallback is invalid; left unchanged.")
        servers.update(copy.deepcopy(active))
        inherited = len(active)

    if name in servers:
        existing = servers[name]
        if (
            isinstance(existing, dict)
            and existing.get("url") == url
            and existing.get("type", "http") == "http"
        ):
            return {"status": "already_configured", "client": "zcode", "server": name}
        raise SetupError("The server name is already used for another connection; choose --name.")
    servers[name] = {"type": "http", "url": url}
    result = {
        "status": "preview" if dry_run else "configured",
        "client": "zcode",
        "server": name,
        "url": url,
        "config_path": str(config),
        "preserved_fallback_servers": inherited,
        "next_action": "Refresh ZCode MCP settings and use Open authorization to sign in to Tazo.",
    }
    if dry_run:
        return result

    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if read_config(config)[0] != original:
        raise SetupError("Settings changed during installation; left unchanged. Retry once.")
    if original is not None:
        backup = config.with_name(config.name + ".tazo-mcp-" + uuid.uuid4().hex[:12] + ".bak")
        with backup.open("xb") as output:
            os.chmod(backup, 0o600)
            output.write(original)
        result["backup_path"] = str(backup)
    descriptor, temporary = tempfile.mkstemp(prefix=".tazo-mcp-", dir=config.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(updated, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if read_config(config)[0] != original:
            raise SetupError("Settings changed during installation; left unchanged. Retry once.")
        os.replace(temporary, config)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=PRODUCTION_URL)
    parser.add_argument("--name", default="Tazo-MCP")
    parser.add_argument("--config", type=Path, default=Path.home() / ".zcode/cli/config.json")
    parser.add_argument("--fallback-config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = install(
            args.config,
            url=args.url,
            name=args.name,
            fallback=args.fallback_config,
            dry_run=args.dry_run,
        )
    except (SetupError, OSError) as error:
        print(json.dumps({"status": "error", "message": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
