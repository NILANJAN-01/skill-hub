# Apps and packages (`adb install`, `pm`)

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (adb page, Call package manager). Run on a device as `adb shell pm <command>`.

## Install and uninstall (host side)

```
adb install [-lrtsdg] [--instant] [--abi ABI] [--streaming|--no-streaming] path.apk
adb install-multiple [-lrtsdpg] [--instant] a.apk b.apk ...     # split APKs (for example from Play Console)
adb install-multi-package [-lrtsdpg] a.apk b.apk ...             # several packages atomically
adb uninstall [-k] com.example.app                                # -k keeps data and cache
```

| Flag | Meaning |
|---|---|
| `-r` | Replace an existing app and keep its data |
| `-t` | Allow test APKs (needed for APKs built by a debug run in Android Studio / Gradle test APKs) |
| `-d` | Allow version-code downgrade (debuggable apps) |
| `-g` | Grant all runtime permissions in the manifest |
| `-l` / `-s` | Forward lock / install on SD card |
| `-p` | Partial install (install-multiple) |
| `--instant` | Install as an instant app |
| `--abi ABI` | Force an ABI |
| `--fastdeploy` | Deprecated in platform-tools 37.0.3 in favour of `android install` (Android CLI) |

Android Studio installs apps itself; use adb for scripts, CI and devices without Studio.

## Install errors

| Error | Meaning and fix |
|---|---|
| `INSTALL_FAILED_ALREADY_EXISTS` | Use `-r` |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Signature differs from the installed app: uninstall first (data is lost; use `uninstall -k` if you want to keep it, though a different signature usually cannot reuse it) |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | Installed version is newer: `-d` or uninstall |
| `INSTALL_FAILED_OLDER_SDK` | Device API level below `minSdk` |
| `INSTALL_FAILED_INSUFFICIENT_STORAGE` | Free space |
| `INSTALL_FAILED_TEST_ONLY` | Add `-t` |
| `INSTALL_FAILED_NO_MATCHING_ABIS` | No native libs for the device CPU |
| `INSTALL_FAILED_USER_RESTRICTED` | Device blocks USB installs; allow in Developer options |
| `INSTALL_PARSE_FAILED_NO_CERTIFICATES` | APK is unsigned |
| `INSTALL_FAILED_MISSING_SHARED_LIBRARY` | Needs a shared library the device lacks |

## `pm` queries (read-only)

| Command | Use |
|---|---|
| `pm list packages [-f] [-d] [-e] [-s] [-3] [-i] [-u] [--user ID] [filter]` | `-3` third-party, `-s` system, `-d` disabled, `-e` enabled, `-f` file, `-i` installer, `-u` include uninstalled |
| `pm path PACKAGE` | APK location(s) |
| `pm list permissions [-g] [-f] [-s] [-d] [-u] [group]` | `-d` dangerous only |
| `pm list permission-groups`, `list features`, `list libraries`, `list users`, `list instrumentation [-f] [target]` | Device capabilities, users, test packages |
| `pm get-install-location`, `pm get-max-users` | Settings and limits |
| `pm get-app-links [--user ID] [package]` | Domain verification state: none, verified, approved, denied, migrated, restored, legacy_failure, system_configured, >=1024 custom |
| `pm get-app-link-owners --user ID [--package P] domains` | Who handles a domain, low to high priority |

## `pm` changes

| Command | Effect |
|---|---|
| `pm grant PACKAGE PERMISSION` / `pm revoke ...` | Runtime permission (Android 6+: any permission declared in the manifest) |
| `pm clear PACKAGE` | **Deletes all app data** |
| `pm uninstall [-k] [--user ID] [--versionCode CODE] PACKAGE` | **Removes the app** |
| `pm enable|disable|disable-user [--user ID] PACKAGE_OR_COMPONENT` | Component is `package/class` |
| `pm install [-r -t -d -g -i INSTALLER --user ID --install-location 0|1|2 --incremental ...] path` | Install a file already on the device |
| `pm set-install-location 0|1|2` | 0 auto, 1 internal, 2 external. Debug only: can break apps |
| `pm set-permission-enforced PERMISSION true|false`, `pm trim-caches SIZE` | Rarely needed |
| `pm create-user NAME`, `pm remove-user ID` | **remove-user deletes the user's data** |
| `pm reset-app-links`, `verify-app-links [--re-verify]`, `set-app-links`, `set-app-links-user-selection`, `set-app-links-allowed` | Test Android App Links verification |

`--incremental` needs an APK signed with scheme v4 (`.idsig` next to the APK) and a supporting device; `--no-incremental` turns it off.

## Test devices

`adb shell cmd testharness enable` factory-resets an Android 10+ test device into a test-friendly state (no setup wizard, lock screen off, auto-update off) and keeps the adb key: **it erases the device**. Only on dedicated test devices and only when asked.
