# Readiness after continuation

Applied in `/Users/aliyildirim/nerve-review` on
`codex/robottt-task-adaptation-20261012`. Task adaptation now has a real read-only
repository CLI workflow in addition to the synthetic demos and optional external
fast-memory research. It uses the existing ARC dispatcher, tool registry, independent
verifier and SQLite store. The normal tool is the capable AST inventory; the explicit
`recover-regex` scenario exercises a verified correction, reopened task state and reuse.

| Readiness distinction | Latest result |
|---|---|
| Local implementation | Synthetic workflows and real read-only repository integration implemented |
| Observed normal behavior | Verified both real NERVE source files without correction |
| Observed recovery behavior | Detected incorrect regex inventory, verified AST alternative, reopened/resumed, reused correction and closed with three receipts |
| Final regression | 1,007 Python tests passed on Python 3.12 |
| Focused checks | 46 adaptation/research tests, 86 ARC tests and 7 Node tests passed |
| Fresh current-code evaluation | 60 development plus 30 held-out repository episodes; exact code digest matches current implementation |
| Benefit against capable baseline | Zero: adaptation and fixed AST each passed 30/30 held-out cases |
| Track A overhead | Failed: recovery p95 overhead 95.8%, threshold 20% |
| Track B benefit | Prior five-seed study remains negative, about −12.7 pp versus exact structured memory |
| Live providers / clinical host | Unverified and not activated; zero provider calls |
| Production approval / deployment | Neither approved nor deployed |

See [what NERVE actually did](continuation/observed-behavior.md), including exact
function inventories, decisions, receipts, commands and benchmark interpretation.
The normal workflow does not deliberately choose the inferior tool. Adaptation is
useful in the demonstrated recovery scenario but does not beat the capable fixed
baseline. Candidate `adaptation-repository-v2-final` was rejected accordingly.

The continuation batches schema creation, reuses the planning transaction for
context checks and avoids duplicate intent rewrites. All authorization checks and
durability remain in place. A WAL trial was slower and was discarded. Profiles are
diagnostic samples, not a statistically demonstrated general performance gain.

The new version-2 held-out source templates are separate from the consumed v1
fixtures. Earlier failed attempts and exact source versions remain recorded. The
44 additional offline CI commands from the preceding implementation remain recorded
in `ci/results.json`; they were not rerun in this continuation. Final full regression,
focused tests, Node tests and the new runtime/evaluation commands were run again.

Live subject permissions, domain-specific clinical review, protected-storage
retention/deletion and cancellable external tool interfaces remain host integration
requirements. Non-ARC Hermes/MCP/device adapters are not silently opted in. No paid
provider budget, clinical policy update or learned-memory production activation
was inferred from the instruction to continue. The optional memory experiment is
not RoboTTT reproduction or access to hosted LLM weights.

No commit, push or deployment was performed by this task. Existing ARC work and its
concurrent prerequisite commit were preserved. Reviewable changes include untracked
adaptation/research files and narrow edits to the shared CLI/runtime. Exact working
source hashes are in [source-manifest.json](source-manifest.json).

Evidence: [verification results](verification-results.json),
[implementation status](implementation-status.json),
[fresh held-out report](continuation/repository-heldout.json),
[runbook](runbook.md).
