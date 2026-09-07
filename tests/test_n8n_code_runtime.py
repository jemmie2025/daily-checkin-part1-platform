from __future__ import annotations

import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
HARNESS = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const envelope = JSON.parse(fs.readFileSync(0, 'utf8'));
const execute = new Function('$input', '$env', 'Buffer', 'require', snippet);
const output = execute(
  {first: () => ({json: envelope})},
  {CHECKIN_EVENT_INGEST_TOKEN: '<fixture-ingest-token>'},
  Buffer,
  require,
);
process.stdout.write(JSON.stringify(output));
"""


def event(name: str) -> dict:
    return json.loads(
        (ROOT / "contracts" / "events" / "examples" / f"{name}.json").read_text(encoding="utf-8")
    )


@unittest.skipUnless(NODE, "Node.js is required to execute n8n Code-node runtime tests")
class EventNormalizerRuntimeTests(unittest.TestCase):
    def execute(self, payload: dict, *, token: str = "<fixture-ingest-token>") -> dict:
        envelope = {
            "headers": {"authorization": f"Bearer {token}"} if token else {},
            "body": payload,
        }
        process = subprocess.run(
            [str(NODE), "-e", HARNESS, str(ROOT / "n8n" / "code" / "event-normalizer.js")],
            input=json.dumps(envelope),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)[0]["json"]

    def test_valid_submitted_event_is_flattened(self) -> None:
        result = self.execute(event("checkin.submitted"))
        self.assertEqual(result["disposition"], "valid")
        self.assertEqual(result["incoming"]["event_name"], "checkin.submitted")
        self.assertEqual(len(result["incoming"]["payload_hash"]), 64)

    def test_missing_or_wrong_token_is_unauthorized(self) -> None:
        self.assertEqual(self.execute(event("checkin.opened"), token="")["disposition"], "unauthorized")
        self.assertEqual(self.execute(event("checkin.opened"), token="wrong-token")["disposition"], "unauthorized")

    def test_invalid_calendar_date_is_rejected_before_clickhouse(self) -> None:
        payload = event("checkin.submitted")
        payload["cycle"]["cycle_date"] = "2026-02-30"
        self.assertEqual(self.execute(payload)["disposition"], "invalid")

    def test_submitted_event_requires_all_count_fields(self) -> None:
        payload = event("checkin.submitted")
        del payload["outcome"]["blocked_count"]
        self.assertEqual(self.execute(payload)["disposition"], "invalid")

    def test_submitted_task_states_cannot_exceed_total(self) -> None:
        payload = event("checkin.submitted")
        payload["outcome"].update({"task_count": 2, "done_count": 2, "blocked_count": 1})
        self.assertEqual(self.execute(payload)["disposition"], "invalid")

    def test_nested_unknown_and_private_fields_fail_closed(self) -> None:
        unknown = event("checkin.opened")
        unknown["trace"]["extra"] = "no"
        self.assertEqual(self.execute(unknown)["disposition"], "invalid")

        private = copy.deepcopy(event("checkin.submitted"))
        private["outcome"]["raw_submission"] = "restricted"
        self.assertEqual(self.execute(private)["disposition"], "invalid")

    def test_rejected_event_requires_unique_rule_ids(self) -> None:
        payload = event("checkin.rejected")
        payload["outcome"]["rule_ids"] = ["FMT-5", "FMT-5"]
        self.assertEqual(self.execute(payload)["disposition"], "invalid")


@unittest.skipUnless(NODE, "Node.js is required to execute n8n Code-node runtime tests")
class ComplianceCodeRuntimeTests(unittest.TestCase):
    def execute(self, filename: str, payload: dict) -> list[dict]:
        harness = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const execute = new Function('$input', 'Buffer', 'require', snippet);
const output = execute({first: () => ({json: payload})}, Buffer, require);
process.stdout.write(JSON.stringify(output));
"""
        process = subprocess.run(
            [str(NODE), "-e", harness, str(ROOT / "n8n" / "code" / filename)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def snapshot(self) -> dict:
        return json.loads(
            (ROOT / "contracts" / "compliance" / "examples" / "compliance-snapshot.json").read_text(
                encoding="utf-8"
            )
        )

    def test_expectation_builder_converts_user_local_sla_to_utc(self) -> None:
        output = self.execute("expectation-builder.js", self.snapshot())
        rows = output[0]["json"]["expectations"]
        eod = next(row for row in rows if row["checkin_type"] == "EOD")
        self.assertEqual(eod["sla_due_at"], "2026-09-04T16:00:00Z")

    def test_expectation_builder_rejects_invalid_cycle_and_duplicate_sla(self) -> None:
        bad_date = self.snapshot()
        bad_date["cycle_date"] = "2026-02-30"
        with self.assertRaises(AssertionError):
            self.execute("expectation-builder.js", bad_date)

        duplicate = self.snapshot()
        duplicate["sla_rules"].append(copy.deepcopy(duplicate["sla_rules"][0]))
        with self.assertRaises(AssertionError):
            self.execute("expectation-builder.js", duplicate)

    def test_weekly_rollup_rejects_more_than_seven_days(self) -> None:
        payload = {
            "period_start": "2026-09-01",
            "period_end": "2026-09-08",
            "expectations": [],
            "checkins": [],
            "pod_lead_channels": {},
        }
        with self.assertRaises(AssertionError):
            self.execute("weekly-rollup.js", payload)


@unittest.skipUnless(NODE, "Node.js is required to execute n8n Code-node runtime tests")
class ReplayCodeRuntimeTests(unittest.TestCase):
    def execute_planner(self, payload: dict) -> list[dict]:
        harness = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const execute = new Function('$input', '$execution', 'Buffer', snippet);
const output = execute({first: () => ({json: payload})}, {id: 'runtime-test'}, Buffer);
process.stdout.write(JSON.stringify(output));
"""
        process = subprocess.run(
            [str(NODE), "-e", harness, str(ROOT / "n8n" / "code" / "dlq-replay-planner.js")],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def execute_success(self, response: dict, planned: dict, leased: dict) -> list[dict]:
        harness = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = {
  'Plan Stage-Safe Replay': payload.planned,
  'Acquire Replay Lease': payload.leased,
};
const execute = new Function('$input', '$', snippet);
const output = execute(
  {first: () => ({json: payload.response})},
  (name) => ({item: {json: nodes[name]}}),
);
process.stdout.write(JSON.stringify(output));
"""
        process = subprocess.run(
            [str(NODE), "-e", harness, str(ROOT / "n8n" / "code" / "replay-success.js")],
            input=json.dumps({"response": response, "planned": planned, "leased": leased}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def candidate(self) -> dict:
        return {
            "id": 17,
            "status": {"value": "pending"},
            "failure_stage": {"value": "event_dispatch"},
            "replay_key": "exec-17|event_dispatch",
            "correlation_id": "corr-12345678",
            "raw_submission": "- valid task @status:done",
            "next_retry_at": "2026-09-04T15:00:00Z",
            "replay_started_at": None,
            "replay_attempt_count": 0,
        }

    def test_planner_normalizes_baserow_selects_and_preserves_replay_steps(self) -> None:
        output = self.execute_planner({"now": "2026-09-04T16:00:00Z", "results": [self.candidate()]})
        planned = output[0]["json"]
        self.assertEqual(planned["status"], "replaying")
        self.assertEqual(planned["failure_stage"], "event_dispatch")
        self.assertEqual(planned["replay_steps"], ["verify_checkin", "verify_canonical_post", "ensure_event"])

    def test_success_response_must_match_original_replay_identity(self) -> None:
        planned = self.execute_planner({"now": "2026-09-04T16:00:00Z", "results": [self.candidate()]})[0]["json"]
        valid = {
            "status": "resolved",
            "checkin_id": "mm-user|2026-09-04|EOD",
            "correlation_id": planned["correlation_id"],
            "replay_key": planned["replay_key"],
        }
        output = self.execute_success(valid, planned, {"id": 17})
        self.assertEqual(output[0]["json"]["patch"]["status"], "resolved")

        wrong = dict(valid, correlation_id="corr-wrong999")
        with self.assertRaises(AssertionError):
            self.execute_success(wrong, planned, {"id": 17})


if __name__ == "__main__":
    unittest.main()
