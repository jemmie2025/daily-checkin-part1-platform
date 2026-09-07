from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_hardening", ROOT / "scripts" / "validate_hardening.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class SloTests(unittest.TestCase):
    def test_hardening_validator_components_pass(self) -> None:
        self.assertEqual(validator.validate_slos()[0], 5)
        self.assertGreaterEqual(validator.validate_telemetry(), 9)
        self.assertEqual(validator.validate_test_plans(), 3)
        self.assertGreaterEqual(validator.validate_runbooks(), 8)
        self.assertEqual(validator.validate_superset_assets(), 6)

    def test_every_slo_has_an_owned_alert_and_indicator(self) -> None:
        slos = yaml.safe_load((ROOT / "config/slos.yaml").read_text(encoding="utf-8"))["slos"]
        alerts_doc = yaml.safe_load((ROOT / "observability/prometheus/checkin-alerts.yaml").read_text(encoding="utf-8"))
        records_doc = yaml.safe_load((ROOT / "observability/prometheus/checkin-recording-rules.yaml").read_text(encoding="utf-8"))
        alerts = {rule["alert"]: rule for group in alerts_doc["groups"] for rule in group["rules"]}
        records = {rule["record"] for group in records_doc["groups"] for rule in group["rules"]}
        for slo in slos:
            self.assertIn(slo["critical_alert"], alerts)
            self.assertIn(slo["indicator"], records)
            self.assertIn("owner", alerts[slo["critical_alert"]]["labels"])

    def test_submission_durability_is_exactly_one_hundred_percent(self) -> None:
        slos = yaml.safe_load((ROOT / "config/slos.yaml").read_text(encoding="utf-8"))["slos"]
        durability = next(item for item in slos if item["id"] == "submission_durability")
        self.assertEqual(durability["objective_percent"], 100.0)

    def test_high_cardinality_ids_are_not_metric_labels(self) -> None:
        contract = yaml.safe_load((ROOT / "observability/telemetry-contract.yaml").read_text(encoding="utf-8"))
        all_labels = {label for metric in contract["metrics"] for label in metric["labels"]}
        self.assertTrue({"correlation_id", "request_id", "execution_id"}.isdisjoint(all_labels))

    def test_forbidden_content_is_not_an_allowed_log_field(self) -> None:
        contract = yaml.safe_load((ROOT / "observability/telemetry-contract.yaml").read_text(encoding="utf-8"))
        self.assertTrue(set(contract["forbidden_labels_and_log_fields"]).isdisjoint(contract["allowed_log_fields"]))


class ReleaseControlTests(unittest.TestCase):
    def test_release_manifest_hashes_every_included_file(self) -> None:
        manifest = json.loads((ROOT / "release" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        listed = {item["path"]: item for item in manifest["files"]}
        actual = {
            path.relative_to(ROOT).as_posix(): path
            for path in validator.ROOT.rglob("*")
            if path.is_file()
            and path != ROOT / "release" / "manifest.json"
            and not any(part in {".git", ".venv", "__pycache__", "build"} for part in path.relative_to(ROOT).parts)
            and path.relative_to(ROOT).parts[:2] != ("evidence", "private")
            and path.suffix not in {".pyc", ".pyo"}
        }
        self.assertEqual(set(listed), set(actual))
        for relative, path in actual.items():
            content = path.read_bytes()
            self.assertEqual(listed[relative]["size_bytes"], len(content), relative)
            self.assertEqual(listed[relative]["sha256"], hashlib.sha256(content).hexdigest(), relative)

    def test_release_zip_is_deterministic_and_has_one_root(self) -> None:
        import zipfile

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            for target in (first, second):
                process = subprocess.run(
                    [sys.executable, "scripts/build_release.py", "--output", str(target)],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertTrue(names)
                self.assertTrue(all(name.startswith("daily-checkin-part1-platform/") for name in names))
                self.assertIn("daily-checkin-part1-platform/release/manifest.json", names)
                self.assertFalse(any("__pycache__" in name or name.startswith("daily-checkin-part1-platform/build/") for name in names))

    def test_github_actions_are_sha_pinned(self) -> None:
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        references = re.findall(r"uses:\s*([^\s]+)", workflow)
        self.assertGreaterEqual(len(references), 2)
        for reference in references:
            self.assertRegex(reference, r"@[0-9a-f]{40}$")

    def test_ci_has_read_only_repository_permissions(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"))
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertTrue(workflow["jobs"]["validate"]["steps"][0]["with"]["persist-credentials"] is False)

    def test_release_checklist_does_not_claim_live_evidence(self) -> None:
        checklist = (ROOT / "release/production-readiness-checklist.md").read_text(encoding="utf-8")
        environment = checklist.split("## Must be completed in company staging", maxsplit=1)[1]
        self.assertNotIn("- [x]", environment)

    def test_dashboard_layout_json_is_valid(self) -> None:
        dashboard = yaml.safe_load((ROOT / "analytics/superset/dashboards/Daily_Checkin_Compliance.yaml").read_text(encoding="utf-8"))
        layout = json.loads(dashboard["position"])
        self.assertEqual(layout["DASHBOARD_VERSION_KEY"], "v2")
        self.assertEqual(len([key for key in layout if key.startswith("CHART-")]), 6)

    def test_private_evidence_directory_is_ignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("evidence/private/", gitignore)


if __name__ == "__main__":
    unittest.main()
