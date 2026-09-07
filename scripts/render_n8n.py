#!/usr/bin/env python3
"""Render importable n8n workflows from JSON templates and reviewed Code nodes."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "n8n" / "templates"
CODE_DIR = ROOT / "n8n" / "code"
CANONICAL_DIR = ROOT / "n8n" / "workflows"
MARKER_PREFIX = "@code:"


class WorkflowError(ValueError):
    """Raised when a workflow template is unsafe or structurally invalid."""


def _replace(value: Any) -> Any:
    if isinstance(value, list):
        return [_replace(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace(child) for key, child in value.items()}
    if isinstance(value, str) and value.startswith(MARKER_PREFIX):
        filename = value.removeprefix(MARKER_PREFIX)
        if not filename or Path(filename).name != filename:
            raise WorkflowError("invalid code marker")
        path = CODE_DIR / filename
        if not path.is_file():
            raise WorkflowError(f"missing n8n code file: {filename}")
        return path.read_text(encoding="utf-8").rstrip("\n")
    return value


def validate_workflow(workflow: dict[str, Any], filename: str) -> None:
    required = {"name", "nodes", "connections", "settings", "active", "versionId"}
    if not required <= set(workflow):
        raise WorkflowError(f"{filename} is missing workflow fields")
    if workflow["active"] is not False:
        raise WorkflowError(f"{filename} must be imported inactive")
    nodes = workflow["nodes"]
    names = [node.get("name") for node in nodes]
    identifiers = [node.get("id") for node in nodes]
    if len(names) != len(set(names)) or len(identifiers) != len(set(identifiers)):
        raise WorkflowError(f"{filename} has duplicate node names or IDs")
    for source, outputs in workflow["connections"].items():
        if source not in names:
            raise WorkflowError(f"{filename} connection has unknown source {source}")
        for groups in outputs.values():
            for group in groups:
                for target in group:
                    if target["node"] not in names:
                        raise WorkflowError(f"{filename} connection has unknown target {target['node']}")
    serialized = json.dumps(workflow).lower()
    forbidden = ("bearer eyj", "password=", "api_key=", "private_key")
    if any(item in serialized for item in forbidden):
        raise WorkflowError(f"{filename} contains credential-like material")


def render() -> dict[str, str]:
    rendered: dict[str, str] = {}
    for template in sorted(TEMPLATE_DIR.glob("*.template.json")):
        workflow = _replace(json.loads(template.read_text(encoding="utf-8")))
        output_name = template.name.replace(".template", "")
        validate_workflow(workflow, output_name)
        rendered[output_name] = json.dumps(workflow, indent=2, ensure_ascii=False) + "\n"
    if not rendered:
        raise WorkflowError("no n8n workflow templates found")
    return rendered


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=CANONICAL_DIR)
    args = parser.parse_args()
    try:
        rendered = render()
        if args.check:
            actual = {path.name: path.read_text(encoding="utf-8") for path in args.output_dir.glob("*.json")}
            if actual != rendered:
                missing = sorted(set(rendered) - set(actual))
                extra = sorted(set(actual) - set(rendered))
                stale = sorted(name for name in set(actual) & set(rendered) if actual[name] != rendered[name])
                raise WorkflowError(f"canonical workflows differ; missing={missing}, extra={extra}, stale={stale}")
        else:
            for name, content in rendered.items():
                write_atomic(args.output_dir / name, content)
    except (WorkflowError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    verb = "validated" if args.check else "rendered"
    print(f"PASS: {len(rendered)} n8n workflows {verb} deterministically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
