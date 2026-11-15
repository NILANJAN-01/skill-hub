# dumpsys and bug reports

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (bug report page, adb page). `dumpsys` is a device tool: services and output change between Android versions, so list what the device has with `adb shell dumpsys -l`.

## Bug report

Capture:
- On the device: Developer options > **Take bug report**.
- Emulator: Extended controls > Bug report > Save report.
- adb: `adb bugreport [PATH]` (default `bugreport.zip` in the current folder; with several devices `adb -s SERIAL bugreport`). Takes minutes; keep the device unlocked.
- Older reports stay on the device in `/bugreports`: `adb shell ls /bugreports/`, then `adb pull /bugreports/<file>.zip`.

Contents of `bugreport-BUILD_ID-DATE.zip`:
- `bugreport-BUILD_ID-DATE.txt`: the main file: `dumpsys` output for system services, `dumpstate` error logs, and `logcat` (stack traces and app logs).
- `version.txt` (Android release letter), `systrace.txt` when enabled.
- `FS/`: files copied from the device (`/dirA/dirB/fileC` becomes `FS/dirA/dirB/fileC`).

Privacy: contains account names, installed apps, network info and logs. Share carefully. Crashes from real users: Google Play Console (crashes and ANRs, previous six months) and Firebase Crashlytics.

Read it with `android-logcat-analyzer` (accepts the zip) or search the `.txt` for `FATAL EXCEPTION`, `ANR in`, `Tombstone`, `beginning of crash`, `am_crash`, `am_anr`.

## dumpsys

```
adb shell dumpsys -l                 # list services
adb shell dumpsys <service> [args]   # dump one
```

Commonly useful services (confirm with `-l`):

| Service | Use |
|---|---|
| `meminfo [pkg|pid]` | Memory by process/app: PSS, Java heap, native heap, graphics; `-a` all details |
| `gfxinfo <pkg> [framestats]` | Frame rendering stats: total frames, janky frames, percentiles |
| `batterystats [--charged] [pkg]`, `battery` | Battery history and current state (`battery` shows level, status, plugged) |
| `activity [activities|top|processes|services|broadcasts|providers|intents]` | Activity stack, current top activity, processes, services |
| `package <pkg>` | Version, SDKs, permissions (granted or not), signatures, install times, components |
| `window [windows|displays]` | Windows, focus, display info |
| `display`, `power`, `alarm`, `jobscheduler`, `notification`, `usagestats` | Display, wakelocks, scheduled work, notifications |
| `connectivity`, `wifi`, `netstats`, `telephony.registry` | Network state |
| `cpuinfo` | Recent CPU usage per process |
| `diskstats` | Storage use |
| `dbinfo <pkg>` | SQLite usage of an app |

Examples:
```bash
adb shell dumpsys meminfo com.example.app
adb shell dumpsys gfxinfo com.example.app reset ; (use the app) ; adb shell dumpsys gfxinfo com.example.app     # frames since reset
adb shell dumpsys activity top | head -40                      # what is on screen
adb shell dumpsys package com.example.app | grep -A3 "granted=true"
adb shell dumpsys battery set level 15 ; adb shell dumpsys battery reset    # simulate low battery, then undo
```
`dumpsys` output can be large: write to a file with `adb_tool.py dumpsys <service> --out file`.

## Snapshot (script)

`adb_tool.py snapshot [--package PKG] [--out DIR]` collects properties, battery, activity top, processes, storage, display, meminfo, and for a package gfxinfo and package info, plus the last 2000 log lines, all read-only. Attach the folder to a ticket instead of a full bug report when a light-weight overview is enough.
