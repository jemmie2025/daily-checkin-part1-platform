from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "n8n" / "workflows"
CODE = ROOT / "n8n" / "code"
SPEC = importlib.util.spec_from_file_location("render_n8n", ROOT / "scripts" / "render_n8n.py")
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def workflows() -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.glob("*.json"))
    }


class WorkflowPackageTests(unittest.TestCase):
    def test_six_canonical_workflows_render_deterministically(self) -> None:
        expected = renderer.render()
        actual = {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.json")}
        self.assertEqual(len(expected), 6)
        self.assertEqual(actual, expected)

    def test_every_workflow_imports_inactive_with_unique_nodes(self) -> None:
        for filename, workflow in workflows().items():
            with self.subTest(filename=filename):
                self.assertFalse(workflow["active"])
                self.assertEqual(workflow["settings"]["executionOrder"], "v1")
                names = [node["name"] for node in workflow["nodes"]]
                identifiers = [node["id"] for node in workflow["nodes"]]
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_generated_workflows_have_no_unresolved_code_markers(self) -> None:
        for path in WORKFLOWS.glob("*.json"):
            self.assertNotIn("@code:", path.read_text(encoding="utf-8"), path.name)

    def test_code_nodes_allow_only_crypto_builtin(self) -> None:
        requires: set[str] = set()
        for path in CODE.glob("*.js"):
            requires.update(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", path.read_text(encoding="utf-8")))
        self.assertEqual(requires, {"crypto"})

    def test_workflows_contain_no_exported_credential_objects(self) -> None:
        for filename, workflow in workflows().items():
            with self.subTest(filename=filename):
                self.assertFalse(any("credentials" in node for node in workflow["nodes"]))
                serialized = json.dumps(workflow)
                self.assertNotRegex(serialized, r"(?i)bearer\s+eyj[a-z0-9_-]+")
                self.assertNotRegex(serialized, r"(?i)(?:password|api_key)=[^&\s\"]+")

    def test_every_downstream_http_write_has_bounded_retry(self) -> None:
        writes = []
        for workflow in workflows().values():
            for node in workflow["nodes"]:
                if node["type"] != "n8n-nodes-base.httpRequest":
                    continue
                method = node["parameters"].get("method", "GET")
                if method in {"POST", "PATCH", "PUT"}:
                    writes.append(node)
        self.assertGreaterEqual(len(writes), 10)
        for node in writes:
            self.assertTrue(node.get("retryOnFail"), node["name"])
            self.assertEqual(node.get("maxTries"), 3, node["name"])
            self.assertLessEqual(node.get("waitBetweenTries", 0), 4000, node["name"])

    def test_compliance_workflow_has_all_required_actions(self) -> None:
        workflow = workflows()["checkin-compliance-v1.json"]
        names = {node["name"] for node in workflow["nodes"]}
        self.assertTrue(
            {
                "Send Nudge",
                "Create PI-6 Violation",
                "Resolve PI-6 Violation",
                "Send Escalation Digest",
                "Commit Action ID",
            } <= names
        )
        body = json.dumps(workflow)
        self.assertNotIn("BASEROW_CHECKINS_TOKEN", body)
        self.assertNotIn("BASEROW_DLQ_TOKEN", body)

    def test_dlq_capture_uses_error_trigger_and_verbatim_dm(self) -> None:
        workflow = workflows()["checkin-dlq-capture-v1.json"]
        types = [node["type"] for node in workflow["nodes"]]
        self.assertEqual(types.count("n8n-nodes-base.errorTrigger"), 1)
        self.assertEqual(types.count("n8n-nodes-base.scheduleTrigger"), 1)
        names = {node["name"] for node in workflow["nodes"]}
        self.assertTrue(
            {
                "Fetch Failed Submit Execution",
                "List Failed Submit Executions",
                "Extract Failure Context",
                "Persist DM Receipt",
            } <= names
        )
        code = next(node for node in workflow["nodes"] if node["name"] == "Build DLQ Record")["parameters"]["jsCode"]
        self.assertIn("raw_submission: raw", code)
        self.assertIn("three attempts", code)
        serialized = json.dumps(workflow)
        self.assertIn("CHECKIN_N8N_EXECUTION_READ_TOKEN", serialized)
        self.assertIn("includeData", serialized)
        guard = next(node for node in workflow["nodes"] if node["name"] == "Guard Duplicate DM")
        self.assertIn("dm_notified_at", guard["parameters"]["jsCode"])
        self.assertNotIn("notified_dlq_ids", guard["parameters"]["jsCode"])

    def test_replay_passes_original_idempotency_and_correlation(self) -> None:
        workflow = workflows()["checkin-dlq-replay-v1.json"]
        node = next(node for node in workflow["nodes"] if node["name"] == "Execute Idempotent Replay")
        serialized = json.dumps(node)
        self.assertIn("Idempotency-Key", serialized)
        self.assertIn("replay_key", serialized)
        self.assertIn("X-Correlation-ID", serialized)
        self.assertIn("raw_submission", serialized)
        self.assertIn("Plan Stage-Safe Replay", serialized)
        fetch = next(node for node in workflow["nodes"] if node["name"] == "Fetch Replay Candidates")
        self.assertIn("BASEROW_DLQ_REPLAY_VIEW_ID", json.dumps(fetch))
        self.assertIn("size=100", json.dumps(fetch))

    def test_ingestion_has_contract_auth_duplicate_and_conflict_responses(self) -> None:
        workflow = workflows()["checkin-event-ingestion-v1.json"]
        response_codes = {
            node["parameters"].get("options", {}).get("responseCode")
            for node in workflow["nodes"]
            if node["type"] == "n8n-nodes-base.respondToWebhook"
        }
        self.assertEqual(response_codes, {200, 202, 400, 401, 409})
        body = json.dumps(workflow)
        self.assertIn("insert_deduplication_token", body)
        self.assertIn("payload_hash", body)
        validator = next(node for node in workflow["nodes"] if node["name"] == "Validate and Flatten Event")
        validation_code = validator["parameters"]["jsCode"]
        self.assertIn("timingSafeEqual", validation_code)
        self.assertIn("validDate", validation_code)
        self.assertIn("submitted outcome missing", validation_code)
        lookup = next(node for node in workflow["nodes"] if node["name"] == "Check Event ID")
        self.assertIn("FORMAT JSON", json.dumps(lookup))

    def test_success_execution_bodies_are_not_retained(self) -> None:
        for filename, workflow in workflows().items():
            with self.subTest(filename=filename):
                self.assertEqual(workflow["settings"]["saveDataSuccessExecution"], "none")
                self.assertEqual(workflow["settings"]["saveDataErrorExecution"], "all")


if __name__ == "__main__":
    unittest.main()
