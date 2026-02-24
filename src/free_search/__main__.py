"""CLI entrypoint for subprocess usage: python -m free_search."""

from __future__ import annotations

import argparse
import json
import sys

from . import configure_logging, get_quota_status, reset_quota, search
from .router import SearchRouterError


def _normalize_compat_tokens(argv: list[str]) -> list[str]:
    if len(argv) >= 3 and argv[0].lower() == "brave" and argv[1].lower() == "search":
        return argv[2:]
    if len(argv) >= 2 and argv[0].lower() == "search":
        return argv[1:]
    return argv


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    normalized_args = _normalize_compat_tokens(raw_args)

    if normalized_args and normalized_args[0].lower() == "status":
        parser = argparse.ArgumentParser(description="Show or reset provider quota usage")
        parser.add_argument("--config", default=None, help="Path to providers.yaml")
        parser.add_argument("--log-level", default="INFO")
        parser.add_argument("--compact", action="store_true", help="Print compact JSON")
        parser.add_argument("--reset", action="store_true", help="Reset quota counters before showing status")
        args = parser.parse_args(normalized_args[1:])

        configure_logging(args.log_level)
        try:
            payload = (
                reset_quota(config_path=args.config)
                if args.reset
                else get_quota_status(config_path=args.config)
            )
        except Exception as exc:  # pragma: no cover - defensive for CLI consumers
            print(json.dumps({"error": f"unexpected_error: {exc}"}, ensure_ascii=False), file=sys.stderr)
            return 1

        indent = None if args.compact else 2
        print(json.dumps(payload, ensure_ascii=False, indent=indent))
        return 0

    parser = argparse.ArgumentParser(description="Run failover web search")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--config", default=None, help="Path to providers.yaml")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    args = parser.parse_args(normalized_args)
    query = " ".join(args.query).strip()

    configure_logging(args.log_level)
    try:
        payload = search(query, max_results=args.max_results, config_path=args.config)
    except SearchRouterError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive for CLI consumers
        print(json.dumps({"error": f"unexpected_error: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    print(json.dumps(payload, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
