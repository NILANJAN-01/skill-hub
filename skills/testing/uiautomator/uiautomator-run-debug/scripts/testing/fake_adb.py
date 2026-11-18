#!/usr/bin/env python3
"""A stand-in for `adb`, used only by test_uia_run.py (no device needed).

FAKE_ADB_LOG      file that records each call (one line per call)
FAKE_ADB_DEVICES  comma list of serial:state (default "emulator-5554:device")
FAKE_ADB_OUTPUT   file printed for `shell am instrument ...`
"""
import os
import sys

args = sys.argv[1:]
log = os.environ.get("FAKE_ADB_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\n")
if args[:1] == ["-s"]:
    args = args[2:]
if args[:1] == ["version"]:
    print("Android Debug Bridge version 1.0.41\nVersion 37.0.1-fake")
elif args[:1] == ["devices"]:
    print("List of devices attached")
    for item in filter(None, os.environ.get("FAKE_ADB_DEVICES", "emulator-5554:device").split(",")):
        serial, state = item.split(":")
        print("%s\t%s" % (serial, state))
    print()
elif args[:1] == ["shell"] and len(args) > 1 and args[1].startswith("am instrument"):
    with open(os.environ["FAKE_ADB_OUTPUT"], encoding="utf-8") as fh:
        sys.stdout.write(fh.read())
elif args[:4] == ["shell", "pm", "list", "instrumentation"]:
    print("instrumentation:com.example.app.test/androidx.test.runner.AndroidJUnitRunner (target=com.example.app)")
elif args[:4] == ["shell", "settings", "get", "global"]:
    print("1.0")
elif args[:1] == ["logcat"]:
    print("11-18 08:00:00.000  1234  1234 E AndroidRuntime: FATAL EXCEPTION: main")
else:
    sys.stderr.write("fake adb: unsupported %r\n" % args)
    sys.exit(1)
