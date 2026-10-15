# Durable negative-evidence screening

The proposed learning loop now has a scoped rejection journal and a screening
runner. These prevent an adjudicated failed candidate from silently becoming a
fresh experiment through new hypothesis packaging. This is groundwork for
Loop 39.3, not proof that the new candidates improve the model.

## Authority and evidence

`scientific_negative_evidence.py` reuses the existing Memory Gateway's read and
approve capabilities. A trusted host reviewer can record a rejection only for a
registered hypothesis whose current scoped episode evidence validates. The
receipt binds candidate configuration, hypothesis, evaluator, model identity,
task-bank identity, reason and a bounded inline study report with its hash.
Report and receipt must both state `evaluated_rejected`. Insufficient power and
transport failure are not accepted as efficacy rejection verdicts.

This is an **explicit trusted-host adjudication boundary**: the approve capability
vouches for the submitted experiment report. The journal checks structural and
identity consistency; it does not independently establish that supplied metrics
were measured. A future evaluator adapter must verify actual study receipts before
host adjudication. No rejection was fabricated for the actual registered candidates,
and their previous interface failures were not mislabeled as evaluations of the
new conflict-check configuration.

Approved rejection history is separate from approved factual knowledge and from
promotion authority. Ordinary proposers cannot write it. Private SQLite storage
uses append-only triggers, canonical receipts, scope binding, a complete hash
chain and tail count. Atomic duplicate submissions preserve the existing record;
concurrent duplicate writes recheck authorization. Missing or corrupt journals
allow no candidates. The screening runner requires explicit initialization and a
separate durable identity marker; deleting the database does not silently reset
history. These controls protect against accidental/partial alteration, not a
privileged host rewriting every checksum and marker.

## Retry rule

Candidate identity is the hash of the fixed typed configuration. Distance is
Hamming distance over those configuration fields, not over hashes. Exact matches
and distance <=1 match a rejection. The current four distinct configurations are
all distance >=2, so end-to-end suppression tests exercise exact matches; the
distance-one helper is tested separately without pretending an unregistered
combination is executable.

Every rejection stores **all failure-cluster keys present at rejection time**.
A key is `(stratum, failure_class)`. A matching candidate is eligible for another
experiment only if its currently validated cited key was absent from every
matching rejection's snapshot. Renamed episode IDs, timestamps, source pins,
changed context/input hashes, new members within an existing cluster and reuse
of a different old cluster do not qualify. A changed bank hash alone is not a
verified new-bank exception; that path remains unsupported and fails closed.

This is deliberately a narrow definition of new failure evidence. It does not
perform semantic scientific adjudication of arbitrary data. Current source
import validation and trusted host roles remain responsible for episode truth.
A novel key authorizes consideration for another experiment, never promotion.

The filter returns the consulted journal head and rejection count. Even an
unrelated later adjudication changes the screening snapshot, so a stale report
cannot be reused as if it checked the latest history.

## Integration and actual run

`scientific_candidate_screening.py` revalidates the completed candidate
registration and original episode import, consults negative history, and writes
a deterministic private report. It reuses host capabilities, exact publication
and exclusive-lock helpers. The new CLI has no inference, holdout, rejection
creation or promotion operation.

Actual paths:

- Registration: `nerve-research-runs/scientific-candidates-v1`
- Rejection history: `nerve-research-runs/scientific-negative-history-v1`
- Screen: `nerve-research-runs/scientific-candidate-screen-v1`

The actual journal has **zero rejection records** because the three candidates
have not been evaluated. All three were returned as eligible, unevaluated
proposals; none was promoted. Fresh-process replay with model calls and protected
bank/seed access forbidden preserved ten checked report/database/export files'
bytes and modification times, including the original validation receipt and
call-claim journal. No model calls or rejection records were created.

[Actual screen](evidence/scientific-candidate-screen-v1.json) and
[restart verification](evidence/scientific-candidate-screen-v1-verification.json)
record this result. Rejection, retry-exception and corruption behavior are tested
using explicitly fabricated adjudications in isolated temporary fixtures. Those
fixtures are not empirical efficacy evidence.

## Reproduction

From the repository root, using the existing completed registration:

```bash
PYTHONPATH=src .venv/bin/python scripts/screen_scientific_candidates.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-screen-v1 \
  --registration-directory /Users/aliyildirim/nerve-research-runs/scientific-candidates-v1 \
  --history-directory /Users/aliyildirim/nerve-research-runs/scientific-negative-history-v1 \
  --initialize-history
# Subsequent runs may omit --initialize-history; missing history is never rebuilt.
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_negative_evidence.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_candidate_screening.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

The 23 new focused tests cover host authorization/revocation, deterministic
identity, rejection persistence, typed distance, all-prior-cluster comparison,
old-cluster reuse, hash-only novelty attempts, failed-store handling, concurrency,
report integrity, screening snapshots, CLI and zero-inference restart.

Full regression: **1,925 tests passed in 173.633 seconds**. Independent review
reran the 23 new tests and checked actual artifacts read-only.
[Test evidence](evidence/scientific-negative-evidence-v1-tests.json).

## Remaining work

An executable candidate adapter and a preregistered development study are next.
The powered evaluator, independent holdout, verified study-to-rejection ingestion,
new-bank exception, skill retention and complete unattended conductor remain
unfinished. GPU endpoint/budget and Galahad compatibility/licensing/restoration
remain unverified. No clinical workflow, model weights, active policy, deployment,
push or pull request changed. No new accuracy or performance claim is made.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
