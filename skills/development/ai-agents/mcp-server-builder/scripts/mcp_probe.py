#!/usr/bin/env python3
"""Smoke-test an MCP server over stdio and lint what it exposes.

Usage:
    python mcp_probe.py [--timeout 15] [--call TOOL --args JSON] [--json] -- <command> [args...]

Starts the server command, runs the initialize handshake, lists tools,
resources and prompts (following pagination), lints the tool definitions and
optionally calls one tool. Standard library only.

Exit codes: 0 no errors, 1 lint/call errors, 2 server failed to start or answer.
"""
import argparse
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

PROTOCOL_VERSION = "2025-06-18"
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
MAX_PAGES = 20


class ProbeError(Exception):
    """The server could not be started or did not answer."""


class StdioClient:
    def __init__(self, cmd, timeout):
        exe = shutil.which(cmd[0]) or cmd[0]
        self.timeout = timeout
        self.stdout_noise = []
        self.notifications = []
        self.stderr_lines = []
        self._q = queue.Queue()
        self._next_id = 1
        try:
            self.proc = subprocess.Popen(
                [exe] + list(cmd[1:]), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as exc:
            raise ProbeError("could not start %r: %s" % (cmd[0], exc))
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self):
        for line in self.proc.stdout:
            self._q.put(line)
        self._q.put(None)

    def _pump_stderr(self):
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip("\n"))
            if len(self.stderr_lines) > 200:
                del self.stderr_lines[0]

    def _send(self, msg):
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError) as exc:
            raise ProbeError("server closed its input: %s" % exc)

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def request(self, method, params=None):
        req_id = self._next_id
        self._next_id += 1
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        deadline = time.time() + self.timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                raise ProbeError("timed out after %ss waiting for %s" % (self.timeout, method))
            try:
                line = self._q.get(timeout=left)
            except queue.Empty:
                continue
            if line is None:
                try:
                    code = self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    code = None
                raise ProbeError("server exited (code %s) while waiting for %s" % (code, method))
            text = line.strip()
            if not text:
                continue
            try:
                data = json.loads(text)
            except ValueError:
                self.stdout_noise.append(text[:200])
                continue
            if not isinstance(data, dict):
                self.stdout_noise.append(text[:200])
                continue
            if "method" in data and "id" in data:
                # Server-to-client request (roots/list, sampling, ...): we declared no capabilities.
                self._send({"jsonrpc": "2.0", "id": data["id"],
                            "error": {"code": -32601, "message": "probe does not support " + str(data["method"])}})
                continue
            if "method" in data:
                self.notifications.append(data["method"])
                continue
            if data.get("id") == req_id:
                return data

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def lint_tools(tools):
    """Return a list of (level, message) findings for MCP tool definitions."""
    findings = []
    seen = set()
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            findings.append(("ERROR", "tools[%d] is not an object" % i))
            continue
        name = tool.get("name")
        label = name if isinstance(name, str) else "tools[%d]" % i
        if not isinstance(name, str) or not name:
            findings.append(("ERROR", "%s: missing name" % label))
        else:
            if not TOOL_NAME_RE.match(name):
                findings.append(("WARN", "%s: name should be 1-128 chars of A-Z a-z 0-9 _ - ." % label))
            if name in seen:
                findings.append(("ERROR", "%s: duplicate tool name" % label))
            seen.add(name)
        desc = tool.get("description")
        if not isinstance(desc, str) or not desc.strip():
            findings.append(("ERROR", "%s: missing description (the model cannot tell when to use it)" % label))
        elif len(desc.strip()) < 40:
            findings.append(("WARN", "%s: description is very short; say what it does and when to use it" % label))
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            findings.append(("ERROR", "%s: missing inputSchema" % label))
            continue
        if schema.get("type") != "object":
            findings.append(("ERROR", '%s: inputSchema type must be "object"' % label))
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            findings.append(("ERROR", "%s: inputSchema.properties must be an object" % label))
            props = {}
        for req in schema.get("required", []) or []:
            if req not in props:
                findings.append(("ERROR", "%s: required parameter %r is not in properties" % (label, req)))
        for pname, pschema in props.items():
            if isinstance(pschema, dict) and not pschema.get("description") and "enum" not in pschema:
                findings.append(("WARN", "%s: parameter %r has no description" % (label, pname)))
        if len(props) > 10:
            findings.append(("WARN", "%s: %d parameters; consider splitting the tool" % (label, len(props))))
    return findings


def _list_all(client, method, key):
    items, cursor = [], None
    for _ in range(MAX_PAGES):
        resp = client.request(method, {"cursor": cursor} if cursor else {})
        if "error" in resp:
            return items, resp["error"]
        result = resp.get("result") or {}
        items.extend(result.get(key) or [])
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return items, None


def run_probe(cmd, timeout=15.0, call=None, call_args=None):
    """Probe a server. Returns a report dict; raises ProbeError if it never answers."""
    report = {"command": cmd, "findings": []}
    client = StdioClient(cmd, timeout)
    try:
        try:
            init = client.request("initialize", {
                "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "mcp-probe", "version": "1.0.0"}})
        except ProbeError as exc:
            raise ProbeError("%s\n--- server stderr (tail) ---\n%s"
                             % (exc, "\n".join(client.stderr_lines[-20:])))
        if "error" in init:
            raise ProbeError("initialize failed: %s" % json.dumps(init["error"]))
        result = init.get("result") or {}
        caps = result.get("capabilities") or {}
        report["server"] = result.get("serverInfo") or {}
        report["protocolVersion"] = result.get("protocolVersion")
        report["capabilities"] = sorted(caps)
        report["instructions"] = result.get("instructions")
        if result.get("protocolVersion") != PROTOCOL_VERSION:
            report["findings"].append(("INFO", "server negotiated protocol %s (probe asked for %s)"
                                       % (result.get("protocolVersion"), PROTOCOL_VERSION)))
        client.notify("notifications/initialized")

        for cap, method, key in (("tools", "tools/list", "tools"),
                                 ("resources", "resources/list", "resources"),
                                 ("prompts", "prompts/list", "prompts")):
            if cap not in caps:
                report[key] = []
                continue
            items, err = _list_all(client, method, key)
            report[key] = items
            if err:
                report["findings"].append(("ERROR", "%s failed: %s" % (method, json.dumps(err))))
        if not caps.get("tools") and "tools" not in caps:
            report["findings"].append(("INFO", "server does not declare the tools capability"))
        report["findings"].extend(lint_tools(report["tools"]))

        if call:
            names = {t.get("name") for t in report["tools"] if isinstance(t, dict)}
            if call not in names:
                report["findings"].append(("ERROR", "tool %r is not in tools/list" % call))
            resp = client.request("tools/call", {"name": call, "arguments": call_args or {}})
            report["call"] = resp.get("result", resp.get("error"))
            if "error" in resp:
                report["findings"].append(("ERROR", "tools/call %s: %s" % (call, json.dumps(resp["error"]))))
            elif (resp.get("result") or {}).get("isError"):
                report["findings"].append(("WARN", "tools/call %s returned isError: true" % call))
    finally:
        client.close()
        report["stdout_noise"] = client.stdout_noise
        report["notifications"] = client.notifications
        report["stderr_tail"] = client.stderr_lines[-10:]
    for line in report["stdout_noise"][:5]:
        report["findings"].append(("ERROR", "non-JSON line on stdout (log to stderr instead): %s" % line))
    return report


def format_text(report):
    out = []
    server = report.get("server") or {}
    out.append("Server: %s %s (protocol %s)" % (server.get("name", "?"), server.get("version", ""),
                                               report.get("protocolVersion")))
    out.append("Capabilities: %s" % (", ".join(report.get("capabilities") or []) or "none"))
    for key in ("tools", "resources", "prompts"):
        items = report.get(key) or []
        out.append("\n%s (%d):" % (key.capitalize(), len(items)))
        for item in items:
            if not isinstance(item, dict):
                continue
            ident = item.get("name") or item.get("uri") or "?"
            desc = (item.get("description") or "").strip().splitlines()
            out.append("  - %s%s" % (ident, (": " + desc[0][:100]) if desc else ""))
    if "call" in report:
        out.append("\nCall result:\n" + json.dumps(report["call"], indent=2)[:2000])
    out.append("\nFindings:")
    if report["findings"]:
        for level, msg in report["findings"]:
            out.append("  %-5s %s" % (level, msg))
    else:
        out.append("  none")
    if report.get("stderr_tail"):
        out.append("\nServer stderr (tail):")
        out.extend("  " + line for line in report["stderr_tail"])
    return "\n".join(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        split = argv.index("--")
        own, cmd = argv[:split], argv[split + 1:]
    else:
        own, cmd = argv, []
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--timeout", type=float, default=15.0, help="seconds to wait for each reply")
    parser.add_argument("--call", help="name of a tool to call after listing")
    parser.add_argument("--args", default="{}", help="JSON object of arguments for --call")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    opts = parser.parse_args(own)
    if not cmd:
        parser.error("give the server command after --, e.g. -- python server.py")
    try:
        call_args = json.loads(opts.args)
    except ValueError as exc:
        parser.error("--args is not valid JSON: %s" % exc)
    if not isinstance(call_args, dict):
        parser.error("--args must be a JSON object")
    try:
        report = run_probe(cmd, opts.timeout, opts.call, call_args)
    except ProbeError as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        return 2
    if opts.json:
        report["findings"] = [{"level": l, "message": m} for l, m in report["findings"]]
        print(json.dumps(report, indent=2))
        return 1 if any(f["level"] == "ERROR" for f in report["findings"]) else 0
    print(format_text(report))
    return 1 if any(level == "ERROR" for level, _ in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
