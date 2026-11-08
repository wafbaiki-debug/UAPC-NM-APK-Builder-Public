"""Verify the built artifact is a genuine, structurally valid Android APK."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

MIN_APK_BYTES = 4096
REQUIRED_ENTRIES = {"AndroidManifest.xml", "classes.dex"}


def verify_apk(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ValueError("APK tidak ditemui")
    size = path.stat().st_size
    if size < MIN_APK_BYTES:
        raise ValueError(f"APK terlalu kecil: {size} bait; minimum {MIN_APK_BYTES}")
    try:
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("APK ZIP rosak")
            filenames = set(archive.namelist())
            if not REQUIRED_ENTRIES.issubset(filenames):
                raise ValueError("APK tidak mengandungi manifest dan classes.dex")
    except BadZipFile as exception:
        raise ValueError("Bukan fail APK ZIP yang sah") from exception
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"apk": path.name, "bytes": size, "sha256": digest,
            "manifest_verified": True, "dex_verified": True,
            "android_install_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk")
    parser.add_argument("--output", default="output/build-report.json")
    args = parser.parse_args()
    details = verify_apk(Path(args.apk))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(details))


if __name__ == "__main__":
    main()
