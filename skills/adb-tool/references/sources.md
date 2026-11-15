# Sources

Checked on 2026-11-15 (platform-tools 37.0.1 released; 37.0.3 canary). Re-read the page before relying on a version-specific claim; `url-to-skill` can refresh a page into notes.

| Topic | Official page |
|---|---|
| adb overview, how it works, wireless debugging, install, forward, push/pull, shell, `am`, `pm`, `dpm`, screencap, screenrecord, testharness, sqlite, USB and mDNS backends, burst mode | https://developer.android.com/tools/adb |
| adb manual page (every command and environment variable) | https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md |
| logcat options, filters, formats, buffers | https://developer.android.com/tools/logcat |
| Bug reports | https://developer.android.com/studio/debug/bug-report |
| Set up a device, USB drivers, udev, wireless pairing, Connection Assistant | https://developer.android.com/studio/run/device |
| Platform-Tools downloads and release notes | https://developer.android.com/tools/releases/platform-tools |
| OEM USB drivers (Windows) | https://developer.android.com/studio/run/oem-usb |
| Android CLI (`android install`, `run`, `screen capture`) | https://developer.android.com/tools/agents |

## What comes from where

- Catalog entries with source `doc`: the adb page or the adb manual page above.
- Source `notes`: platform-tools release notes (for example `adb pair --qr` and the `--fastdeploy` deprecation are in 37.0.3, a canary; `ADB_MDNS_OPENSCREEN` has no effect since 37.0.1).
- Source `device`: tools that run on the device (`dumpsys`, `getprop`, `settings`, `wm`, `input`, `svc`, `monkey`, `content`, `cmd`, toybox utilities). Their options are not on the pages above and change between Android versions: confirm with `adb shell <tool> --help` before relying on a flag.
- Where the pages disagree, the newer release notes win: the adb page still tells you to set `ADB_MDNS_OPENSCREEN=0` for an obsolete mDNS backend, while the 37.0.1 notes say the openscreen backend was deleted.

## Version facts used by the script

- 37.0.0 or newer: default mDNS backend `libadbmdns`, `adb server-status` shows mDNS state; ADB Wi-Fi 2.0 also needs Android 17 on the device (`mdns_service_version: "2.0"`).
- Wireless debugging (pairing) needs Android 11 on phones, Android 13 on TV and Wear OS.
- `adb server-status` exists in current Platform-Tools only; the script falls back to a hint on older ones.
