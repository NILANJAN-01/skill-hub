# Playwright MCP options

Source: https://github.com/microsoft/playwright-mcp (run `npx @playwright/mcp@latest --help` for the full, current list).

| Option | Use |
|---|---|
| `--headless` | No browser window (CI, remote machines). Headed is the default |
| `--browser <name>` | `chrome`, `firefox`, `webkit` or `msedge` |
| `--isolated` | Keep the profile in memory; nothing is saved between sessions |
| `--user-data-dir <path>` | Persistent profile (stays signed in); a temporary one is used if unset |
| `--storage-state <file>` | Load cookies and local storage (a signed-in test session) into an isolated session |
| `--allowed-origins <a;b>` / `--blocked-origins <a;b>` | Limit which origins the browser may request. Not a security boundary |
| `--caps <list>` | Extra tool groups: `vision` (coordinate-based), `pdf`, `devtools`; `testing` adds locator and verify tools |
| `--codegen <lang>` | Language for generated code: `typescript` (default), `python`, `java`, `csharp`, `none` |
| `--output-dir <path>` | Where screenshots and other files go |
| `--config <file>` | All options in a JSON file |
| `--no-webmcp` | Do not expose a site's own WebMCP tools (`webmcp_<tool>`); available since WebMCP support in Playwright 1.64 |

The MCP server also ships inside Playwright itself since 1.62: `npx playwright mcp` (same tools, uses the project's Playwright version and browsers).

## Team setups

**Shared test account, starts signed in**

1. Produce a session file with a Playwright setup test (`page.context().storageState({ path: 'auth/qa-user.json' })`) or `npx playwright codegen --save-storage=auth/qa-user.json <url>`.
2. Register the server with `--isolated --storage-state=<absolute path to auth/qa-user.json>`:
   ```bash
   python install.py --add-mcp playwright --mcp-arg=--isolated --mcp-arg=--storage-state=C:/qa/auth/qa-user.json
   ```
3. Keep the file out of git and refresh it when the session expires.

**Restrict to company test environments**

```bash
python install.py --add-mcp playwright --mcp-arg=--isolated \
  "--mcp-arg=--allowed-origins=https://staging.example.com;https://auth.staging.example.com"
```

**Headless on a build agent or remote machine**

`--headless --isolated --output-dir=<folder>`; collect screenshots from the output folder.

## Config file example

```json
{
  "browser": {
    "browserName": "chromium",
    "isolated": true,
    "launchOptions": { "headless": true },
    "contextOptions": { "viewport": { "width": 1280, "height": 800 }, "locale": "en-GB", "timezoneId": "Europe/London" }
  },
  "outputDir": "./mcp-output"
}
```
Start with `--config=<path to this file>`. Field names follow the server's config schema; check the README for the current version.
