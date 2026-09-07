#!/usr/bin/env python3
"""Build the deterministic one-folder WSL release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from release_manifest import MANIFEST, ROOT, included_files


FIXED_TIME = (2026, 9, 7, 0, 0, 0)
ARCHIVE_ROOT = "daily-checkin-part1-platform"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_paths = {item["path"] for item in manifest["files"]}
    actual_paths = {path.relative_to(ROOT).as_posix() for path in included_files()}
    if expected_paths != actual_paths:
        parser.error("release manifest does not match the release file set")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    files = [*included_files(), MANIFEST]
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix()):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{relative}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o100755 if path.suffix in {".py", ".sh"} else 0o100644
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"PASS: wrote {args.output} ({args.output.stat().st_size} bytes)")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
