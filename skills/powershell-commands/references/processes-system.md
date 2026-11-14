# Processes, services and system

Changes to services, the registry, scheduled tasks and the machine need user confirmation. Many need an elevated (administrator) shell; check with the test below.

```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

## Processes

```powershell
Get-Process                                   # ps
Get-Process -Name chrome                      # -Id 123
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name,Id,@{n='MB';e={[int]($_.WorkingSet64/1MB)}}
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId,CommandLine   # full command line
Start-Process notepad                         # launch detached
Start-Process python -ArgumentList 'app.py','--flag' -NoNewWindow -Wait -PassThru   # run and wait, get exit code via .ExitCode
Start-Process pwsh -Verb RunAs                # elevated (shows a UAC prompt)
Start-Process .\app.exe -RedirectStandardOutput out.txt -RedirectStandardError err.txt -Wait
Stop-Process -Id 123                          # add -Force; CONFIRM before killing
Stop-Process -Name notepad -WhatIf
Wait-Process -Id 123 -Timeout 30
Get-Process -Id $PID                          # this shell
taskkill /PID 123 /F /T                       # kill a process tree (native)
```

Port owner: `Get-NetTCPConnection -LocalPort 8080 | Select-Object OwningProcess,State` then `Get-Process -Id <pid>`.

## Services

```powershell
Get-Service                                   # -Name wuauserv ; Where-Object Status -eq Running
Get-Service | Where-Object { $_.Status -eq 'Running' -and $_.StartType -eq 'Automatic' }
Start-Service Spooler; Stop-Service Spooler; Restart-Service Spooler    # elevated; confirm first
Set-Service Spooler -StartupType Disabled     # Automatic | Manual | Disabled
Get-CimInstance Win32_Service -Filter "Name='Spooler'" | Select-Object Name,PathName,StartName
sc.exe query Spooler                          # note .exe: `sc` is an alias of Set-Content
```

## Scheduled tasks

```powershell
Get-ScheduledTask | Where-Object State -ne Disabled
$a = New-ScheduledTaskAction -Execute 'pwsh' -Argument '-NoProfile -File C:\jobs\run.ps1'
$t = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName 'NightlyJob' -Action $a -Trigger $t        # elevated for SYSTEM tasks
Start-ScheduledTask NightlyJob; Unregister-ScheduledTask NightlyJob -Confirm:$false   # confirm with the user
schtasks /query /fo LIST /v                   # native alternative
```

## Event logs

```powershell
Get-WinEvent -LogName System -MaxEvents 20
Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2; StartTime=(Get-Date).AddHours(-6)}   # errors in the last 6 h (Level 1 critical, 2 error, 3 warning)
Get-WinEvent -ListLog * | Where-Object RecordCount | Sort-Object RecordCount -Descending | Select-Object -First 10 LogName,RecordCount
Get-EventLog -LogName System -Newest 20       # 5.1 only
```

## Registry

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft' | Select-Object -First 5
Test-Path 'HKCU:\Software\MyApp'
New-Item 'HKCU:\Software\MyApp' -Force
Set-ItemProperty 'HKCU:\Software\MyApp' -Name Setting -Value 1 -Type DWord   # back up first: reg export HKCU\Software\MyApp backup.reg
Remove-ItemProperty 'HKCU:\Software\MyApp' -Name Setting                      # confirm first
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion /v ProgramFilesDir   # native alternative
```

HKLM writes need elevation. Registry edits can break Windows: confirm and back up.

## Environment variables

```powershell
$env:NAME = 'value'                           # this session only
$env:PATH += ';C:\tools\bin'                  # this session only
Get-ChildItem Env:                            # all; Get-ChildItem Env: | Where-Object Name -like 'JAVA*'
Remove-Item Env:NAME
[Environment]::SetEnvironmentVariable('NAME','value','User')       # persistent for the user (new shells only); 'Machine' needs admin
[Environment]::GetEnvironmentVariable('PATH','User') -split ';'
setx NAME value                               # native persistent; truncates values over 1024 characters
```

Persistent changes do not affect the current shell; set `$env:NAME` too.

## System information

```powershell
Get-ComputerInfo | Select-Object OsName,OsVersion,OsArchitecture,CsTotalPhysicalMemory     # slow; 7+ and 5.1
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,LastBootUpTime,FreePhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,@{n='FreeGB';e={[int]($_.FreeSpace/1GB)}},@{n='SizeGB';e={[int]($_.Size/1GB)}}
Get-Volume; Get-Disk; Get-PhysicalDisk
hostname; $env:COMPUTERNAME; whoami; whoami /groups
systeminfo                                    # native
(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime     # uptime
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5
```

`Get-WmiObject` is removed in 7; use `Get-CimInstance`.

## Packages and installed software

```powershell
winget search git; winget list; winget install --id Git.Git -e; winget upgrade --all     # install/upgrade only with user approval
winget show --id Git.Git
Get-Package; Get-Module -ListAvailable
Install-Module PSReadLine -Scope CurrentUser; Update-Module; Get-InstalledModule         # PowerShell Gallery
choco list --local-only; scoop list           # if those managers are installed
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName,DisplayVersion | Sort-Object DisplayName
Get-AppxPackage | Select-Object Name,Version
Get-WindowsOptionalFeature -Online | Where-Object State -eq Enabled     # elevated
```

## Power, clipboard, misc

```powershell
Get-Clipboard; 'text' | Set-Clipboard
Start-Process shell:startup                    # open a shell folder
Invoke-Item .\file.pdf                         # open with the default app
Restart-Computer -WhatIf; Stop-Computer -WhatIf   # never run for real without explicit confirmation
shutdown /a                                    # abort a pending shutdown
powercfg /query; powercfg /batteryreport
Get-NetAdapter; Get-NetIPAddress               # see network-and-web.md
Measure-Command { .\script.ps1 }               # time a command
$PROFILE                                       # path of your profile script
```
