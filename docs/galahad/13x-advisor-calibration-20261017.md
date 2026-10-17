# W2 advisor calibration checkpoint

D9: advisor calibration — Brier and AUC per generator against verdicts, trust
weights at close, and whether Socratic or template hypotheses were kept more often.
Evidence: `research/leaderboard-20261017.jsonl`,
`research/calibration-20261017.json`, this doc 13x.

Status: **not achieved; new cycle not running**. The rewritten program replaces
W2's old stop-after-three-reverts specification. The existing B01b keep remains
historical: its registration has no prospective advisor priors, so it contributes
neither calibration labels nor bandit feedback. No new verdict was manufactured.

| Advisor | Prospective verdicts | Brier | AUC | Current weight |
|---|---:|---|---|---:|
| template | 0 | undefined | undefined | 1/3 |
| socratic | 0 | undefined | undefined | 1/3 |
| jev | 0 | undefined | undefined | 1/3 |

Both families lack comparable generator keep rates. No bank hardening has run;
old versus new incumbent scores are unmeasured. Jev's absent key selects the
neutral `no-live-jev` readiness fixture, not a backfilled historical prior.

Preflight verified the existing 17 protected-file hashes and four experience
journal chains. The live Runpod get-pod read found pinned pod B
`5xndo7i7s5r9zn` EXITED at USD0.59/hour. No GBP rate is claimed without an FX
basis. W0's shared inference-revoked.json still records infrastructure_stop.
No lock was acquired, no model calls made, no holdout opened, no spend fabricated.

The new code supplies advisor triage/calibration, a labelled offline Jev prior,
and a source-hashed Obsidian research view through obsidian_export_v18. It does
not yet wire the two Hermes generators, arbitrary family seams, transport,
sealed new-bank creation or repeated cycle dispatch into an executable runner.
The existing overnight_dev_study.py remains a historical one-study transport;
its frozen source and evaluator have not been changed to bypass registration.

Refusals: retrospectively assigning priors to B01b; counting an infrastructure
stop as a revert; claiming AUC with one/no label class; calling this a running
engine; treating exported research records as approved memory; reopening W0's
global stop without resolving its scope. The four 01:40 readiness checks are
not satisfied at this checkpoint.

Audit view: `~/nerve-research-runs/obsidian-audit-vault/W2-20261017.md`.
The vault is display only and is never read back as state.
