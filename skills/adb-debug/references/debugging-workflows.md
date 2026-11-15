# Debugging workflows

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (adb page: am, JDWP, ART profiles; bug report page). Device tools (`dumpsys`, `ps`, `top`) are marked (device).

## App crashed

1. Reproduce, then `adb_tool.py logcat --crash --out crash.txt` and `logcat --package PKG --level E --out app-errors.txt` (the package filter needs the app running; after a crash the pid is gone, so use `--buffer crash` or the time filter `--since`).
2. Look for `FATAL EXCEPTION`, the exception type, `Caused by:`, and the first frame in your package. Native crashes: `Fatal signal`, `backtrace:`, `Abort message`.
3. `android-logcat-analyzer` summarises crashes, ANRs and kills from the saved file.

## ANR (app not responding)

- Log lines `ANR in <package>` with the reason (input dispatching timed out, Broadcast of ..., executing service ...).
- `adb bugreport` contains thread traces. A live view: `adb shell am monitor` reports crashes and ANRs as they happen (`--gdb` starts gdbserv on crash/ANR).
- Typical causes: main-thread I/O, lock contention, long `onReceive`, deadlock.

## Startup time

`adb shell am start -W -S -n com.example.app/.MainActivity` prints `ThisTime`, `TotalTime` and `WaitTime` (cold start with `-S`).

## Memory

- Quick: `adb shell dumpsys meminfo com.example.app` (device).
- Heap dump: `adb shell am dumpheap com.example.app /data/local/tmp/app.hprof`, then `adb pull /data/local/tmp/app.hprof` and delete the device copy. `-n` dumps the native heap; `-b png` dumps bitmaps (API 35+); `am dumpbitmaps -p com.example.app -d png` writes `dumpbitmaps-<time>.zip` (API 36+). Convert `.hprof` with `hprof-conv` if the profiler needs it.
- Low-memory kills: `lmkd` and `am_kill` lines in logcat (`logcat -b events`).
- Android 17 memory limits: `am memory-limiter status`, `ignore UID|none|all`, `manual PID LIMIT|max|none`.

## Jank and rendering

`adb shell dumpsys gfxinfo com.example.app` (device) shows total and janky frames and percentiles; `reset` clears the counters; `framestats` gives per-frame timings. `am start --opengl-trace` traces GL calls. For deep profiling use Android Studio Profiler or Perfetto (systrace was removed from Platform-Tools).

## Battery

`adb shell dumpsys batterystats --reset`, use the app, then `adb shell dumpsys batterystats > batterystats.txt` (device). Simulate states with `dumpsys battery set ...` and `dumpsys battery reset`.

## Attaching a debugger or profiler

- Wait for a debugger at launch: `adb shell am set-debug-app -w com.example.app` then start the app; undo with `am clear-debug-app`. `am start -D` also starts in debug mode.
- Debuggable processes: `adb jdwp`; forward one: `adb forward tcp:8700 jdwp:PID`, then attach a JDWP debugger to `localhost:8700`.
- CPU profile: `am start --start-profiler FILE ...` (or `-P FILE` to stop at idle); or `am profile start PROCESS FILE` and `am profile stop PROCESS`.
- ART execution profiles: `adb shell cmd package dump-profiles PACKAGE`, pull `/data/misc/profman/PACKAGE.prof.txt` (root or emulator).

## Instrumented tests

```
adb shell am instrument -w -r -e class com.example.CartTest#totalIsSummed com.example.test/androidx.test.runner.AndroidJUnitRunner
```
`-w` waits and is required to see results; `-r` raw output; `-e package|class|size|log|debug`; `--no-window-animation` helps flakiness. Tests must be installed with `-t` when it is a test APK. Output ends with `OK (N tests)` or the failing test and stack.

## Network and app links

- `adb shell dumpsys connectivity`, `dumpsys wifi` (device).
- `adb shell pm get-app-links com.example.app` and `am start --debug-link` (Android 17+) diagnose why a link opens or does not open your app.
- Forward a dev server to the device: `adb reverse tcp:8081 tcp:8081`.

## Evidence to include in a report

Device model and Android version (`adb_tool.py info`), app version (`app-info`), the exact steps, log excerpt with timestamps and pid, and the bug report or snapshot folder if it is large.
