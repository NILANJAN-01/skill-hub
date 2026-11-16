"""MCP over stdio: JSON-RPC 2.0, one JSON message per line. Standard library only.

Methods: initialize, ping, tools/list, tools/call, resources/list, resources/templates/list,
resources/read, prompts/list, prompts/get. stdout carries protocol messages only; logs go to stderr.
"""
from __future__ import annotations

import json
import sys

PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603
RESOURCE_NOT_FOUND = -32002


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class ToolError(Exception):
    """A problem the model can read and fix. Returned as a tool result with isError=true."""


class Tool:
    """One MCP tool. `params` maps an argument name to a JSON-schema fragment; `writes` marks tools
    that change files, so clients ask the user before running them."""

    def __init__(self, name, title, description, handler, params=None, required=(), writes=False):
        self.name, self.title, self.description, self.handler = name, title, description, handler
        self.params, self.required, self.writes = params or {}, list(required), writes

    def spec(self):
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": {"type": "object", "properties": self.params, "required": self.required,
                                "additionalProperties": False},
                "annotations": {"readOnlyHint": not self.writes, "destructiveHint": self.writes,
                                "idempotentHint": not self.writes, "openWorldHint": False}}

    def clean(self, args):
        """Check and normalise the arguments the client sent."""
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        out = {}
        for key, val in args.items():
            schema = self.params.get(key)
            if schema is None:
                raise ToolError(f"unknown argument '{key}'. Allowed: {', '.join(self.params) or 'none'}")
            if val is None:
                continue
            kind = schema.get("type")
            if kind == "integer":
                if isinstance(val, bool):
                    raise ToolError(f"'{key}' must be an integer")
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    raise ToolError(f"'{key}' must be an integer") from None
                val = min(max(val, schema.get("minimum", val)), schema.get("maximum", val))
            elif kind == "string":
                if not isinstance(val, str):
                    raise ToolError(f"'{key}' must be a string")
                if "enum" in schema and val not in schema["enum"]:
                    raise ToolError(f"'{key}' must be one of: {', '.join(schema['enum'])}")
            elif kind == "boolean" and not isinstance(val, bool):
                raise ToolError(f"'{key}' must be true or false")
            out[key] = val
        for key in self.required:
            if out.get(key) in (None, ""):
                raise ToolError(f"missing required argument '{key}'")
        return out


class Server:
    def __init__(self, name, version, instructions, tools, resources=None, prompts=None, soft_errors=()):
        """resources: object with list(), templates(), read(uri) (read raises KeyError when unknown).
        prompts: {name: (spec, builder)}. soft_errors: exception types shown to the model as tool errors."""
        self.name, self.version, self.instructions = name, version, instructions
        self.tools = {t.name: t for t in tools}
        self.resources, self.prompts = resources, prompts or {}
        self.soft_errors = (ToolError,) + tuple(soft_errors)

    # ---- one message in, one reply out (None for notifications)
    def handle(self, msg):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method = msg.get("method")
        if not isinstance(method, str):          # a reply to a request we never sent
            return None
        note, mid = "id" not in msg, msg.get("id")
        params = msg.get("params")
        try:
            if params is not None and not isinstance(params, dict):
                raise RpcError(INVALID_PARAMS, "params must be an object")
            result = self.dispatch(method, params or {})
        except RpcError as exc:
            return None if note else _error(mid, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - one bad request must not stop the server
            print(f"internal error in {method}: {exc!r}", file=sys.stderr)
            return None if note else _error(mid, INTERNAL, f"internal error: {exc}")
        return None if note else {"jsonrpc": "2.0", "id": mid, "result": result}

    def dispatch(self, method, params):
        if method == "initialize":
            wanted = params.get("protocolVersion")
            caps = {"tools": {"listChanged": False}}
            if self.prompts:
                caps["prompts"] = {"listChanged": False}
            if self.resources:
                caps["resources"] = {"subscribe": False, "listChanged": False}
            return {"protocolVersion": wanted if wanted in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": caps,
                    "serverInfo": {"name": self.name, "title": "skill-hub", "version": self.version},
                    "instructions": self.instructions}
        if method == "ping" or method.startswith("notifications/"):
            return {}
        if method == "tools/list":
            return {"tools": [t.spec() for t in self.tools.values()]}
        if method == "tools/call":
            return self.call_tool(params.get("name"), params.get("arguments") or {})
        if self.resources and method == "resources/list":
            return {"resources": self.resources.list()}
        if self.resources and method == "resources/templates/list":
            return {"resourceTemplates": self.resources.templates()}
        if self.resources and method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str) or not uri:
                raise RpcError(INVALID_PARAMS, "uri is required")
            try:
                return {"contents": [self.resources.read(uri)]}
            except KeyError:
                raise RpcError(RESOURCE_NOT_FOUND, f"resource not found: {uri}") from None
        if method == "prompts/list":
            return {"prompts": [spec for spec, _ in self.prompts.values()]}
        if method == "prompts/get":
            entry = self.prompts.get(params.get("name"))
            if not entry:
                raise RpcError(INVALID_PARAMS, f"unknown prompt '{params.get('name')}'")
            return entry[1](params.get("arguments") or {})
        raise RpcError(METHOD_NOT_FOUND, f"method not found: {method}")

    def call_tool(self, name, args):
        tool = self.tools.get(name)
        if tool is None:
            raise RpcError(INVALID_PARAMS, f"unknown tool '{name}'")
        try:
            out = tool.handler(**tool.clean(args))
        except self.soft_errors as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        if isinstance(out, str):
            return {"content": [{"type": "text", "text": out}], "isError": False}
        return {"content": [{"type": "text", "text": json.dumps(out, indent=2, ensure_ascii=False)}],
                "structuredContent": out, "isError": False}

    # ---- transport
    def serve(self, stdin=None, stdout=None):
        stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                _write(stdout, _error(None, PARSE_ERROR, "invalid JSON"))
                continue
            if isinstance(msg, list):
                replies = [r for r in (self.handle(m) for m in msg) if r is not None]
                if replies:
                    _write(stdout, replies)
            else:
                reply = self.handle(msg)
                if reply is not None:
                    _write(stdout, reply)


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _write(stdout, obj):
    stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    stdout.flush()
