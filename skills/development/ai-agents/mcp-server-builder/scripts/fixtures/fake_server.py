"""Minimal stdio MCP server used by the tests. Flags: --noisy, --crash, --paged."""
import json
import sys

NOISY = "--noisy" in sys.argv
CRASH = "--crash" in sys.argv
PAGED = "--paged" in sys.argv

GOOD = {"name": "echo", "description": "Echo the given text back unchanged. Use to test the connection.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to echo"}},
                        "required": ["text"]}}
BAD = {"name": "bad tool", "inputSchema": {"type": "string"}}


def reply(msg_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


if CRASH:
    sys.stderr.write("boom: missing API_KEY\n")
    sys.exit(3)

for line in sys.stdin:
    msg = json.loads(line)
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:
        continue
    if method == "initialize":
        if NOISY:
            print("server starting...")
        reply(msg_id, {"protocolVersion": msg["params"]["protocolVersion"],
                       "capabilities": {"tools": {}},
                       "serverInfo": {"name": "fake", "version": "0.1"}})
    elif method == "tools/list":
        cursor = (msg.get("params") or {}).get("cursor")
        if PAGED and not cursor:
            reply(msg_id, {"tools": [GOOD], "nextCursor": "p2"})
        elif PAGED:
            reply(msg_id, {"tools": [BAD]})
        else:
            reply(msg_id, {"tools": [GOOD, BAD]})
    elif method == "tools/call":
        params = msg["params"]
        if params["name"] == "echo":
            reply(msg_id, {"content": [{"type": "text", "text": params["arguments"].get("text", "")}]})
        else:
            reply(msg_id, error={"code": -32602, "message": "unknown tool"})
    else:
        reply(msg_id, error={"code": -32601, "message": "method not found"})
