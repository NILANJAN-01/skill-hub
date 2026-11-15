# Wireless debugging

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (adb page: Connect over Wi-Fi).

## Android 11+ (pairing)

Prerequisites: workstation and device on the same Wi-Fi; Android 11 (API 30) on phones, Android 13 (API 33) on TV and Wear OS; latest Platform-Tools. (Wear OS 11 uses a different flow: see the Wear OS debugging guide.)

1. Developer options > **Wireless debugging** on. Allow it on the network. "Always allow on this network" makes it a trusted network that auto-allows later.
2. Tap **Pair device with pairing code**. Note IP address, **pairing port** and the six-digit code.
3. `adb pair IP:PAIRPORT` and enter the code (or `adb pair IP:PAIRPORT CODE`). Script: `adb_tool.py wifi pair IP:PAIRPORT --code CODE`.
4. The main Wireless debugging screen shows another **IP address and port**. `adb connect IP:PORT`. Script: `adb_tool.py wifi connect IP:PORT`.
5. `adb devices` lists `IP:PORT  device`.

Pair once. The device stays paired until you Forget it (Wireless debugging > Paired devices) or tap **Revoke USB debugging authorizations**. Android Studio can pair with a QR code (Pair devices over Wi-Fi). Quick settings developer tiles switch wireless debugging on and off.

## ADB Wi-Fi 2.0 (Android 17 + adb 37.0.0)

The device connects automatically when it joins a trusted wireless-debugging network. Check support: `adb mdns track-services --proto-text`; a service block with `mdns_service_version: "2.0"` or higher means the device supports it. Pairing by QR code in the terminal (`adb pair --qr`) is in platform-tools 37.0.3 (canary at the time of checking).

## Verify your workstation

`adb server-status` should show:
- `version: "37.0.0"` or higher,
- `mdns_enabled: true` (if false: set `ADB_MDNS=1`, `adb kill-server`, `adb start-server`),
- an mDNS backend of `LIBADBMDNS` (since 37.0.1 it is the only backend; the old `ADB_MDNS_OPENSCREEN=0` advice on the adb page is obsolete).

Check the network supports mDNS: with wireless debugging on, `adb mdns track-services --proto-text`. Empty output means the network blocks mDNS (guest Wi-Fi, some routers, VPNs): connect manually with the IP and port.

## Android 10 and lower, or over an initial USB connection (`adb tcpip`)

1. Device and computer on the same Wi-Fi (some access points block adb).
2. Connect by USB. `adb tcpip 5555`.
3. Unplug. Find the device IP (Settings > About phone > Status, or `adb shell ip -o -4 addr show wlan0` before unplugging).
4. `adb connect IP:5555`. `adb devices` shows `IP:5555 device`.
5. Back to USB: `adb usb`. If the link drops: same network? `adb connect` again; else `adb kill-server` and start over.

Script: `adb_tool.py wifi tcpip` does steps 2 to 4 (device connected by USB). `adb tcpip` is **unencrypted**: use trusted networks only. Android Studio's device mirroring over a tcpip connection sends screen data unencrypted too.

## Disconnect

`adb disconnect IP:PORT`, or `adb disconnect` for all. Script: `wifi disconnect [IP:PORT]`.

## Report a wireless bug

Attach device logs (bug report), and adb logs: set `ADB_TRACE=all`, `adb kill-server`, `adb start-server`, reproduce, attach the file at `log_absolute_path` from `adb server-status`.
