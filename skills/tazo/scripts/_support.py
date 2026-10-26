"""Small shared helpers; only Python's standard library is required."""

from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://api.tazolabs.com"


def validate_base_url(value: str) -> str:
    """Reject credentials and query parameters before displaying a target URL."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
    ):
        raise ValueError("Use an http(s) API origin without credentials, query, or fragment.")
    if parsed.path.rstrip("/").endswith("/v1"):
        raise ValueError("--base-url must not end in /v1; the SDK adds API paths.")
    # Accessing port also rejects malformed or out-of-range port numbers.
    _ = parsed.port
    return value.rstrip("/")


def redact(value: str) -> str:
    """Also redact an echoed key in remote errors or serialized extra fields."""
    key = os.environ.get("TAZO_API_KEY", "").strip()
    if key:
        # JSON reports may contain escaped forms of a configured credential.
        for secret in {key, json.dumps(key)[1:-1], json.dumps(key, ensure_ascii=False)[1:-1]}:
            value = value.replace(secret, "[REDACTED]")
    return value
