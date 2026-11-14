# Developer tools from PowerShell

Calling native programs (git, python, node, dotnet, docker, adb) is where most PowerShell mistakes happen. Rules first, then tool recipes.

## Calling native programs

```powershell
git status                                  # on PATH: just call it
& "C:\Program Files\Git\bin\git.exe" status # path with spaces: call operator &
$gitArgs = @('commit','-m','fix: x y'); git @gitArgs      # splatting an array of arguments
git log --format='%h %s' -n 5               # single quotes keep % and = untouched
git log --% --format=%H                     # stop-parsing: rest of the line goes to the program as is
(Get-Command python -ErrorAction SilentlyContinue).Source    # is it installed? where?
$LASTEXITCODE                               # exit code of the last native program
$out = git rev-parse HEAD; if ($LASTEXITCODE -ne 0) { throw 'git failed' }
```

- Pass an empty string or a string with quotes by escaping for the target program: `foo.exe '"a b"'` in 5.1 sends literal quotes; 7.3+ has `$PSNativeCommandArgumentPassing = 'Standard'` to do it properly.
- In 5.1 avoid `2>&1` on native programs (stderr becomes error records). To capture both streams, use `cmd /c "prog 2>&1"` or `Start-Process -RedirectStandardError`.
- Many tools write progress to stderr (git, pip, npm); that is not a failure. Judge by `$LASTEXITCODE`.
- A line starting with a quoted path needs `&`: `& 'C:\a b\x.exe'`.
- Environment for one command: `$env:CI = '1'; npm test; Remove-Item Env:CI` (there is no `VAR=1 cmd` prefix).
- `Out-File`/`>` re-encodes piped text. For binary or exact bytes, use `cmd /c "prog > file"` or `Start-Process -RedirectStandardOutput`.

## Git

```powershell
git status -sb; git diff --stat; git log --oneline -n 10
git add -A; git commit -m 'message'                    # commit/push only when the user asks
git switch -c feature/x; git switch main
git fetch --prune; git pull --ff-only
git push -u origin HEAD
git stash push -m 'wip'; git stash pop
git diff --name-only main...HEAD                       # files changed on this branch
git branch --merged main | Where-Object { $_ -notmatch '^\*|main' }
git config --global core.autocrlf true                 # Windows line endings
git -C C:\path\to\repo status                          # run without cd
git commit -F msg.txt                                  # long messages from a file
```

Multi-line commit message in one command:

```powershell
git commit -m @'
Short summary

Longer body with $dollars and "quotes".
'@
```

Destructive commands (`git reset --hard`, `git clean -fd`, `git push --force`, `git branch -D`, `git checkout -- .`) need user confirmation. Preview with `git clean -nd`.

Line endings: `warning: LF will be replaced by CRLF` is informational. Set `.gitattributes` (`* text=auto`) to control it.

## Python

```powershell
python --version; py -0                                # py launcher lists installed versions
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1                           # may be blocked: Set-ExecutionPolicy -Scope Process Bypass (ask first)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt     # works without activation
python -m pip install --upgrade pip
python -m pytest -q; python -m unittest discover -v
python -c "import sys; print(sys.executable)"          # which python is used
python -I script.py                                    # isolated mode for untrusted data
$env:PYTHONIOENCODING = 'utf-8'                        # fix UnicodeEncodeError on console output
$env:PYTHONUTF8 = '1'
```

If `python` opens the Microsoft Store, disable the alias in Settings > Apps > Advanced app settings > App execution aliases, or use `py`.

## Node / npm

```powershell
node --version; npm --version
npm ci; npm install; npm run build; npm test -- --watch=false
npx --yes some-tool
npm ls --depth=0; npm outdated; npm audit
$env:NODE_OPTIONS = '--max-old-space-size=4096'
```

`npm.ps1` can be blocked by execution policy: call `npm.cmd` instead.

## .NET, Java, Go, Rust

```powershell
dotnet --info; dotnet new console -n App; dotnet build -c Release; dotnet test; dotnet run --project .\App
dotnet publish -c Release -r win-x64 --self-contained false -o out
java -version; $env:JAVA_HOME; .\gradlew.bat build; .\gradlew.bat test --tests 'com.x.MyTest'; mvn -q test
go version; go build ./...; go test ./...
cargo build --release; cargo test
```

Gradle wrapper on Windows is `gradlew.bat` (not `./gradlew`).

## Docker

```powershell
docker ps -a; docker images; docker logs -f --tail 100 name
docker run --rm -it -v "${PWD}:/work" -w /work python:3.12 python script.py     # ${PWD} avoids parsing problems with ':'
docker compose up -d --build; docker compose down
docker system prune                                    # DESTRUCTIVE: confirm first
```

Use `"${PWD}:/work"` (braces) because `$PWD:` would be read as a drive-qualified variable.

## Android (adb)

```powershell
adb devices -l
adb -s <serial> shell getprop ro.build.version.release
adb logcat -d -v threadtime > logcat.txt               # cmd redirect keeps text intact on 7+; on 5.1 use: cmd /c "adb logcat -d > logcat.txt"
adb shell uiautomator dump /sdcard/window_dump.xml; adb pull /sdcard/window_dump.xml .
adb install -r app.apk; adb shell pm list packages | Select-String 'myapp'
adb shell "dumpsys activity activities | grep mResumedActivity"    # quote so the grep runs on the device
```

Quote the whole remote command so PowerShell does not interpret `|`, `>` or `$`. `adb pull`/`exec-out screencap -p` write binary: do not redirect binary output with `>` in 5.1.

## Build, format and search tooling

```powershell
rg -n 'TODO' --glob '!node_modules'                    # ripgrep, if installed: much faster than Select-String
fd -e py                                               # fd, if installed
jq '.items[].name' data.json                           # jq, if installed; otherwise ConvertFrom-Json
make test                                              # needs make installed; or use the tool's own commands
code .                                                 # open an editor in this folder, if on PATH
```

Check that an optional tool exists before using it: `if (Get-Command rg -ErrorAction SilentlyContinue) { ... } else { ... }`.

## Running other shells

```powershell
bash -lc 'ls -la | head'                               # WSL / Git Bash, if installed
wsl -e bash -c 'echo $HOME'                            # note: use single quotes so PowerShell does not expand $HOME
cmd /c 'dir /b & echo done'                            # cmd built-ins
pwsh -NoProfile -Command "Get-Date"                    # PowerShell 7 from 5.1
powershell -NoProfile -ExecutionPolicy Bypass -File .\script.ps1     # Bypass only for a script the user approved
powershell -EncodedCommand <base64-of-utf16le-command> # avoids all quoting issues; the content is invisible, so show the decoded text to the user
```
