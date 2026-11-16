---
name: adb-connect
description: "Install and set up adb (Android Platform-Tools), enable USB debugging, install USB drivers, pair and connect over Wi-Fi (wireless debugging, adb tcpip), and fix adb connection problems: no devices, unauthorized, offline, no permissions, more than one device, daemon or port 5037 errors, mDNS not working. Use when adb is missing, adb devices shows nothing or the wrong state, or the user wants to connect a phone or emulator wirelessly."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ and the script from the adb-tool skill (install the adb-tools bundle). Needs adb on PATH or in the Android SDK platform-tools folder; the script says how to install it if missing.
metadata:
  title: "adb setup, USB and wireless connection, troubleshooting"
  category: adb-tools
---

# adb: setup and connection

Goal: `adb devices` shows the device as `device` and commands work. The script `skills/adb-tool/scripts/adb_tool.py` (from the `adb-tool` skill) checks each step and prints the fix.

## When to use

- "adb not found", "install adb", "set up adb on Windows/Mac/Linux".
- `adb devices` is empty, or shows `unauthorized`, `offline`, `no permissions`, `recovery`, `bootloader`.
- "more than one device/emulator", "cannot connect to daemon", "adb server version doesn't match", port 5037 in use.
- Connect over Wi-Fi: pair, `adb connect`, `adb tcpip`, "mDNS", "wireless debugging".

## When NOT to use

- Anything after the device is connected: installing apps, files, screenshots (`adb-device-control`), logs and bug reports (`adb-debug`), a Gradle build failing (`gradle-android`).

## Safety rules for the agent

- Diagnosis is read-only. Do not reset authorizations, uninstall drivers or edit system files without asking.
- `adb tcpip` and `adb -a` are unencrypted and open the device or server to the network; use trusted networks and run `adb usb` afterwards.
- Pairing codes are secrets: use them once, never write them to files or logs.
- Do not disable or script around the "Allow USB debugging?" dialog; the user must accept it on the unlocked device.

## Procedures

1. **Check everything at once.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py doctor
   ```
   It finds adb, prints the version and `server-status` (mDNS), and lists devices with one fix per bad state. Exit 1 means something needs fixing.
2. **adb missing.** Install Android SDK Platform-Tools (Android Studio SDK Manager, `sdkmanager "platform-tools"`, or the zip from the official page) and add its folder to PATH or set `ANDROID_HOME`. Details: [references/install-and-usb.md](references/install-and-usb.md).
3. **USB device not listed.** On the device: Developer options on, USB debugging on, screen unlocked, USB mode not "charging only". Use a data cable and another port. Windows: install the OEM USB driver. Linux: `plugdev` group and udev rules. Then `adb kill-server` and `adb devices`.
4. **`unauthorized`.** Unlock the device and accept the RSA key dialog ("Allow USB debugging", tick "Always allow"). No dialog: Developer options > Revoke USB debugging authorizations, replug, `adb kill-server`.
5. **`offline`.** Replug, toggle USB debugging, `adb reconnect offline`, update Platform-Tools.
6. **Wireless (Android 11+).** Same Wi-Fi network; update Platform-Tools. On the device: Developer options > Wireless debugging > Pair device with pairing code (note IP:port and code). Then:
   ```bash
   python skills/adb-tool/scripts/adb_tool.py wifi pair 192.168.1.9:37123 --code 123456
   python skills/adb-tool/scripts/adb_tool.py wifi connect 192.168.1.9:40000   # port from the main Wireless debugging screen
   python skills/adb-tool/scripts/adb_tool.py wifi status                      # mDNS services
   ```
   Pair once; the device stays paired until you forget it. Android 10 and lower, or a network without mDNS: connect the USB cable once and run `wifi tcpip`, which does `adb tcpip 5555` then `adb connect IP:5555`. Details and mDNS checks: [references/wireless-debugging.md](references/wireless-debugging.md).
7. **Several devices.** Pass `--serial SERIAL` to every command (or set `ANDROID_SERIAL`); `-d` selects the one USB device, `-e` the one emulator.
8. **Verify.** `adb_tool.py devices` shows `device`, then `adb_tool.py info` prints the model and Android version.

## Troubleshooting

| Symptom / message | Cause and fix |
|---|---|
| `adb: command not found` | Not installed or not on PATH: step 2 |
| empty list | Cable, USB debugging, driver, unlocked screen: step 3 |
| `unauthorized` | Accept the RSA dialog: step 4 |
| `offline` | Step 5 |
| `no permissions (user in plugdev group; are your udev rules wrong?)` | Linux: `sudo usermod -aG plugdev $LOGNAME`, log out and in, `apt-get install android-sdk-platform-tools-common` |
| `more than one device/emulator` | Step 7 |
| `cannot connect to daemon at tcp:5037` / `daemon not running` | Another adb or a firewall holds port 5037: `adb kill-server`, close other adb users (older Android Studio, Genymotion), `adb start-server` |
| `adb server version (X) doesn't match this client (Y); killing...` | Two different adb copies; use one (check `where adb` / `which -a adb`) |
| emulator missing from `adb devices` | Start the adb server before the emulator, or `adb kill-server` then `adb start-server` after it started |
| `failed to connect to 'IP:PORT'` / `Connection refused` | Wrong port (use the Wireless debugging port, not the pairing port), different networks, VPN, firewall; re-pair |
| pairing fails | Pairing code expires; reopen the pairing dialog and retry with the new code and port |
| `mdns_enabled: false` | Set `ADB_MDNS=1`, then `adb kill-server` and `adb start-server` |
| `adb mdns track-services` prints nothing | The network blocks mDNS; connect manually with `wifi connect IP:PORT` |
| Redmi/Poco phones on Android 12 | Also enable "USB debugging (Security settings)" and restart the device |

For a bug report to the Android team: set `ADB_TRACE=all`, `adb kill-server`, `adb start-server`, reproduce, then attach the file named by `log_absolute_path` in `adb server-status`.

## References

- [references/install-and-usb.md](references/install-and-usb.md): install Platform-Tools, enable USB debugging, Windows drivers, Linux udev
- [references/wireless-debugging.md](references/wireless-debugging.md): pairing, tcpip, mDNS, ADB Wi-Fi 2.0
- [references/connection-troubleshooting.md](references/connection-troubleshooting.md): device states and a decision tree
