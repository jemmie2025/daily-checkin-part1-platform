# Superset dashboard package

`make superset` creates a deterministic native-import ZIP from these assets.
Import it first into an isolated Superset workspace. During import, map the
database asset to the approved ClickHouse connection and supply its password
through Superset's secret backend; `XXXXXXXXXX` is intentionally non-secret.

The dashboard ships unpublished with two native filters and six charts:

1. Submission rate by expected-roster denominator.
2. On-time versus late submissions by pod.
3. Median submit latency.
4. Top FMT rejection rules.
5. Proof-attachment rate.
6. Blocked-task trend.

The reader role is restricted to three security-definer reporting views, which
combine recent deduplicated metrics with aggregate-only history. Validate each
dashboard total against `checkin_platform.analytics.reconcile_metrics` fixtures
before publishing to leads.
