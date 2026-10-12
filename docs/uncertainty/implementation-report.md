# Persistent uncertainty: implementation and combined verification

Implemented uncertainty loops 20–25 on `codex/uncertainty-integration` in
`/Users/aliyildirim/nerve-uncertainty`. Starting commit: `57074d9`.
This report records implementation commit `3cbb7e0` and handoff `64b6073`.
Later atomicity and performance changes are documented in
[continuation-performance.md](continuation-performance.md); the benchmark below
remains evidence for its original source revision.
Frozen Python source digest:
`56590516c37869a1a3830f758e39700e0c88bf2ef5d9aac00d733556cc6c500a`.

The two other windows were allowed to finish their published handoffs. Memento
commit `2d42201` was merged as `ead0457`. Adaptation's final 22-file manifest was
validated before importing its completed snapshot. Exact provenance is retained
in [adaptation-import.json](adaptation-import.json). Neither original checkout was edited.

## Implementation and acceptance evidence

| Loop | Implemented behavior | Acceptance evidence |
|---|---|---|
| 20 | Scoped source/claim/conflict ledger, additive versioned schema, lineage normalization, typed reconciliation, CAS closure and reopening | Migration preserves historical rows; duplicate delivery, source deletion, cross-scope denial and concurrent close/new evidence tests |
| 21 | Authoritative envelopes across actual Hermes learning, trusted-memory retrieval, checkpoints and Memento coordinator/rulebook | Missing conflict lists are rebuilt; incomplete state is explicit; restart, truncation, source deletion and role changes tested |
| 22 | Durable reservations, finite verification deadlines, deduplication and evidence-predicate resolution | Timeout remains uncertain; late callbacks cannot resolve; no useful evidence earns no resolution credit; three sealed fixture resolutions independently audited |
| 23 | Action-specific host policy in real governed dispatch and ARC; release/canary/monitor gates | Relevant actions denied with no handler effect; unrelated work proceeds; task substitution, dropped child dependencies, expiry and stale assessments denied |
| 24 | Supported/qualified/unresolved output, canonical text/API/report rendering, provisional streaming, bounded regeneration | Actual Hermes output, contradictory summaries, malicious certainty, wrong-task assessment and source-change race tests |
| 25 | Four-arm paired evaluator, frozen code/data/policy, scoped consumed holdouts, CLI and release evidence bindings | 86 uncertainty tests; all CLI commands exercised; deterministic fixture gates pass, factual/model-benefit gate remains inconclusive and ineligible |

Existing integration points extended: `governed_learning_v20`, `hermes_learning`,
`memory_v18`, `arc_execution`, `canary_learning_v23`, `promotion_monitor_v24`,
Memento registry/coordinator/release, and the Agent OS adaptation CLI. The new
services share existing host capabilities and SQLite storage. They do not replace
the orchestrator, create a second agent memory system, or grant external authority.

## What the combined demo actually did

`combined-final.json` records real dispatcher calls in a deliberately synthetic,
local deterministic host:

1. An incorrect heading returned successfully but failed semantic verification.
2. A host-verified correction was retained; the next action verified successfully.
3. New contradictory evidence created a material conflict. The next dependent
   action received `verify_first`; the registered handler ran **zero** times.
4. An independent task verified successfully. The affected Memento model could
   no longer freeze. Its disputed rule remained a hypothesis.
5. Reopening with fresh host capabilities, resuming and resetting retained the
   current conflict and action receipts. No effect was repeated.

The separate real repository recovery command also passed: regex inventory failed
independent verification, AST correction was verified, then reused after restart.
This demonstrates task-local verified correction reuse, not a learned LLM weight
update or improvement over an already-correct AST baseline.

## Tests and commands

Controlled evidence directory: `/private/tmp/nerve-uncertainty-evidence/`.
Runtime SQLite, detailed conflict events and raw uncertainty run reports remain
there rather than in source control. The documentation records aggregate outcomes.

| Command/check | Result | Evidence |
|---|---|---|
| `PYTHONPATH=src /private/tmp/nerve-adaptation-ci-venv/bin/python -m unittest discover -s tests -v` | Exit 0; **1,121 passed, zero skips**, 104.245 s | `full-tests.log` |
| `node --test tests/test_checkpoint_discovery.cjs` | Exit 0; **7 passed** | `node-tests.log` |
| `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_uncertainty*.py' -q` | Exit 0; **86 passed** | `uncertainty-tests.log` |
| Adaptation focused suite with Python 3.12/NumPy | Exit 0; **46 passed** | `adaptation-tests.log` |
| Combined demo with fresh explicit SQLite path | Exit 0; `passed: true` | `combined-final.json` |
| Actual repository recovery via `adaptation-run --scenario recover-regex --restart` | Exit 0 | `repository-recovery.json` |
| Optional bounded CPU fast-memory training and scaling commands from CI | Both exit 0; benefit **false** | `research-training.json`, `research-scaling.json` |
| Uncertainty doctor, selection, freeze, sealed evaluation, report, demo, inspect, resume | All exit 0 | `final/commands.json` |
| Uncertainty verify without an authenticated external primary record | Expected exit **4**, `unresolved_no_source`; resume repeats zero calls | `final/verify.json`, `final/resume.json` |

The first aggregate test run overlapped source integration and correctly rejected
an evaluation whose source digest changed. Its failure remains recorded in
`intermediate-source-change-tests.log`. After freezing the source, the entire suite
passed; no test or integrity condition was weakened. All **51 offline CI commands** were verified, plus the two folded CPU training/scaling commands. The final CI rerun initially passed 50/51: the Memento demo refused its already-consumed disposable database with exit 8. Running that demo with a fresh explicit database passed; both receipts are retained (`ci/check-46.log`, `ci/check-46-fresh.log`). This reproduces public diagnostic fixtures and does not create a new promotion holdout. Full command results are in `ci/results.json`, `verification-results.json` and the resumable progress file.

## Frozen benchmark

Run `run-9875cf8208c94cba898d7aefd405692c`, dataset
`2249e21a2f9cfe062f9c8507b9ccef0239bceb1a2a24cf1c23435a1222fc2b2c`.
Selection and sealed-final each contain 12 cases in six paired source-family
clusters. Across both splits: 96 scripted-provider invocations, nine verification
calls, no incomplete cases, zero paid cost and **zero live model requests**.

| Sealed-final metric | A: existing | B: instruction | C: ledger | D: full handling |
|---|---:|---:|---:|---:|
| Answer coverage | 12/12 | 12/12 | 12/12 | 12/12 |
| Unsupported certainty | 6/12 | 6/12 | 6/12 | **0/12** |
| Observed dispatch policy violations | 3/12 | 3/12 | 3/12 | **0/12** |
| Remaining conflicts visible in final answer | 0/6 | 0/6 | 0/6 | **3/3**, after three justified resolutions |
| Total observed case time | 0.404 s | 0.403 s | 0.700 s | 1.358 s |

D added approximately 79.5 ms/case over A; its maximum case time was 0.202 s,
below the frozen two-second ceiling. These are local observed timings during
validation, not controlled production latency estimates. In selection, D's
coverage was 9/12 against A's 12/12; the report retains that abstention tradeoff.

The fixtures intentionally use an adversarial scripted provider that ignores
instructions. B's result cannot estimate prompt effectiveness on a real LLM.
Factual accuracy, factual confident errors, selective factual risk, blinded human
review and accuracy non-inferiority remain **null**, because independent labels are
missing. The primary model-benefit hypothesis is **inconclusive**. Release
eligibility remains **false/shadow-only**, even though deterministic policy checks
pass. Public fixture reproduction is diagnostic, not a new independent holdout.
See [evaluation.md](evaluation.md) for full methodology and denominators.

## Remaining boundaries and defaults

- No provider-verified or deployed result. Host adapters remain opt-in; no running
  production Agent OS/Hermes/MCP/device service was silently enabled. Local CLI
  identity is the OS user, not a remote authentication service.
- Memento's supplied workstream remains a research foundation with its own
  [partial-loop backlog](../world-model/backlog.json). Actual implemented hooks
  are wired; missing production proposal tools or external-effect machinery are
  not represented as completed.
- Adaptation's fresh source-window evaluation found 30/30 recovery successes and
  30/30 capable AST successes: **zero accuracy gain**, and 95.8% recovery overhead
  against a 20% ceiling. That candidate remains rejected. Historical evidence
  retains its own recorded digest; this combined branch does not borrow it as a
  new held-out trial.
- The repeated optional CPU study again found trained online memory **12.744 pp
  worse** than exact structured memory (paired seed interval approximately
  −13.496 to −11.992 pp). Training completing does not authorize promotion.
- A timed-out trusted read callback may finish in a background thread. Waiting
  and worker admission are bounded; late results are discarded. This is not an
  arbitrary-code sandbox or forced cancellation of an external service.
- Sources are immutable host-registered references; a content hash proves
  identity, not truth. Live verification needs reviewed connectors, source trust,
  authoritative receipts and an explicit finite priced budget. Paid budget here
  is zero; no Claude credit was consumed.
- Normal adaptation and world-model production configuration remains off.
  Uncertainty evaluation defaults to shadow/ineligible. Once a context is opted
  in, omission of its adapter fails closed after restart. Backup before explicitly
  constructing/migrating these components against any persistent host store.
  Reset/rollback never deletes newly discovered conflicts or evidence history.

## Reproduce

Use Python 3.12 and the dependencies pinned in `.github/workflows/tests.yml`
(OIDC crypto, MCP, and optional NumPy in the research job). No provider keys are
required. Choose fresh demo paths so prior evidence is preserved.

```sh
cd /Users/aliyildirim/nerve-uncertainty
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --test tests/test_checkpoint_discovery.cjs
PYTHONPATH=src python3 -m nerve_awim.uncertainty.combined_demo --state /tmp/nerve-combined-demo.sqlite3
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli doctor --json
PYTHONPATH=src python3 scripts/agentos_bridge.py adaptation-run --repository . --scenario recover-regex --restart --state /tmp/nerve-recovery --report /tmp/nerve-recovery.json
```

For selection/freeze/evaluation and actual returned identifiers, follow the
[operator guide](operator-guide.md). Do not reuse a consumed holdout to claim
fresh benefit. `implementation-progress.json` preserves status and remaining gates.
