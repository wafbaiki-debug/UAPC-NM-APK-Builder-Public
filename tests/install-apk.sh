#!/usr/bin/env bash
set -euo pipefail

apk="$1"
report="$2"
aapt="$ANDROID_HOME/build-tools/35.0.0/aapt"
badging="$("$aapt" dump badging "$apk")"
package="$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" <<< "$badging")"
activity="$(sed -n "s/^launchable-activity: name='\([^']*\)'.*/\1/p" <<< "$badging")"
test -n "$package"
test -n "$activity"

adb install "$apk"
launch="$(adb shell am start -W -n "$package/$activity" | tr -d '\r')"
printf '%s\n' "$launch"
grep -qx 'Status: ok' <<< "$launch"
adb shell pidof "$package"
api="$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
test "$api" = 35

python3 - "$report" "$api" <<'PY'
import json
from pathlib import Path
import sys

report = Path(sys.argv[1])
evidence = json.loads(report.read_text())
evidence["android_emulator_install_verified"] = True
evidence["android_emulator_launch_verified"] = True
evidence["android_emulator_api"] = int(sys.argv[2])
report.write_text(json.dumps(evidence, indent=2) + "\n")
PY
