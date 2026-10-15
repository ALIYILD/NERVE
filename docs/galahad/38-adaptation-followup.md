# Automatic diagnosis after rejected adaptation

The registered followup coordinator consumes a receipt-verified recovery-study rejection, claims a diagnostic node durably, computes the diagnosis, revalidates its predecessor and writes a reconciled result. A reused shared ledger refuses a renamed-directory retry, including after failure. This subloop runs through `scripts/diagnose_recovery_adaptation.py`; the earlier study executable does not automatically invoke it.

The calculation uses validation traces only. Four fixed 20-step physical windows and four joint baseline/adaptive command-source combinations exhaust every paired step. Summed contributions reproduce the aggregate goal and prediction differences. Strata are descriptive: conditioning on command source does not identify causal effects. No acceptance gates change and no candidate is selected.

## Measured evidence

The real predecessor contains 32 validation episodes. Diagnosis inspected **1,280 matched steps** in 32 strata, with **zero new plant episodes**. The aggregate adaptive-minus-baseline differences are:

| Regime | Goal error | Prediction error |
| --- | ---: | ---: |
| Stationary | −0.000114748253 | +0.000354490930 |
| Drift | +0.008471711957 | −0.002258440339 |

Only drift has improved prediction with worse goal tracking. The original decision remains **retain baseline**. The returned next action is `register_objective_aligned_candidate_study`; that prospective study is not implemented or automatically executed by this diagnostic. No final-evaluation stream was run or used for these diagnostics. Receipt reconciliation checks predecessor integrity, including any records already present; diagnostic aggregation itself excludes holdout rows.

Independent review identified two source-level hypotheses for a subsequent experiment: the learned dynamics gain and filter propagation coefficient may diverge, and the active WorldCore action chooser uses a one-step score despite its inherited horizon setting. These observations do not establish the cause of this regression. Investigating them requires a fresh prospective contract rather than changing this study's gates.

## Replay and verification

An initial diagnostic ran before review requested tighter snapshot binding. The revised reader brackets receipt validation with identical report bytes and rejects mutation during validation. The revised diagnostic was then explicitly replayed over the same existing validation traces using a separate review ledger. This is reanalysis of published evidence, **not an independent experiment**. Both ledgers remain intact; the original dataset ledger still prohibits rerunning the plant study. Operator deletion/replacement of ledgers is not prevented.

Authoritative reviewed run: `/private/tmp/nerve-adaptation-followup-reviewed`, claims: `/private/tmp/nerve-adaptation-followup-reviewed-claims.sqlite`. [Archived diagnostic](evidence/adaptation-followup-reviewed.json) contains source hashes and the predecessor digest. The source study remains `/private/tmp/nerve-recovery-adaptation-v1` with `/private/tmp/nerve-recovery-adaptation-claims.sqlite`.

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_adaptation_followup.py -v
# Explicit reanalysis of published validation evidence, not a new learning experiment:
PYTHONPATH=src .venv/bin/python scripts/diagnose_recovery_adaptation.py \
  --directory /private/tmp/nerve-adaptation-diagnostic-replication \
  --predecessor /private/tmp/nerve-recovery-adaptation-v1 \
  --study-claims /private/tmp/nerve-recovery-adaptation-claims.sqlite \
  --followup-claims /private/tmp/nerve-adaptation-diagnostic-replication-claims.sqlite
```

Eight targeted tests cover exact contribution accounting, holdout exclusion, malformed pairs/traces, claim ordering, replay denial, failure consumption, receipt tampering and mutation during validation. This is synthetic research infrastructure, not a demonstration of generally self-improving intelligence, LLM weight training or clinical readiness.

The full repository suite passed **1,364 tests in 89.701 seconds** before the final snapshot-binding adjustment. After that adjustment, the complete targeted module passed **8 tests** (including the new mutation test), and read-only receipt reconciliation of the reviewed run returned `True`. The full suite was not rerun after that small adjustment.
