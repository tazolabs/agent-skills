"""Check Python, the installed Tazo SDK, key presence, health, and models.

Does not upload audio or submit inference. --offline avoids all network calls.
Exit codes: 0 ready, 1 prerequisite/API failure, 2 invalid command-line input.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

from _support import DEFAULT_BASE_URL, redact, validate_base_url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Check only local prerequisites")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=15, help="HTTP budget in seconds")
    args = parser.parse_args()
    try:
        args.base_url = validate_base_url(args.base_url)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("--timeout must be positive and finite.")
    except ValueError as error:
        parser.error(redact(str(error)))

    print(f"Python {sys.version.split()[0]}: {sys.executable}")
    if sys.version_info < (3, 11):  # noqa: UP036 - this diagnostic also runs on older Pythons
        print("FAIL: Python 3.11 or newer is required.", file=sys.stderr)
        return 1
    try:
        import tazo
        from tazo import Tazo
    except ImportError:
        print("FAIL: Install tazo-sdk in this Python environment.", file=sys.stderr)
        return 1
    print(f"SDK {tazo.__version__}: {tazo.__file__}")
    key_present = bool(os.environ.get("TAZO_API_KEY", "").strip())
    print(f"TAZO_API_KEY: {'set (value hidden)' if key_present else 'missing'}")
    if args.offline:
        return 0 if key_present else 1

    try:
        with Tazo(
            # An explicitly empty environment value is rejected by the SDK.
            # Health sends no Authorization header; this placeholder isn't sent.
            api_key=os.environ.get("TAZO_API_KEY", "").strip() or "unused-for-health",
            base_url=args.base_url,
            timeout=args.timeout,
            operation_timeout=args.timeout,
            max_retries=0,
        ) as client:
            print(f"Target: {args.base_url}")
            health = client.health.check()
            print(f"Health: {health.status}")
            if health.status != "ok":
                return 1
            if not key_present:
                print("Set TAZO_API_KEY from https://app.tazolabs.com to discover models.")
                return 1
            models = client.models.list().models
            for model in models:
                print(redact(f"Model {model.id}: ready={model.ready}"))
                print(redact(model.capabilities.model_dump_json(indent=2)))
            if not any(model.ready for model in models):
                print("FAIL: No model is currently ready.", file=sys.stderr)
                return 1
    except Exception as error:
        print(redact(f"FAIL: {type(error).__name__}: {error}"), file=sys.stderr)
        return 1
    print("Setup passed. No inference requests were submitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
