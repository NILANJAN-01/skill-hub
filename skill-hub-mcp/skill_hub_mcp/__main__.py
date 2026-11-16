"""python -m skill_hub_mcp [--root DIR] [--remote] [--ref REF] [--allow-install] [--check]"""
from __future__ import annotations

import argparse
import sys

from . import hub
from .server import NAME, VERSION, build_server


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skill_hub_mcp", description="MCP server (stdio) for the skill-hub catalog.")
    ap.add_argument("--root", help="path to a skill-hub clone (default: SKILLHUB_ROOT, or the clone this file is in)")
    ap.add_argument("--remote", action="store_true", help="read from GitHub instead of a local clone")
    ap.add_argument("--ref", default="main", help="branch or release tag for --remote (default: main)")
    ap.add_argument("--allow-install", action="store_true",
                    help="add the apply_change tool, which installs, updates and removes skill folders. "
                         "Without it the server is read-only")
    ap.add_argument("--check", action="store_true", help="load the catalog, print a summary and exit")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", **({"newline": "\n"} if stream is sys.stdout else {}))
    try:
        source = hub.make_source(args.root, args.remote, args.ref)
        server = build_server(source, allow_write=args.allow_install)
        count = len(hub.Hub(source).skills)
    except hub.HubError as exc:
        print(f"{NAME}: {exc}", file=sys.stderr)
        return 2
    mode = "installs enabled" if args.allow_install else "read-only"
    print(f"{NAME} {VERSION}: {count} skills from {source.describe()} ({mode}, {len(server.tools)} tools)",
          file=sys.stderr)
    if args.check:
        return 0
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
