#!/usr/bin/env python3
"""A stand-in for gradlew / mvnw, used only by test_junit_report.py (no JDK or build tool needed).

It records its arguments in fake-build.log in the current folder and copies the report named by
FAKE_BUILD_REPORT into build/test-results/test/, like a Gradle test run. Exit code: FAKE_BUILD_EXIT (default 0).
"""
import os
import shutil
import sys

with open("fake-build.log", "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\n")
report = os.environ.get("FAKE_BUILD_REPORT")
if report:
    out = os.path.join("build", "test-results", "test")
    os.makedirs(out, exist_ok=True)
    shutil.copy(report, os.path.join(out, os.path.basename(report)))
sys.exit(int(os.environ.get("FAKE_BUILD_EXIT", "0")))
