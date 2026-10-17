# W2 advisor calibration and cycle evidence — doc 13x

Status: **blocked**. All evidence is synthetic dev research. No holdout, signing or activation.

D9: Brier and AUC per generator against verdicts, final advisor trust weights, and template versus Socratic keep rates.

D10: monitor coverage and quarantine counts: {"agent_node": 0, "checked": 0, "eligible": 0, "exercised": false, "missing": 0, "quarantined": 0, "socratic": 0}. Zero eligible is not live validation.

| Advisor | Verdicts | Brier | AUC | Weight |
|---|---:|---:|---:|---:|
| template | 0 | None | None | 0.333333 |
| socratic | 0 | None | None | 0.333333 |
| jev | 0 | None | None | 0.333333 |

Null metrics are undefined, not passing scores. Jev fixture and live calibration are separated in the JSON file.
Historical rows without prospective priors are excluded. Comparisons are conditional on selection, not causal generator effects.

Family A: {"higher_keep_rate": null, "socratic": {"keep_rate": null, "kept": 0, "n": 0}, "template": {"keep_rate": null, "kept": 0, "n": 0}}

Run summary / refusals / bank hardening: {}

Family B: {"higher_keep_rate": null, "socratic": {"keep_rate": null, "kept": 0, "n": 0}, "template": {"keep_rate": null, "kept": 0, "n": 0}}

Run summary / refusals / bank hardening: {}

Reason: ANTHROPIC_API_KEY_missing_and_W0_preflight_pending

Evidence: research/leaderboard-20261017.jsonl; research/calibration-20261017.json; research/status-20261017.json.
Private immutable registrations and wire receipts: ~/nerve-research-runs/w2-cycle-20261017/.
Obsidian exports: ~/nerve-research-runs/obsidian-audit-vault/. Display only, never state.
