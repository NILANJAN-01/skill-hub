---
name: powershell-commands
description: "Run shell tasks correctly in PowerShell on Windows: files, text search, processes, network, Git, builds, with a bash-to-PowerShell map. Use when the shell is PowerShell, a `&&`, `grep`, `head` or `export` command fails, or quoting, encoding or exit codes go wrong."
license: MIT
compatibility: Windows PowerShell 5.1 and PowerShell 7+ (commands marked 7+ do not work in 5.1). Most commands also work on macOS/Linux with PowerShell 7.
metadata:
  title: "PowerShell Commands for Agents"
  category: shell-tools
---

# PowerShell commands for agents

A playbook for running terminal tasks in PowerShell without the usual failures: bash syntax pasted into PowerShell, broken quoting, wrong encodings and misread exit codes.

## When to use

- The shell is PowerShell (the Windows default) and you need to read, search, create, move or delete files, run programs, inspect processes or the network, or drive Git and build tools.
- A command written for bash fails in PowerShell (`&&`, `||`, `export`, `grep`, `head`, `sed`, `which`, `rm -rf`, `2>/dev/null`).
- Quoting, escaping, here-strings, encoding (BOM, garbled text), or "exit code 1 although it worked" problems.

## When NOT to use

- The shell is bash, zsh or cmd.exe and cannot start PowerShell: use that shell's syntax (for cmd, `cmd /c`).
- Writing a large reusable module or a Pester test suite: use PowerShell's own documentation.

## Safety rules for the agent

- **Look before you delete or overwrite.** Run `Get-ChildItem <target>` first. Confirm with the user before `Remove-Item -Recurse`, `Clear-Content`, `Stop-Process`, `Restart-Computer`, registry writes, firewall or service changes, `git reset --hard` or `git clean`.
- Preview with `-WhatIf` (most cmdlets that change things support it). Add `-Confirm:$false` only after the user agreed.
- Never pipe a downloaded script straight into `Invoke-Expression` (`iex`) without reading it. Do not weaken `ExecutionPolicy` machine-wide; use `-Scope Process` if truly needed, and ask first.
- Never print or log secrets. Read them from `$env:NAME` or a secret store; do not hard-code them.
- Do not use `New-Item -Force` on an existing file: it truncates it.

## First step: know your shell

```powershell
$PSVersionTable.PSVersion        # 5.1 = Windows PowerShell, 7.x = PowerShell
$PSVersionTable.PSEdition        # Desktop (5.1) or Core (7+)
Get-Location                     # where am I
```

| Feature | 5.1 | 7+ |
|---|---|---|
| `&&` and `\|\|` pipeline chain | No (parser error) | Yes |
| `?:` ternary, `??`, `?.` | No | Yes |
| `ConvertFrom-Json -AsHashtable` | No | Yes |
| Default encoding of `>` / `Out-File` | UTF-16 LE | UTF-8 without BOM |
| Default encoding of `Set-Content` | System ANSI codepage | UTF-8 without BOM |
| `ForEach-Object -Parallel` | No | Yes |
| `curl` / `wget` | Aliases of `Invoke-WebRequest` | Aliases removed |

When unsure, write code that works in both.

## Top rules (these cause most failures)

1. **No `&&` in 5.1.** Use `A; if ($?) { B }` or `A; if ($LASTEXITCODE -eq 0) { B }`. Use `;` alone only when B should run regardless.
2. **Commands return objects, not text.** Filter with `Where-Object`, pick with `Select-Object`, and convert to text with `Out-String` or `-join "`n"` only at the end.
3. **Quoting:** single quotes are literal; double quotes expand `$var` and `$(expr)`; the escape character is the backtick, not backslash. Use single quotes for regex and paths that contain `$`.
4. **Native programs:** call a quoted path with the call operator: `& "C:\Program Files\App\app.exe" arg1`. Use the stop-parsing token `--%` when arguments contain `-`, `@` or `$` that PowerShell would interpret.
5. **Avoid `2>&1` on native programs in 5.1.** It wraps stderr lines in `ErrorRecord` objects and can set `$?` to `$false` even when the exit code is 0. Check `$LASTEXITCODE` instead.
6. **Exit codes:** `$?` is the success of the last command; `$LASTEXITCODE` is a native program's exit code. Cmdlet errors are non-terminating by default: add `-ErrorAction Stop` and wrap in `try { } catch { }` to really catch them.
7. **Paths:** use `-LiteralPath` when a name contains `[`, `]` or wildcards. Quote paths with spaces. Both `\` and `/` work. Build paths with `Join-Path`, not string concatenation.
8. **Encoding:** pass `-Encoding utf8` to `Set-Content`, `Out-File` and `Add-Content` when another tool reads the file. In 5.1 `utf8` writes a BOM; for BOM-less use `[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))`.
9. **Multi-line text for a program:** use a single-quoted here-string with the closing `'@` at column 0:
   ```powershell
   $msg = @'
   line one with $literal dollars
   '@
   git commit -m $msg
   ```
10. **No prompts in non-interactive runs:** `Read-Host`, `pause`, `Out-GridView` and `Get-Credential` block or fail.
11. **Bash-only syntax does not exist:** `/dev/null` is `$null` (`2>$null`), `export X=1` is `$env:X = '1'`, and backticks are not command substitution. Capture output with `$x = command`.

## Bash to PowerShell map

| Task | bash | PowerShell |
|---|---|---|
| List files | `ls -la` | `Get-ChildItem -Force` (`ls`, `dir`, `gci`) |
| Recursive find | `find . -name "*.py"` | `Get-ChildItem -Recurse -Filter *.py` |
| Show file | `cat f` | `Get-Content f` (`-Raw` for one string) |
| First / last lines | `head -n 5 f` / `tail -n 5 f` | `Get-Content f -TotalCount 5` / `Get-Content f -Tail 5` |
| Follow file | `tail -f f` | `Get-Content f -Wait -Tail 10` |
| Search text in files | `grep -rn "x" .` | `Get-ChildItem -Recurse -File \| Select-String -Pattern 'x'` |
| Count lines | `wc -l f` | `(Get-Content f \| Measure-Object -Line).Lines` |
| Replace text | `sed -i 's/a/b/g' f` | `(Get-Content f -Raw) -replace 'a','b' \| Set-Content f -Encoding utf8` |
| Create dir | `mkdir -p a/b` | `New-Item -ItemType Directory -Force a\b` |
| Create empty file | `touch f` | `if (-not (Test-Path f)) { New-Item -ItemType File f }` |
| Copy / move | `cp -r a b` / `mv a b` | `Copy-Item a b -Recurse` / `Move-Item a b` |
| Delete | `rm -rf d` | `Remove-Item d -Recurse -Force` (confirm first) |
| Set / read env var | `export X=1` / `$X` | `$env:X = '1'` / `$env:X` |
| Locate command | `which git` | `(Get-Command git).Source` |
| Discard output | `2>/dev/null` | `2>$null` |
| Write to file | `cmd > f` / `>> f` | `cmd \| Out-File f -Encoding utf8` / add `-Append` |
| Processes / kill | `ps aux` / `kill 123` | `Get-Process` / `Stop-Process -Id 123` |
| Sleep | `sleep 5` | `Start-Sleep -Seconds 5` |
| Chain on success | `a && b` | `a; if ($?) { b }` (5.1) or `a && b` (7+) |
| JSON field | `jq .a f` | `(Get-Content f -Raw \| ConvertFrom-Json).a` |
| HTTP GET | `curl url` | `Invoke-RestMethod url`, or `curl.exe -s url` |
| Download | `wget url` | `Invoke-WebRequest url -OutFile f` |
| Hash | `sha256sum f` | `Get-FileHash f -Algorithm SHA256` |
| Folder size | `du -sh d` | `(Get-ChildItem d -Recurse -File \| Measure-Object Length -Sum).Sum / 1MB` |
| Symlink | `ln -s t l` | `New-Item -ItemType SymbolicLink -Path l -Target t` |

In 5.1, `curl` and `wget` are aliases of `Invoke-WebRequest`, not the real programs. Use `curl.exe` for the real curl.

## Command references (read only the one you need)

- [references/files-and-paths.md](references/files-and-paths.md): list, find, read, write, copy, move, delete, permissions, archives, hashes, symlinks.
- [references/text-and-data.md](references/text-and-data.md): search, regex, replace, sort, unique, columns, JSON, CSV, XML, formatting output.
- [references/processes-system.md](references/processes-system.md): processes, services, scheduled tasks, event logs, registry, environment, disks, OS info, packages (winget).
- [references/network-and-web.md](references/network-and-web.md): HTTP, downloads, DNS, ports, connectivity, firewall, SSH.
- [references/dev-tools.md](references/dev-tools.md): Git, Python, Node, .NET, Docker, adb and other native tools from PowerShell, with path and quoting gotchas.
- [references/scripting-patterns.md](references/scripting-patterns.md): variables, arrays, hashtables, loops, functions, parameters, error handling, background jobs, dates.
- [references/troubleshooting.md](references/troubleshooting.md): error messages and fixes.

## Troubleshooting (most common)

| Symptom / error | Fix |
|---|---|
| `The token '&&' is not a valid statement separator` | 5.1: use `A; if ($?) { B }`, or run in PowerShell 7 (`pwsh`). |
| `... is not recognized as the name of a cmdlet` | Usually a bash command. See the map above, or run `Get-Command <name>`. |
| `running scripts is disabled on this system` | With user approval: `Set-ExecutionPolicy -Scope Process Bypass` for this session only. |
| Garbled characters or a BOM in files | Pass `-Encoding utf8`; see rule 8. |
| `Illegal characters in path` | Check quoting; use `-LiteralPath`. |
| Exit code 1 though the program succeeded | Remove `2>&1` on native programs (5.1) and read `$LASTEXITCODE`. |
| `curl` returns an object with `Content` | It is `Invoke-WebRequest`; use `curl.exe`. |
