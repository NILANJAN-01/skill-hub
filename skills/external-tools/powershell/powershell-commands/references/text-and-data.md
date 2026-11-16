# Text and data

PowerShell pipes objects. Convert to strings late.

## Search

```powershell
Select-String -Path .\app.log -Pattern 'ERROR'                    # grep (regex by default)
Select-String -Path .\app.log -Pattern 'a.b' -SimpleMatch         # literal
Select-String -Path .\*.log -Pattern 'ERROR' -Context 2,3         # -B 2 -A 3
Select-String -Path .\app.log -Pattern 'ERROR' -CaseSensitive
Select-String -Path .\app.log -Pattern 'DEBUG' -NotMatch          # grep -v
Select-String -Path .\app.log -Pattern 'x' -List                  # first match per file
Get-ChildItem -Recurse -File -Include *.py | Select-String 'TODO' # grep -r
Select-String 'x' -Path f | Select-Object -ExpandProperty Line
Select-String -Path f -Pattern '(\d+)-(\d+)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
(Select-String -Path f -Pattern 'x').Count                        # number of matching lines
```

`Select-String` has no `-Recurse`; feed it files from `Get-ChildItem -Recurse`.

## Compare and test strings

```powershell
'abc' -like 'a*'; 'abc' -notlike 'a*'       # wildcard
'abc' -match '^a(b)'; $Matches[1]           # regex; sets $Matches
'abc' -cmatch 'B'                           # case-sensitive (c prefix on most operators)
'a,b' -split ','; 'a','b' -join '-'
'abc' -replace 'b','X'                      # regex replace; groups use $1: 'ab' -replace '(a)(b)','$2$1'
'abc'.Contains('b'); 'abc'.StartsWith('a'); 'abc'.Substring(1,2); 'abc'.ToUpper(); '  x '.Trim()
'{0:N2} of {1}' -f 3.14159, 'x'            # format operator
'a' -in 'a','b'; 'a','b' -contains 'a'       # membership
[regex]::Escape('a.b'); [regex]::Matches($text, '\d+') | ForEach-Object Value
```

## Edit files

```powershell
(Get-Content f.txt -Raw) -replace 'old','new' | Set-Content f.txt -Encoding utf8   # sed -i
(Get-Content f.txt) | Where-Object { $_ -notmatch '^#' } | Set-Content f.txt        # delete matching lines
Get-Content f.txt | Select-Object -Skip 1                                           # drop header
Get-Content f.txt | Select-Object -Index 4                                          # line 5
(Get-Content f.txt)[-3..-1]                                                         # last 3 lines
```

Read the whole file into memory (the parentheses) before writing back to the same path, or the write will truncate the file while it is being read.

## Sort, group, count, unique

```powershell
Get-Content f | Sort-Object                          # sort; -Descending, -Unique, -CaseSensitive
Get-Content f | Sort-Object -Unique                  # sort -u
Get-Content f | Group-Object | Sort-Object Count -Descending | Select-Object Count,Name   # uniq -c
Get-Content f | Measure-Object -Line -Word -Character
Get-Process | Measure-Object WorkingSet64 -Sum -Average -Maximum
1..10 | Where-Object { $_ % 2 -eq 0 }
Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name,CPU
```

## Select columns and reshape

```powershell
Get-Process | Select-Object Name,Id,@{n='MemMB';e={[int]($_.WorkingSet64/1MB)}}   # calculated column
Get-Process | Select-Object -ExpandProperty Name      # plain strings, not objects
Get-Process | Where-Object CPU -gt 100                # simple syntax
Get-Process | ForEach-Object { $_.Name }              # or: ForEach-Object Name
(Get-Content f) -split '\s+' | Where-Object { $_ }    # words
'a b  c' -split '\s+'
```

## Output formatting

```powershell
Format-Table -AutoSize -Wrap          # for display only: never pipe Format-* into other commands
Format-List *
Out-String -Width 200                 # avoid truncated columns when capturing a table as text
$obj | ConvertTo-Json -Depth 10       # the default depth (2) silently truncates nested data
Write-Output $x; Write-Host 'info'    # Write-Host is display-only, not captured by pipelines in the usual way
```

## JSON

```powershell
$j = Get-Content data.json -Raw | ConvertFrom-Json
$j.items[0].name
$j | ConvertTo-Json -Depth 10 | Set-Content out.json -Encoding utf8
$j.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }     # enumerate keys
'{"a":1}' | ConvertFrom-Json
Get-Content data.json -Raw | ConvertFrom-Json -AsHashtable               # 7+ only
# add or change a property
$j | Add-Member -NotePropertyName extra -NotePropertyValue 1 -Force
```

`ConvertFrom-Json` returns `PSCustomObject`, not a hashtable (in 5.1 there is no `-AsHashtable`). Arrays of one element can unwrap: wrap with `@( ... )`.

## CSV, XML, INI, YAML

```powershell
Import-Csv data.csv | Where-Object { [int]$_.age -gt 30 }          # values are strings: cast
Import-Csv data.csv -Delimiter ';'
Get-Process | Select-Object Name,Id | Export-Csv out.csv -NoTypeInformation -Encoding utf8
ConvertFrom-Csv $text; ConvertTo-Csv $objs -NoTypeInformation
[xml]$x = Get-Content f.xml -Raw; $x.root.item.name
Select-Xml -Path f.xml -XPath '//item/@id' | ForEach-Object { $_.Node.Value }
$x.Save("$PWD\out.xml")
Get-Content a.ini | Where-Object { $_ -match '^(\w+)=(.*)$' } | ForEach-Object { $Matches[1], $Matches[2] }
# YAML has no built-in cmdlet: 7+/5.1 need the powershell-yaml module (Install-Module powershell-yaml) or an external tool such as yq.
```

## Encoding and special characters

```powershell
[Console]::OutputEncoding = [Text.Encoding]::UTF8     # fix garbled output from native tools
$OutputEncoding = [Text.Encoding]::UTF8               # encoding used when piping to native programs
Get-Content f.txt -Encoding utf8                      # read as UTF-8 when there is no BOM (5.1 assumes ANSI)
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s)); [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b))
"tab`t newline`n quote`" dollar`$ backtick``"
```

## Dates and numbers

```powershell
Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
(Get-Date).AddDays(-7); [datetime]::Parse('2026-01-31'); [datetime]'2026-01-31'
(Get-Date) - (Get-Date '2026-01-01')        # TimeSpan; .TotalDays
Get-Date -UFormat %s                        # Unix time (5.1 local; use [DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
[math]::Round(3.14159, 2); [int]'42'; [double]'1.5'; 1KB, 1MB, 1GB
'{0:N0}' -f 1234567; '{0:P1}' -f 0.256; '{0:X}' -f 255
```
