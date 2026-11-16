# Scripting patterns

## Variables, types, collections

```powershell
$name = 'x'; $n = 5; [int]$count = '42'; $path = "$HOME\file.txt"; "${name}_suffix"
$arr = @(1,2,3); $arr += 4; $arr[0]; $arr[-1]; $arr.Count        # += copies the array; use a List for many appends
$list = [System.Collections.Generic.List[string]]::new(); $list.Add('a')
$h = @{ a = 1; b = 2 }; $h['c'] = 3; $h.ContainsKey('a'); $h.Keys; $h.GetEnumerator() | Sort-Object Name
$o = [ordered]@{ first = 1; second = 2 }                           # keeps insertion order
[pscustomobject]@{ Name = 'x'; Size = 3 }                          # make an object
$null -eq $x                                                       # put $null on the left when testing
$x = if ($c) { 'a' } else { 'b' }                                  # works in 5.1 and 7
$x = $c ? 'a' : 'b'                                                # 7+ only
$x = $y ?? 'default'                                               # 7+ only
@($single).Count                                                   # force an array
```

## Conditions and loops

```powershell
if ($a -eq 1 -and $b -ne 2) { } elseif ($c -gt 3) { } else { }     # -eq -ne -gt -ge -lt -le -like -match -in -contains
switch -Regex ($s) { '^a' { 'starts with a' } default { 'other' } }
foreach ($f in Get-ChildItem) { $f.Name }
1..5 | ForEach-Object { $_ * 2 }
for ($i = 0; $i -lt 5; $i++) { }
while ($true) { if ($done) { break }; continue }
do { Start-Sleep 1 } until (Test-Path $file)
$items | ForEach-Object -Parallel { $_ } -ThrottleLimit 4          # 7+ only
```

`break`/`continue` inside `ForEach-Object` (a script block) do not behave like in loops; use `foreach` when you need them.

## Functions and parameters

```powershell
function Get-Thing {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory, ValueFromPipeline)][string]$Name,
        [ValidateSet('a','b')][string]$Mode = 'a',
        [switch]$Force
    )
    process {
        if ($PSCmdlet.ShouldProcess($Name, 'delete')) { Remove-Item $Name }   # gives -WhatIf / -Confirm for free
    }
}
```

Return values: every un-captured expression is output. Use `$null = ...` or `| Out-Null` to silence, and `return $x` only when you mean it. `Write-Host` is not output.

Script-level parameters: put `param(...)` at the top of the .ps1 file. `$PSScriptRoot` is the script's folder; `$args` holds unnamed arguments; `$MyInvocation` describes the call.

## Error handling

```powershell
$ErrorActionPreference = 'Stop'                    # make non-terminating errors terminate (script-wide)
try { Remove-Item $p -ErrorAction Stop } catch { Write-Error $_.Exception.Message; exit 1 } finally { 'cleanup' }
Get-Item nope -ErrorAction SilentlyContinue        # swallow; check $? or the result
$Error[0]                                          # last error; $Error.Clear()
throw 'message'
trap { }                                           # rarely needed
Set-StrictMode -Version Latest                     # catches typos in variable names
if (-not (Test-Path $p)) { Write-Warning "missing $p"; exit 2 }
exit 0                                             # script exit code; a failing last native command's code leaks out otherwise
```

- Native programs do not throw. Check `$LASTEXITCODE` after each. In 7.4+ `$PSNativeCommandUseErrorActionPreference = $true` makes non-zero exit codes errors.
- `-ErrorAction` does not affect native programs. `2>$null` hides their stderr.
- In 5.1, avoid `$ErrorActionPreference = 'Stop'` together with native commands writing to stderr and `2>&1`: it turns harmless stderr text into terminating errors.

## Streams and output

```powershell
Write-Output $x            # success stream (pipeline)
Write-Error 'bad'          # error stream
Write-Warning 'careful'    # 3
Write-Verbose 'detail' -Verbose  # 4
Write-Debug 'x'            # 5
Write-Information 'i' -InformationAction Continue   # 6
Write-Host 'shown on screen'
cmd *> all.log             # redirect all streams to a file (5.1: *>, 2>&1 on cmdlets is fine)
Start-Transcript -Path run.log; Stop-Transcript     # record a whole session
```

## Jobs and parallel work

```powershell
$j = Start-Job { Get-Process }; Wait-Job $j -Timeout 30; Receive-Job $j; Remove-Job $j
Start-ThreadJob { ... }                    # 7+ or ThreadJob module; lighter than Start-Job
$p = Start-Process python -ArgumentList 'server.py' -PassThru -WindowStyle Hidden; ...; Stop-Process -Id $p.Id
Start-Sleep -Milliseconds 500
```

Long-running servers: start with `Start-Process` and keep the PID; do not block the shell with `Start-Job ... | Wait-Job` unless you want to wait.

## Timeouts and retries

```powershell
$p = Start-Process app.exe -PassThru
if (-not $p.WaitForExit(30000)) { $p.Kill(); 'timed out' } else { $p.ExitCode }
function Retry([scriptblock]$s, $n = 3) { for ($i=1; $i -le $n; $i++) { try { return & $s } catch { if ($i -eq $n) { throw }; Start-Sleep ($i*2) } } }
```

## Modules, scripts and profiles

```powershell
Get-Command -Module Microsoft.PowerShell.Management | Select-Object -First 5
Get-Help Get-ChildItem -Examples; Get-Help about_Quoting_Rules; Update-Help     # Update-Help needs admin and network
Get-Command *service*; Get-Member -InputObject $obj; $obj | Get-Member
Import-Module .\MyModule.psm1; . .\helpers.ps1                 # dot-source runs a script in the current scope
Get-ExecutionPolicy -List
pwsh -NoProfile -File .\script.ps1 -Arg value                  # reproducible: skip the user's profile
```

## Regex and dates (quick)

```powershell
if ($s -match '(?<year>\d{4})-(?<mon>\d{2})') { $Matches.year }
[regex]::Replace($s, '\s+', ' ')
$s -replace '^\s+|\s+$',''
(Get-Date).ToString('o'); [DateTime]::UtcNow; [DateTimeOffset]::Now.ToUnixTimeSeconds()
New-TimeSpan -Start $a -End $b; (Get-Date).Date; (Get-Date).DayOfWeek
```

## Calling .NET and COM

```powershell
[Math]::Sqrt(16); [IO.Path]::Combine('a','b'); [Guid]::NewGuid(); [Environment]::MachineName
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -TypeDefinition 'public class X { public static int F() { return 1; } }'; [X]::F()
$sh = New-Object -ComObject WScript.Shell; $sh.Popup('hi')       # GUI popup: avoid in unattended runs
```

## Safe script template

```powershell
#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory)][string]$Path)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Path)) { throw "Not found: $Path" }
Get-ChildItem -LiteralPath $Path -File | ForEach-Object {
    if ($PSCmdlet.ShouldProcess($_.FullName, 'process')) { $_.Name }
}
```
