#!/usr/bin/env python3
"""token-optimizer hook handler: an agent's hook system runs it and passes the event as JSON on stdin.

  read-guard    Before a file read. If the agent reads a whole text file of more than --min-tokens (default 2000)
                without a line range, block that read ONCE per file per session, with a short reason telling the
                agent to run `token_optimizer.py auto` on it (or read a range). A second attempt goes through, so
                full reads that are really needed (for example before an edit) still work.
  session-end   When a session ends. Import its transcript into the usage ledger, so `stats` and the dashboard
                stay current without anyone running `import`.

It never gets in the agent's way: on any error it allows the action and exits 0.
Off switch: TOKEN_GUARD=off in the environment, or a file ~/.skill-hub/token-guard.off.
Threshold: --min-tokens N, or TOKEN_GUARD_MIN_TOKENS.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

READ_TOOLS = {"read", "read_file", "readfile", "view", "view_file", "open_file"}
PATH_KEYS = ("file_path", "filePath", "path", "absolute_path", "target_file", "file")
RANGE_KEYS = ("offset", "limit", "start_line", "end_line", "startLine", "endLine", "line_range", "view_range",
              "lines", "pages")
NOT_TEXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".ipynb", ".svg", ".zip", ".gz",
            ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".exe", ".dll", ".so", ".class", ".jar"}
STATE_DIR = Path.home() / ".skill-hub" / "token-guard"
OFF_FILE = Path.home() / ".skill-hub" / "token-guard.off"
STATE_MAX_AGE = 2 * 86400


def read_event() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _tool_input(event: dict) -> dict:
    for key in ("tool_input", "toolInput", "toolArgs", "input", "arguments"):
        val = event.get(key)
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except ValueError:
                continue
        if isinstance(val, dict):
            return val
    return {}


def guard_decision(event: dict, min_tokens: int, state_dir: Path = STATE_DIR):
    """The reason to block this read, or None to allow it."""
    if os.environ.get("TOKEN_GUARD", "").lower() in ("off", "0", "false", "no") or OFF_FILE.exists():
        return None
    tool = str(event.get("tool_name") or event.get("toolName") or "").lower()
    if tool and tool not in READ_TOOLS:
        return None
    args = _tool_input(event)
    if any(args.get(k) not in (None, "", [], 0) for k in RANGE_KEYS):
        return None                                         # already a partial read
    raw = next((args[k] for k in PATH_KEYS if isinstance(args.get(k), str) and args[k]), None)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute() and event.get("cwd"):
        path = Path(event["cwd"]) / path
    if path.suffix.lower() in NOT_TEXT or not path.is_file():
        return None
    from token_optimizer import CODE_EXT, looks_binary   # imported late: the common path above stays fast
    size = path.stat().st_size
    est = int(math.ceil(size / (3.3 if path.suffix.lower() in CODE_EXT else 4.0)))
    if est <= min_tokens or looks_binary(path):
        return None
    if _seen_before(event, path, state_dir):
        return None
    script = (HERE / "token_optimizer.py").as_posix()
    return (f"token-optimizer: {path.name} is ~{est:,} tokens. Run `python {script} auto \"{path.as_posix()}\"` "
            f"and read its output, or read only a line range. If you need the whole file, read it again; "
            f"the second read is allowed.")


def _seen_before(event: dict, path: Path, state_dir: Path) -> bool:
    """True if this file was already blocked once in this session; otherwise remember it and return False."""
    session = re.sub(r"[^\w.-]", "_", str(event.get("session_id") or event.get("sessionId")
                                          or event.get("conversationId") or "no-session"))[:80]
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for old in state_dir.glob("*.json"):
            if now - old.stat().st_mtime > STATE_MAX_AGE:
                old.unlink()
        f = state_dir / f"{session}.json"
        seen = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
        key = str(path.resolve())
        if key in seen:
            return True
        f.write_text(json.dumps(seen + [key]), encoding="utf-8")
    except (OSError, ValueError):
        return True                                         # cannot keep state: never block twice by accident
    return False


def record_guard(path_name: str, est: int) -> None:
    from token_optimizer import append_event, ledger_path, now_iso
    append_event({"time": now_iso(), "kind": "guard", "tool": "read-guard", "skill": "token-optimizer",
                  "source": path_name, "before": est}, ledger_path())


def session_end(event: dict, agent: str) -> int:
    from token_optimizer import import_logs, ledger_path
    tp = event.get("transcript_path") or event.get("transcriptPath")
    if not tp or not Path(tp).expanduser().is_file():
        return 0
    r = import_logs([(Path(tp).expanduser(), agent)], ledger_path())
    return r["events"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["read-guard", "session-end"])
    ap.add_argument("--min-tokens", type=int, default=int(os.environ.get("TOKEN_GUARD_MIN_TOKENS") or 2000))
    ap.add_argument("--agent", default="unknown", help="session-end: label for the imported session")
    a = ap.parse_args(argv)
    event = read_event()
    try:
        if a.mode == "read-guard":
            reason = guard_decision(event, a.min_tokens)
            if reason:
                try:
                    m = re.search(r": (.+?) is ~([\d,]+) tokens", reason)
                    record_guard(m.group(1), int(m.group(2).replace(",", "")))
                except Exception:                           # the ledger is a nice-to-have here
                    pass
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                         "permissionDecision": "deny",
                                                         "permissionDecisionReason": reason}}))
        else:
            session_end(event, a.agent)
    except Exception as exc:                                # never block or break the agent
        print(f"token_hook: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
