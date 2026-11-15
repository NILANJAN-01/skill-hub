# Install adb and connect over USB

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (Platform-Tools, Set up a device, adb pages).

## Install Platform-Tools

`adb` ships in **Android SDK Platform-Tools** (`android_sdk/platform-tools/`). Platform-Tools is backward compatible: use the latest.

- With Android Studio: SDK Manager > SDK Tools > Android SDK Platform-Tools (Studio updates it for you).
- Command line: `sdkmanager "platform-tools"`.
- Standalone zip for Windows, Mac or Linux: https://developer.android.com/tools/releases/platform-tools (the links always point to the latest). Unzip it anywhere.

Then make `adb` findable:

| OS | PATH |
|---|---|
| Windows | System Properties > Environment Variables > Path > add the `platform-tools` folder (default `%LOCALAPPDATA%\Android\Sdk\platform-tools`); open a new terminal |
| macOS | `export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"` in the shell profile |
| Linux | `export PATH="$HOME/Android/Sdk/platform-tools:$PATH"` |

Check: `adb version` prints `Android Debug Bridge version 1.0.41` and `Version 37.x.x-...`. Keep only one adb on PATH: two copies fight over the server (`adb server version ... doesn't match`).

## Enable USB debugging on the device

1. Settings > About phone > tap **Build number** seven times (Developer options are hidden on Android 4.2+ until then).
2. Settings > Developer options > **USB debugging** on.
3. Connect with a data cable. The device shows **Allow USB debugging?** with an RSA fingerprint of the computer: accept (tick Always allow for a trusted computer). adb cannot run commands until this is accepted: it protects the device.
4. `adb devices` shows the serial with state `device`.

## System setup

- **macOS, ChromeOS:** nothing more.
- **Windows:** install the OEM USB driver for the phone (links: https://developer.android.com/studio/run/oem-usb). After installing, replug and run `adb kill-server`.
- **Ubuntu/Linux:**
  - `sudo usermod -aG plugdev $LOGNAME`, then log out and in; check with `id`.
  - Install udev rules: `apt-get install android-sdk-platform-tools-common` (community rules for Android devices).
  - If the state is `no permissions`, replug after both steps.

## Android Studio's Connection Assistant

Tools > Troubleshoot Device Connections walks through connecting over USB, enabling USB debugging and restarting the adb server.

## If the device still does not appear

- Try another cable (many are charge-only), another USB port (no hub), and another device or the emulator to tell cable from device.
- Set USB mode to File transfer (MTP) on the device.
- Emulator test: if Android Studio cannot connect to an emulator either, download the latest Platform-Tools.
- OEM-specific: ask the vendor; tell them the device does not connect to Android Studio with ADB.

## Windows tip for the script

`adb_tool.py doctor` also looks in `%LOCALAPPDATA%\Android\Sdk\platform-tools` and `ANDROID_HOME`/`ANDROID_SDK_ROOT`, so it can find adb even when PATH is not set.
