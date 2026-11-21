@echo off
rem skill-hub one-shot installer for Windows.
rem Checks the preconditions, shows which agents it found, then runs tools\install.py.
rem
rem   install.bat                      default (--setup): every skill + the skill-hub MCP server, every
rem                                    detected agent, for your user (asks y/n first)
rem   install.bat --check              only check the preconditions, change nothing
rem   install.bat --yes                default install without the y/n question
rem   install.bat --dry-run            show the plan, change nothing
rem   install.bat <installer options>  any other options go straight to tools\install.py, e.g.
rem                                    install.bat --agent claude-code --plugin hub-tools,gradle-tools --global
rem
rem Needs: Python 3.8+. From a clone it uses tools\install.py; otherwise it downloads the installer of
rem the latest release (it installs that release, checksum-verified). Set SKILLHUB_REF=main for the latest
rem development version or SKILLHUB_REF=v1.3.0 for a given one, SKILLHUB_REPO=owner/name for a fork.
rem Exit codes: 0 done, 1 error, 2 bad options, 3 partly done (see the summary), 4 cancelled.
rem Nothing is written without your yes (or --yes).
setlocal EnableExtensions

set "HUB=%~dp0"
set "CHECK_ONLY=0"
set "ARGS="
set "TMPD="

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--check" goto parse_check
set ARGS=%ARGS% %1
shift
goto parse
:parse_check
set "CHECK_ONLY=1"
shift
goto parse
:parsed

echo.
echo skill-hub installer: checking preconditions
echo ----------------------------------------------

rem 1. Python 3.8+ (a Microsoft Store stub named python.exe fails the version test and is skipped)
set "PY="
for %%C in (py python python3) do if not defined PY call :try_python %%C
if defined PY goto have_python
echo [FAIL] Python 3.8 or newer was not found.
echo        Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH")
echo        or run: winget install Python.Python.3.12
echo        then open a new terminal and run this file again.
exit /b 1
:have_python
for /f "delims=" %%V in ('%PY% --version 2^>^&1') do echo [ OK ] %%V  (command: %PY%)

rem 2. a folder the installer can write to (user skill folders live under your profile)
set "PROBE=%USERPROFILE%\.skillhub-write-test.tmp"
(echo test>"%PROBE%") 2>nul
if exist "%PROBE%" goto home_ok
echo [FAIL] Cannot write to %USERPROFILE%. Use a project install instead, for example:
echo        install.bat --agent claude-code --all --project .
goto fail
:home_ok
del "%PROBE%" >nul 2>nul
echo [ OK ] Home folder is writable: %USERPROFILE%

rem 3. the installer script: local clone first, otherwise download it
set "INSTALLER=%HUB%tools\install.py"
if exist "%INSTALLER%" goto have_installer
set "REPO=%SKILLHUB_REPO%"
if not defined REPO set "REPO=NILANJAN-01/skill-hub"
set "URL=https://github.com/%REPO%/releases/latest/download/install.py"
set "WHAT=the latest release"
if defined SKILLHUB_REF set "URL=https://raw.githubusercontent.com/%REPO%/%SKILLHUB_REF%/tools/install.py"
if defined SKILLHUB_REF set "WHAT=%SKILLHUB_REF%"
set "TMPD=%TEMP%\skillhub-%RANDOM%%RANDOM%"
mkdir "%TMPD%" >nul 2>nul
set "INSTALLER=%TMPD%\install.py"
echo [ .. ] No clone here; downloading the installer of %WHAT% from github.com/%REPO%
rem TLS 1.2 explicitly: older Windows PowerShell 5.1 does not offer it by default, and GitHub requires it.
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072; Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%INSTALLER%' } catch { Write-Host $_.Exception.Message; exit 1 }"
if not errorlevel 1 goto downloaded
echo [FAIL] Could not download the installer. Check your internet, proxy or VPN,
echo        or clone the repo and run install.bat from it.
goto fail
:downloaded
echo [ OK ] Downloaded the installer
goto have_installer_done
:have_installer
echo [ OK ] Found the hub clone: %HUB%
:have_installer_done

rem 4. which agents are installed
echo.
echo Agents found on this computer:
"%PY%" -I "%INSTALLER%" --detect
if not errorlevel 1 goto detected
echo [FAIL] The installer could not run. See the message above.
goto fail
:detected

if not "%CHECK_ONLY%"=="1" goto do_install
echo.
echo All preconditions are met. Nothing was changed (--check).
goto done_ok

rem 5. install (the installer shows the plan and asks before writing, unless --yes is given)
:do_install
if "%ARGS%"=="" goto default_args
set "REST=%ARGS: --yes=%"
set "REST=%REST: -y=%"
set "REST=%REST: --dry-run=%"
if not "%REST%"=="" goto run_install
:default_args
set ARGS=--setup%ARGS%
:run_install
echo.
echo Running: %PY% tools\install.py %ARGS%
echo.
"%PY%" -I "%INSTALLER%" %ARGS%
set "RC=%ERRORLEVEL%"
if defined TMPD rmdir /s /q "%TMPD%" >nul 2>nul
exit /b %RC%

:fail
if defined TMPD rmdir /s /q "%TMPD%" >nul 2>nul
exit /b 1

:done_ok
if defined TMPD rmdir /s /q "%TMPD%" >nul 2>nul
exit /b 0

:try_python
%1 -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul && set "PY=%1"
exit /b 0
