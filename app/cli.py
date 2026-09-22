"""Headless CLI for Squad AI.

Exercises the same AnswerEngine as the GUI (no PySide6 required), useful for
scripting, CI and demonstrating the end-to-end pipeline.

Examples:
    python -m app.cli profile set age 39
    python -m app.cli profile list
    python -m app.cli key set sk-...            # stored via keyring
    python -m app.cli ask "What is your age?"
    python -m app.cli ask "Which age range?" -o "18-24" -o "25-34" -o "35-44"
    python -m app.cli ask "Describe your weekend" --no-api
    python -m app.cli usage
"""
from __future__ import annotations

import argparse
import sys

from .services import Services
from .utils.config import CONFIG


def _cmd_profile(svc: Services, args) -> int:
    if args.action == "set":
        svc.profile.upsert(args.key, args.value)
        print(f"set {args.key} = {args.value}")
    elif args.action == "list":
        for f in svc.profile.all():
            print(f"{f.key} = {f.value} ({f.value_type})")
    elif args.action == "delete":
        svc.profile.delete(args.key)
        print(f"deleted {args.key}")
    return 0


def _cmd_key(svc: Services, args) -> int:
    if args.action == "set":
        svc.credentials.set_key(CONFIG.provider.name, args.value)
        print("API key stored securely.")
    elif args.action == "status":
        key = svc.credentials.get_key(CONFIG.provider.name)
        print(svc.credentials.masked(key))
    elif args.action == "delete":
        svc.credentials.delete_key(CONFIG.provider.name)
        print("API key deleted.")
    elif args.action == "test":
        provider = svc.build_provider()
        if provider is None:
            print("No API key configured.")
            return 1
        ok, msg = provider.test_connection()
        print(msg)
        return 0 if ok else 1
    return 0


def _cmd_ask(svc: Services, args) -> int:
    result = svc.engine.answer(args.question, explicit_options=args.option or None,
                               allow_api=not args.no_api)
    print(f"\nAnswer : {result.answer or '(unresolved)'}")
    if result.selected_option is not None:
        print(f"Option : [{result.selected_option_index}] "
              f"{result.selected_option}")
    print(f"Source : {result.source.value}  ({result.source.ui_label()})")
    print(f"Type   : {result.qtype.value}")
    print(f"Reason : {result.reasoning_code}")
    print(f"Conf   : {result.confidence:.2f}")
    print(f"API    : {'yes' if result.used_api else 'no'}  "
          f"({result.processing_time_ms} ms)")
    if result.api_usage:
        u = result.api_usage
        print(f"Tokens : in={u.input_tokens} out={u.output_tokens} "
              f"cached={u.cached_tokens} cost=${u.estimated_cost_usd:.5f}")
    if result.error:
        print(f"Note   : {result.error}")
    return 0


def _cmd_usage(svc: Services, _args) -> int:
    dash = svc.usage.dashboard()
    for label in ("today", "last_7_days", "total"):
        d = dash[label]
        print(f"{label:12} calls={d['calls']} in={d['input_tokens']} "
              f"out={d['output_tokens']} cost=${d['cost']:.5f} "
              f"failures={d['failures']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="squad-ai")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("profile")
    pr.add_argument("action", choices=["set", "list", "delete"])
    pr.add_argument("key", nargs="?")
    pr.add_argument("value", nargs="?")

    ky = sub.add_parser("key")
    ky.add_argument("action", choices=["set", "status", "delete", "test"])
    ky.add_argument("value", nargs="?")

    ak = sub.add_parser("ask")
    ak.add_argument("question")
    ak.add_argument("-o", "--option", action="append", help="answer option")
    ak.add_argument("--no-api", action="store_true",
                    help="never call DeepSeek")

    sub.add_parser("usage")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    svc = Services()
    try:
        return {
            "profile": _cmd_profile, "key": _cmd_key,
            "ask": _cmd_ask, "usage": _cmd_usage,
        }[args.cmd](svc, args)
    finally:
        svc.close()


if __name__ == "__main__":
    sys.exit(main())
