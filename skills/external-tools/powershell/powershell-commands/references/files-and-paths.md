# Files and paths

Preview anything destructive with `-WhatIf`, and list the target first.

## Navigate and inspect

```powershell
Get-Location                              # pwd
Set-Location C:\src\app                   # cd (Push-Location / Pop-Location to return)
Get-ChildItem                             # ls; aliases: ls, dir, gci
Get-ChildItem -Force                      # include hidden and system items
Get-ChildItem -Recurse -File -Filter *.log
Get-ChildItem -Recurse -Include *.ps1,*.py -Exclude node_modules   # -Include needs -Recurse or a wildcard path
Get-ChildItem -Directory                  # only folders
Get-ChildItem | Sort-Object Length -Descending | Select-Object -First 10 Name,Length
Test-Path .\file.txt                      # exists? (-PathType Container / Leaf)
Get-Item .\file.txt | Select-Object *     # all properties (size, times, attributes)
Resolve-Path .\..\x                       # absolute path (must exist)
[IO.Path]::GetFullPath('.\new\file')      # absolute path (need not exist)
Split-Path C:\a\b.txt -Parent             # C:\a   (-Leaf = b.txt, -Extension via [IO.Path]::GetExtension)
Join-Path C:\a b.txt
```

Skip heavy folders when searching a repository: filter after the fact, e.g. `Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\(node_modules|\.git|bin|obj)\\' }`.

## Read

```powershell
Get-Content f.txt                         # array of lines
Get-Content f.txt -Raw                    # one string
Get-Content f.txt -TotalCount 20          # head
Get-Content f.txt -Tail 20                # tail
Get-Content f.txt -Wait -Tail 10          # follow
Get-Content f.bin -AsByteStream -TotalCount 16   # 7+ ; 5.1 uses -Encoding Byte
[IO.File]::ReadAllText((Resolve-Path f.txt))     # fast for big files
Get-Content f.txt -Encoding utf8
```

## Write

```powershell
Set-Content f.txt 'text' -Encoding utf8           # overwrite
Add-Content f.txt 'more' -Encoding utf8           # append
'text' | Out-File f.txt -Encoding utf8 -Append
@('a','b') | Set-Content f.txt -Encoding utf8
New-Item f.txt -ItemType File                     # error if it exists, unless -Force (which truncates!)
New-Item -ItemType Directory -Force -Path a\b\c   # mkdir -p; safe on existing dirs
[IO.File]::WriteAllText("$PWD\f.txt", $text, (New-Object Text.UTF8Encoding $false))   # BOM-less UTF-8
```

`-Encoding utf8` writes a BOM in 5.1 and none in 7+. Some tools (JSON parsers, shell scripts, YAML) dislike a BOM, so use the .NET form above for them.

## Copy, move, rename, delete

```powershell
Copy-Item a.txt b.txt
Copy-Item .\src .\dst -Recurse            # copy a folder (dst becomes src's copy if it doesn't exist; else src goes inside dst)
Move-Item a.txt .\dir\
Rename-Item a.txt b.txt
Remove-Item f.txt
Remove-Item .\dir -Recurse -Force         # DESTRUCTIVE: look and confirm first
Remove-Item *.tmp -WhatIf                 # preview
robocopy src dst /MIR /XD .git node_modules /R:1 /W:1   # mirror (DELETES extra files in dst); exit codes 0-7 are success, 8+ errors
robocopy src dst /E                       # copy tree including empty folders, no deletion
```

`robocopy` is a native program: check `$LASTEXITCODE -lt 8`, not `$?`.

## Attributes, permissions, links

```powershell
(Get-Item f).IsReadOnly = $true
Set-ItemProperty f -Name IsReadOnly -Value $false
attrib +h secret.txt                      # hidden (attrib -h to unhide)
Get-Acl f | Format-List                   # permissions
icacls f                                  # show; icacls f /grant "$env:USERNAME:(R)"
takeown /f f                              # needs an elevated shell
New-Item -ItemType SymbolicLink -Path link -Target target   # needs admin or Developer Mode
New-Item -ItemType Junction -Path link -Target C:\target    # no admin needed (folders)
New-Item -ItemType HardLink -Path link -Target target
(Get-Item f).LastWriteTime = Get-Date     # touch
Get-Item f -Stream *                      # NTFS alternate streams
Unblock-File .\downloaded.ps1             # clear the "from the internet" mark
```

## Hashes, archives, temp files

```powershell
Get-FileHash f -Algorithm SHA256          # MD5, SHA1, SHA256, SHA384, SHA512
Compare-Object (Get-Content a) (Get-Content b)      # diff; SideIndicator <= only in a, => only in b
Compress-Archive -Path .\dir\* -DestinationPath out.zip            # add -Update / -Force
Expand-Archive out.zip -DestinationPath .\dir                      # -Force overwrites
tar -cf out.tar dir; tar -xf out.tar -C dest                       # tar.exe ships with Windows 10+
$tmp = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid()); New-Item -ItemType Directory $tmp
$f = New-TemporaryFile
```

## Drives, sizes, environment paths

```powershell
Get-PSDrive -PSProvider FileSystem
(Get-ChildItem .\dir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
$env:USERPROFILE; $env:TEMP; $env:APPDATA; $env:LOCALAPPDATA; $env:ProgramFiles
[Environment]::GetFolderPath('Desktop')   # also MyDocuments, UserProfile
$env:PATH -split ';'
```

## Gotchas

- `Remove-Item`, `Copy-Item` and `Get-ChildItem` treat `[` `]` `*` `?` as wildcards: use `-LiteralPath` for exact names.
- Long paths (over 260 characters) can fail in 5.1; enable long paths or use `\\?\C:\...`.
- OneDrive/Dropbox folders can be locked or "online-only"; a delete or move may fail with "being used by another process".
- Case is ignored on Windows by default; `-clike`, `-cmatch` exist for case-sensitive comparisons.
- `Get-ChildItem -Filter` is fast and uses the provider's pattern; `-Include` is slower but accepts several patterns.
