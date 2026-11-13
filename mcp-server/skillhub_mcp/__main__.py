"""python -m skillhub_mcp [--root DIR] [--remote] [--ref BRANCH] [--check]"""
from __future__ import annotations

import argparse
import sys

from . import catalog
from .server import VERSION, build_server


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skillhub_mcp", description="MCP server (stdio) for the skill-hub catalog.")
    ap.add_argument("--root", help="path to a skill-hub clone (default: SKILLHUB_ROOT, or the clone this file is in)")
    ap.add_argument("--remote", action="store_true", help="read from GitHub instead of a local clone")
    ap.add_argument("--ref", default="main", help="GitHub branch for --remote (default main)")
    ap.add_argument("--check", action="store_true", help="load the catalog, print a summary and exit")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", **({"newline": "\n"} if stream is sys.stdout else {}))
    try:
        source = catalog.make_source(args.root, args.remote, args.ref)
        server = build_server(source)
        count = len(catalog.Catalog(source).skills)
    except catalog.CatalogError as exc:
        print(f"skillhub_mcp: {exc}", file=sys.stderr)
        return 2
    print(f"skillhub_mcp {VERSION}: {count} skills from {source.describe()}", file=sys.stderr)
    if args.check:
        return 0
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
