# PowerShell troubleshooting

| Symptom / error | Cause and fix |
|---|---|
| `The token '&&' is not a valid statement separator in this version` | Windows PowerShell 5.1. Use `A; if ($?) { B }` or `if ($LASTEXITCODE -eq 0)`, or run `pwsh` (7+). |
| `The term 'grep' (or `head`, `sed`, `awk`, `which`, `touch`, `export`) is not recognized` | Bash tool. Use the bash-to-PowerShell map in SKILL.md, or install the tool and check `Get-Command grep`. |
| `File ... cannot be loaded because running scripts is disabled on this system` | Execution policy. With user approval: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or run `powershell -ExecutionPolicy Bypass -File x.ps1` for an approved script. Prefer `RemoteSigned` for `CurrentUser`. |
| `Missing expression after unary operator '-'` or `Unexpected token '-'` | An argument starting with `-` was parsed as an operator. Quote it, or use `--%`. |
| `ParserError ... Unexpected token '}' ` or `Missing closing '}'` | Unbalanced braces, or a here-string whose closing `'@` is not at column 0. |
| `The string is missing the terminator: "` | An unescaped `"` inside a double-quoted string; use single quotes, or escape with a backtick (``` `" ```) or double it (`""`). |
| `Cannot find path '...' because it does not exist` | Wrong working directory or a bad path. Run `Get-Location`; use `Resolve-Path`; check wildcard characters and use `-LiteralPath`. |
| `Cannot bind argument to parameter 'Path' because it is null` | A variable is empty. Check `$null -eq $x` and how it was assigned. |
| `Cannot convert value "x" to type "System.Int32"` | Cast mismatch; clean the string first (`'12 '.Trim()`) or use `[int]::TryParse`. |
| `The property 'X' cannot be found on this object` (strict mode) | Missing property. Check `$obj \| Get-Member`. |
| `Access to the path is denied` | Needs elevation, the file is open elsewhere, or it is read-only/protected. Do not retry with `-Force` blindly; find the cause (`Get-Acl`, `handle.exe`, close the app). |
| `The process cannot access the file because it is being used by another process` | Another program holds it (editor, antivirus, OneDrive sync). Close it or wait; find the holder with Resource Monitor or `handle.exe`. |
| Output is garbled or has `Ã©` characters | Encoding mismatch. Read with `-Encoding utf8`; set `[Console]::OutputEncoding = [Text.Encoding]::UTF8`; write with `-Encoding utf8`. |
| File written by `>` has spaces between letters or is UTF-16 | 5.1 `>` writes UTF-16 LE. Use `\| Out-File f -Encoding utf8` or `Set-Content -Encoding utf8`. |
| A BOM appears at the start of JSON, YAML or shell scripts | 5.1 `-Encoding utf8` adds a BOM. Use `[IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding $false))`. |
| `NativeCommandError` and the command "failed" but worked | 5.1 with `2>&1`. Drop the redirect and read `$LASTEXITCODE`. |
| Exit code is 0/1 unexpectedly | `$?` reflects the last command, and a script returns the last native exit code unless you `exit` explicitly. |
| `curl` output is an object / `-H` not accepted / `Parameter cannot be found 'H'` | `curl` is the `Invoke-WebRequest` alias in 5.1. Use `curl.exe`, or `Invoke-RestMethod -Headers @{ }`. |
| `Invoke-WebRequest : ... Internet Explorer engine is not available` | Add `-UseBasicParsing` (5.1). |
| `Could not create SSL/TLS secure channel` | Old 5.1 default TLS. `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12`. |
| `Get-Content` very slow on a big file | Use `-ReadCount 0`, `[IO.File]::ReadLines($p)` or `Select-String`. |
| Command prints nothing in a script | The value was not output (assigned, or inside a function that captured it), or `Write-Host` was used in a capture. Use `Write-Output`. |
| `Format-Table` output cut off, or `...` in columns | Pipe to `Out-String -Width 250`, or select fewer columns. |
| A single result is not an array (`.Count` is empty or `[0]` fails) | Wrap with `@( )`. |
| `-eq` on arrays returns elements, not True/False | `-eq`, `-like`, `-match` filter when the left side is an array. Use `-contains` / `-in` to test membership. |
| `if ($x -eq $null)` behaves oddly with arrays | Put `$null` on the left: `$null -eq $x`. |
| `$var:` or `"$HOME:path"` fails | `$name:` is read as a scope/drive. Use `"${HOME}:path"` or `"$($HOME):path"`. |
| Backslashes in regex are wrong | Use single-quoted strings so the regex gets `\d`, and `[regex]::Escape()` for literals. |
| Wildcards in file names (`[1].txt`) fail | Use `-LiteralPath`. |
| `sc stop X` does nothing | `sc` is `Set-Content`. Use `sc.exe`, `Stop-Service` or `Get-Service`. |
| `where` returns nothing | `where` is `Where-Object`; the native program is `where.exe`. |
| `python` opens the Microsoft Store | Disable the Store alias (App execution aliases) or use `py`. |
| `npm : File ...\npm.ps1 cannot be loaded` | Execution policy. Call `npm.cmd`, or set the policy for the process with approval. |
| Command hangs forever in automation | An interactive prompt (`Read-Host`, `pause`, `-Confirm`, a pager). Pass `-Confirm:$false` after approval, add `-NonInteractive`, and use `\| Out-String` instead of paging. |
| Environment variable set but not seen by another program | `$env:X` lives in this process only. Child processes inherit it; persist with `[Environment]::SetEnvironmentVariable(..., 'User')` and restart the program. |
| `PATH` change not picked up | New shells only. Update `$env:PATH` for the current one. |
| `Unable to find type [X]` | Load the assembly (`Add-Type -AssemblyName ...`) or import the module. |
| A `.ps1` runs but changes disappear | Functions and variables set in a script live in its scope. Dot-source it: `. .\script.ps1`. |
| Unicode in a script file shows as `?` | Save the file as UTF-8 with BOM for 5.1, or use escapes like `[char]0x2713`. |

## Diagnose a command

```powershell
Get-Command <name> -All          # what will run (alias, function, cmdlet, exe)
Get-Alias <name>
$Error[0] | Format-List * -Force # full details of the last error
$Error[0].InvocationInfo.PositionMessage
Trace-Command -Name ParameterBinding -Expression { <cmd> } -PSHost     # why parameter binding failed
Set-PSDebug -Trace 1             # trace each script line; Set-PSDebug -Off
```
