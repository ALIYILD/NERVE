# Cycle admission guard — review patch

The cycle previously accepted an authorization flag without checking that the
shared ledger contained the operator's successful preflight. It also did not
require its focused test evidence at session startup. This patch checks both
before creating the private session directory or starting any provider call.

The scoped authorization must add `preflight_event_sha256`: SHA-256 of the exact
operator ledger row serialized with `json.dumps(row, sort_keys=True,
separators=(',', ':')).encode()`. The row must have `event: preflight_ok`, the
admitted `pod_id`, `issued_by: operator`, the canonical `digest`, and a 64-character
lowercase SHA-256 `replay_hash`. Later preflight failure or unusable-pod events
invalidate the selected row. The current pod-B lock must bind the same pod.
These are local admission records, not signatures or promotion authority.

Focused readiness must pin the current cycle and preflight sources, all declared
sources must still match, and the log and receipt hashes must verify. Existing
readiness is intentionally stale after this change. Re-run only the focused
module tests under the shared exclusive test lock, refresh the receipt and
readiness pins, and obtain the genuine successful pod preflight before admission.
Never fabricate a ledger row to satisfy this check.

Nine focused cases cover the accepted record, absent ledger event, wrong event
binding, source drift, receipt/log tampering, wrong pod lock, later failure, and
session refusal before directory creation. They have **not run**: an unrelated
PerfFlux integration pytest process was active. Syntax parsing and all 80
protected hashes passed; no inference, pod calls, signing, or full-tier tests ran.
The patch is isolated on `overnight/resume-admission-guard` based on `8a2cfec`;
it is not integrated or admitted for inference. The base also contains an
external-provider advisor path; this patch does not authorize its use under this
conversation's RunPod-only instruction.
