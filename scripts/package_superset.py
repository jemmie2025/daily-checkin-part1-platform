#!/usr/bin/env python3
"""Build or verify the deterministic Superset native-import archive."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "analytics" / "superset"
DEFAULT_OUTPUT = ROOT / "analytics" / "superset-import" / "daily-checkin-compliance-v1.zip"
FIXED_TIME = (2026, 9, 4, 0, 0, 0)


def source_files() -> list[Path]:
    return sorted(
        path for path in SOURCE.rglob("*")
        if path.is_file() and "superset-import" not in path.parts
    )


def archive_bytes() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
        with zipfile.ZipFile(handle.name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in source_files():
                relative = path.relative_to(SOURCE).as_posix()
                info = zipfile.ZipInfo(relative, FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        return Path(handle.name).read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = archive_bytes()
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != expected:
            parser.error("Superset import archive is missing or stale")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(expected)
    digest = hashlib.sha256(expected).hexdigest()
    verb = "validated" if args.check else "wrote"
    print(f"PASS: {verb} Superset import archive ({len(expected)} bytes, sha256={digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
