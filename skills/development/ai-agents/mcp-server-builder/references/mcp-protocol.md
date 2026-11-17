# MCP protocol cheat sheet

Specification: https://modelcontextprotocol.io/specification. Messages are JSON-RPC 2.0. Over stdio each message is one line of UTF-8 JSON with no embedded newlines.

## Handshake

Client → server:
```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize",
 "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1.0"}}}
```
Server → client:
```json
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18",
 "capabilities": {"tools": {"listChanged": true}, "resources": {}, "prompts": {}},
 "serverInfo": {"name": "notes", "version": "1.0.0"}, "instructions": "Optional hints for the model"}}
```
Client → server (notification, no `id`): `{"jsonrpc": "2.0", "method": "notifications/initialized"}`

If the server does not support the requested `protocolVersion` it answers with one it does support; the client decides whether to continue.

## Tools

`tools/list` result:
```json
{"tools": [{"name": "search_notes", "title": "Search notes",
  "description": "Search the user's notes by keyword. Use when ...",
  "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Words to look for"}}, "required": ["query"]},
  "annotations": {"readOnlyHint": true}}],
 "nextCursor": "optional-page-token"}
```
`tools/call`:
```json
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_notes", "arguments": {"query": "budget"}}}
```
Result:
```json
{"content": [{"type": "text", "text": "2 notes found: ..."}], "isError": false}
```
Content types: `text`, `image` (base64 `data` + `mimeType`), `audio`, `resource_link`, embedded `resource`. Newer spec versions also allow `structuredContent` with an `outputSchema` on the tool.

Tool annotations (hints only, not security): `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`.

Tool names: 1 to 128 characters from `A-Z a-z 0-9 _ - .`, unique within the server. Some clients prefix names with the server name, so keep them short.

## Resources and prompts

- `resources/list` → `{"resources": [{"uri": "notes://all", "name": "All notes", "mimeType": "text/markdown"}]}`; `resources/read` with `{"uri": ...}` → `{"contents": [{"uri": ..., "text": ...}]}`. `resources/templates/list` lists URI templates such as `notes://{id}`.
- `prompts/list` → `{"prompts": [{"name": "summarize", "arguments": [{"name": "topic", "required": true}]}]}`; `prompts/get` returns `messages`.

## Notifications and server-to-client requests

- `notifications/tools/list_changed` (and the resources/prompts equivalents) tell the client to list again.
- `notifications/progress`, `notifications/message` (logging) and `notifications/cancelled`.
- A server may ask the client for `sampling/createMessage`, `roots/list` or `elicitation/create` only if the client declared that capability.

## Error codes

| Code | Meaning |
|---|---|
| -32700 | Parse error (invalid JSON) |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params (e.g. unknown tool name) |
| -32603 | Internal error |
| -32002 | Resource not found |

## Streamable HTTP transport

- One endpoint (e.g. `/mcp`). The client POSTs each JSON-RPC message; the server answers with `application/json` or opens an SSE stream (`text/event-stream`) for long or multi-part replies. GET on the endpoint may open a stream for server-initiated messages.
- The server can issue an `Mcp-Session-Id` header on the initialize response; the client sends it back on every later request.
- Clients send `MCP-Protocol-Version` on requests after initialization.
- Security: validate `Origin`, bind to localhost for local servers, authenticate remote ones (OAuth 2.1 authorization flow in the spec).
- The older "HTTP+SSE" transport (two endpoints) is deprecated; support it only for old clients.

## Testing tools

- `scripts/mcp_probe.py` in this skill: scripted stdio smoke test and lint.
- MCP Inspector: `npx @modelcontextprotocol/inspector <command> [args]` opens a web UI to list and call tools by hand.
