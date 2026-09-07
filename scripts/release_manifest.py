#!/usr/bin/env python3
"""Generate or verify the immutable, deterministic release file manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release" / "manifest.json"
METADATA = ROOT / "release" / "release-metadata.yaml"
IGNORED_PARTS = {".git", ".venv", "__pycache__", "build"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def included_files() -> list[Path]:
    result = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if (
            any(part in IGNORED_PARTS for part in relative.parts)
            or relative.parts[:2] == ("evidence", "private")
            or path.suffix in IGNORED_SUFFIXES
        ):
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(ROOT).as_posix())


def build_manifest() -> dict:
    metadata = yaml.safe_load(METADATA.read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if metadata["version"] != version:
        raise ValueError("release metadata and VERSION differ")
    files = []
    for path in included_files():
        content = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {
        "manifest_schema": 1,
        "version": version,
        "release_date": metadata["release_date"],
        "task": metadata["task"],
        "scope": metadata["scope"],
        "status": metadata["status"],
        "file_count": len(files),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        expected = build_manifest()
        if args.write:
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif not MANIFEST.is_file() or json.loads(MANIFEST.read_text(encoding="utf-8")) != expected:
            raise ValueError("release manifest is missing or stale; review changes before regenerating")
    except (ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    verb = "wrote" if args.write else "verified"
    print(f"PASS: {verb} release manifest for {expected['file_count']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
