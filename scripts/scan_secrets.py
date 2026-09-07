#!/usr/bin/env python3
"""Fail CI when likely credential material appears in the tree or Git history."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = {".git", "build", "__pycache__", ".venv", "venv"}
TEXT_SUFFIXES = {".hcl", ".json", ".md", ".py", ".txt", ".yaml", ".yml", ".env", ".sh", ".js"}
TEXT_NAMES = {"Makefile", "VERSION", ".env.example", ".gitignore", ".editorconfig"}
KNOWN_SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}
ASSIGNMENT = re.compile(
    r"(?i)(?:password|passwd|token|secret|signature|api[_-]?key|auth[_-]?header)"
    r"[A-Za-z0-9_.-]*\s*[:=]\s*[\"']?([^\s\"']{12,})"
)
SAFE_VALUE_MARKERS = (
    "$ENV://",
    "__ENV.",
    "commandToken",
    "$secret://",
    "${",
    "$(",
    "{{",
    "example",
    "placeholder",
    "redacted",
    "<",
    "kv/",
    "dialog-shared",
    "event-shared",
    "os.environ",
    ".get(",
    "call(",
)


def scan_text(content: str, label: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for name, pattern in KNOWN_SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append(f"{label}:{line_number}: possible {name}")
        assignment = ASSIGNMENT.search(line)
        if assignment:
            candidate = assignment.group(1).rstrip(",;)}]")
            lowered = candidate.lower()
            lowered_line = line.lower()
            if not any(marker.lower() in lowered_line or marker.lower() in lowered for marker in SAFE_VALUE_MARKERS):
                findings.append(f"{label}:{line_number}: possible assigned credential")
    return findings


def scan_tree(root: Path) -> tuple[int, list[str]]:
    checked = 0
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        if not path.is_file() or (path.name not in TEXT_NAMES and path.suffix not in TEXT_SUFFIXES):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        checked += 1
        findings.extend(scan_text(content, str(path.relative_to(root))))
    return checked, findings


def scan_history(root: Path) -> tuple[bool, list[str]]:
    if not (root / ".git").exists():
        return False, []
    process = subprocess.run(
        ["git", "log", "--all", "-p", "--no-ext-diff", "--no-color"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError("unable to read Git history")
    return True, scan_text(process.stdout, "git-history")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()

    checked, findings = scan_tree(args.root)
    history_scanned = False
    if args.history:
        try:
            history_scanned, history_findings = scan_history(args.root)
        except RuntimeError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        findings.extend(history_findings)

    if findings:
        for finding in findings:
            print(f"FAIL: {finding}", file=sys.stderr)
        print("FAIL: possible secret material found; output intentionally omits candidate values", file=sys.stderr)
        return 1
    print(f"PASS: {checked} working-tree text files contain no recognized credential material")
    if args.history:
        print("PASS: Git history contains no recognized credential material" if history_scanned else "SKIP: no Git history present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
