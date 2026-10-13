# Registered research handoff and WorldCore evaluation

The new coordinator automatically advances from a verified, terminal online-policy experiment to a separately bounded WorldCore experiment. A completed experiment can reject its candidate; completion never grants promotion. The earlier online study remains rejected for its mixed-regime regression.

The graph has two registered nodes: read-only receipt verification, then WorldCore simulation. It cannot execute arbitrary jobs or generated source. Every node is claimed in SQLite before dispatch. WorldCore runs in a spawned process with a 120-second limit and bounded termination/kill cleanup. Existing execution directories, including symlinks, are refused. A failed or interrupted node is consumed locally; there is no automatic replay. After abrupt termination a child ledger may retain running/claimed rows: these are incomplete consumed evidence, never resumable work. Directory protection and operator-owned SQLite are not independent holdout custody; deleting or copying ledgers can bypass local replay protection.

Receipt verification compares the predecessor export and database against the current registered source/dataset manifest. It validates all 352 trials, their identities, rewards, configurations, order and counts; recomputes each generation's decisions and the final rejection; and checks the frozen-selection digest. The WorldCore receipt similarly reconciles protocol, selection, call journal and report, then replays deterministic decision logic using recorded metrics without running simulations again. These checks detect inconsistent evidence, not coordinated falsification by an operator controlling the filesystem.

WorldCore reuses the existing bounded parallel workers, recursive parameter search, adaptive controller, simulated plant and absolute safety gates. Its final recommendation now additionally requires strict goal improvement on holdout. Optional validation and final seeds are strictly typed, nonempty, bounded and disjoint. A trusted selection callback persists the selected recipe and lineage before final evaluation.

## Actual result

One fresh CPU study ran automatically after receipt verification, using validation seeds 31001–31008 and final seeds 32001–32008. Three generations proposed eight distinct candidates, with one duplicate omitted. Eleven evaluator calls completed across **88 simulation episodes** (80 maximum steps per episode, including early aborts). No language model or GPU was called.

**No deployable improvement was found.** Every validation candidate failed absolute completion/abort gates. The baseline recipe remained max-missing 5, risk-aversion 0.25. Baseline validation completion was 50.94%; final completion was 51.25%, with every final episode aborted. Selected and baseline final metrics are identical. Aborted steps are penalized by the existing evaluator. No gate was relaxed, policy promoted, model weight trained, device actuated or clinical workflow deployed.

This establishes an executable handoff between two research task families. It does not establish general self-learning or scientific discovery. The WorldCore result exposes a concrete next research issue: controller robustness under the simulation's sensor dropouts and drift. Further experiments need a prospective protocol; these observed final seeds must not be reused as fresh evaluation.

Artifacts:

- [Complete compressed graph report](evidence/cross-track-orchestrator-v1.json.gz)
- [Protocol, results and artifact hashes](evidence/cross-track-orchestrator-v1-summary.json)

The local journals remain in `/private/tmp/nerve-cross-track-orchestrator-v1`. The experiment finished; no background worker is claimed to remain active.

## Verification

The complete suite passed **1,301 tests**, zero failures/errors, in 94.606 seconds. A preceding sandboxed attempt could not run localhost/protected-subprocess fixtures; the full rerun used the required permissions. Added tests cover receipt tampering, contradictory lineage, consumed claims, malformed accounting, source drift, timeout/crash cleanup, symlink roots and unchanged-selection holdout validation. Independent review verified the actual receipts and source hashes. See [validation evidence](evidence/cross-track-validation.json).

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/run_research_orchestrator.py \
  --directory /private/tmp/nerve-cross-track-replication \
  --online-database /private/tmp/nerve-online-optimisation-v1.sqlite \
  --online-output /private/tmp/nerve-online-optimisation-v1.json \
  --online-run-id online-optimisation-v1
```

Use a new directory. The predecessor journal must exist and match the pinned current implementation; a compressed report alone cannot substitute for its journal. Repeating published seeds is replication, not fresh evidence. A standalone WorldCore replication is available through `scripts/run_worldcore_study.py --directory NEW_DIRECTORY` with `PYTHONPATH=src` and the repository virtual environment.
