"""A small MCP server over stdio (JSON-RPC 2.0, one JSON message per line). Standard library only.

Implements: initialize, ping, tools/list|call, resources/list|templates/list|read, prompts/list|get.
stdout carries protocol messages only; all logging goes to stderr.
"""
from __future__ import annotations

import json
import sys

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class ToolError(Exception):
    """Reported to the model as a tool result with isError=true, not as a protocol error."""


class Tool:
    def __init__(self, name, title, description, properties, required, handler):
        self.name, self.title, self.description = name, title, description
        self.properties, self.required, self.handler = properties, required, handler

    def spec(self):
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": {"type": "object", "properties": self.properties, "required": self.required,
                                "additionalProperties": False},
                "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}

    def validate(self, args):
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        for key in self.required:
            if key not in args or args[key] in (None, ""):
                raise ToolError(f"missing required argument '{key}'")
        out = {}
        for key, val in args.items():
            spec = self.properties.get(key)
            if spec is None:
                raise ToolError(f"unknown argument '{key}'")
            kind = spec.get("type")
            if kind == "integer":
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    raise ToolError(f"'{key}' must be an integer")
                val = max(spec.get("minimum", val), min(spec.get("maximum", val), val))
            elif kind == "string" and not isinstance(val, str):
                raise ToolError(f"'{key}' must be a string")
            elif kind == "boolean" and not isinstance(val, bool):
                raise ToolError(f"'{key}' must be true or false")
            out[key] = val
        return out


class Server:
    def __init__(self, name, version, instructions, tools, resources=None, prompts=None):
        """resources: object with list(), templates(), read(uri). prompts: dict name -> (spec, builder)."""
        self.name, self.version, self.instructions = name, version, instructions
        self.tools = {t.name: t for t in tools}
        self.resources, self.prompts = resources, prompts or {}
        self.initialized = False

    # ---- dispatch
    def handle(self, msg):
        """Return a response dict, or None for notifications."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return self._error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method, mid = msg.get("method"), msg.get("id")
        if method is None:  # a response to something we never sent
            return None
        is_note = "id" not in msg
        try:
            result = self._call(method, msg.get("params") or {})
        except RpcError as exc:
            return None if is_note else self._error(mid, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - never crash the loop
            print(f"internal error in {method}: {exc!r}", file=sys.stderr)
            return None if is_note else self._error(mid, INTERNAL, f"internal error: {exc}")
        return None if is_note else {"jsonrpc": "2.0", "id": mid, "result": result}

    @staticmethod
    def _error(mid, code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    def _call(self, method, params):
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            caps = {"tools": {"listChanged": False}, "prompts": {"listChanged": False}}
            if self.resources:
                caps["resources"] = {"subscribe": False, "listChanged": False}
            self.initialized = True
            return {"protocolVersion": version, "capabilities": caps,
                    "serverInfo": {"name": self.name, "title": "skill-hub", "version": self.version},
                    "instructions": self.instructions}
        if method in ("notifications/initialized", "notifications/cancelled"):
            return {}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [t.spec() for t in self.tools.values()]}
        if method == "tools/call":
            return self._tools_call(params)
        if method == "resources/list" and self.resources:
            return {"resources": self.resources.list()}
        if method == "resources/templates/list" and self.resources:
            return {"resourceTemplates": self.resources.templates()}
        if method == "resources/read" and self.resources:
            uri = params.get("uri")
            if not uri:
                raise RpcError(INVALID_PARAMS, "uri is required")
            try:
                return {"contents": [self.resources.read(uri)]}
            except KeyError as exc:
                raise RpcError(-32002, f"resource not found: {exc.args[0]}")
        if method == "prompts/list":
            return {"prompts": [spec for spec, _ in self.prompts.values()]}
        if method == "prompts/get":
            entry = self.prompts.get(params.get("name"))
            if not entry:
                raise RpcError(INVALID_PARAMS, f"unknown prompt '{params.get('name')}'")
            return entry[1](params.get("arguments") or {})
        raise RpcError(METHOD_NOT_FOUND, f"method not found: {method}")

    def _tools_call(self, params):
        tool = self.tools.get(params.get("name"))
        if tool is None:
            raise RpcError(INVALID_PARAMS, f"unknown tool '{params.get('name')}'")
        try:
            out = tool.handler(**tool.validate(params.get("arguments") or {}))
        except ToolError as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        except Exception as exc:  # noqa: BLE001 - catalog/network errors become tool errors the model can read
            if exc.__class__.__name__ == "CatalogError":
                return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            raise
        if isinstance(out, str):
            return {"content": [{"type": "text", "text": out}], "isError": False}
        return {"content": [{"type": "text", "text": json.dumps(out, indent=2, ensure_ascii=False)}],
                "structuredContent": out if isinstance(out, dict) else {"items": out}, "isError": False}

    # ---- transport
    def serve(self, stdin=None, stdout=None):
        stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._write(stdout, self._error(None, PARSE_ERROR, "invalid JSON"))
                continue
            replies = [self.handle(m) for m in msg] if isinstance(msg, list) else [self.handle(msg)]
            replies = [r for r in replies if r is not None]
            if replies:
                self._write(stdout, replies if isinstance(msg, list) else replies[0])

    @staticmethod
    def _write(stdout, obj):
        stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
        stdout.flush()
