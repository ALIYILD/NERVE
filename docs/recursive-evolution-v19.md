# NERVE recursive Evolution Loop v1.9

**Status: Scheduled, bounded offline research** on public NERVE `main`. This is an AlphaEvolve-*inspired* evolutionary search controller, **not the Google AlphaEvolve product**, autonomous program synthesis or automated source-code self-modification.

## Research architecture

Google DeepMind AlphaEvolve combines candidate creation, objective automated evaluation, an archive and repeated selection. NERVE now has a corresponding **data-only** model of this pattern:

1. **Observe:** read the independently reviewed NERVE v1.8 synthetic memory corpus. Only approved, exact-scope records enter evaluation.
2. **Hypothesise:** mutate a validated two-integer retrieval recipe (`token_weight`, `trigram_weight`). Candidate strings or LLM responses are never executed as code.
3. **Evaluate:** independently score each candidate on fixed **training** and **validation** questions. The algorithm cannot change the evaluator, threshold, corpus, tenancy or holdout.
4. **Verify:** require zero cross-tenant results; reject any candidate that harms training accuracy or fails to strictly improve validation accuracy.
5. **Evolve:** retain an evaluated champion and a finite typed population archive. Try local mutations first, then explore unseen recipes elsewhere in the 35-recipe search space. Repeat within the generation/evaluation budget; report exhaustion only when all recipes have been considered.
6. **Holdout:** measure the final candidate and the baseline on a separate **report-only** dataset once after selection. If the final candidate regresses on holdout, report `no_verified_improvement`.
7. **Persist:** atomically write a versioned, checksummed numeric checkpoint, separate from the research report. Restore the latest available checkpoint artifact from successful `main` research runs, with cache as a fallback. Revalidate the previous selected candidate before exploring new combinations.
8. **Review:** output `candidate_for_human_review`, never deployment authority. No source files, clinical policies, agent permissions, LLM weights or physical actuators are changed.

## Default local commands

```bash
export PYTHONPATH=src
python -m nerve_awim.recursive_evolution_v19
python scripts/recursive_research_v19.py --checkpoint-out state/evolution.json --generations 6 --seed 19 > first.json
python scripts/recursive_research_v19.py --resume state/evolution.json --checkpoint-out state/evolution.json --generations 6 --seed 20 > second.json
```

Check the JSON `status`, `baseline_validation`, `selected_validation`, `report_only_holdout`, `lineage`, `candidates_evaluated`, `population_archive`, `resumed_from_checkpoint`, `completed_runs`, `cumulative_candidates`, `checkpoint_reset_reason`, `remaining_candidates`, and `stop_reason` fields.

## Scheduled autonomous research

`.github/workflows/recursive-research.yml` has:

- A GitHub Actions `schedule` trigger at minute 17 every six hours (UTC), plus optional `workflow_dispatch`.
- `contents: read` and `actions: read`, no repository-write, issue-create or pull-request permissions. The scoped GitHub workflow token reads artifacts; experiments use no model keys, external models or network data.
- One eight-minute GitHub job budget; unit tests first; bounded 6-generation research second.
- A dedicated `nerve-retrieval-checkpoint-v1` artifact requested for 90-day retention (subject to repository policy), independent of the seven-day report artifact. Discovery checks at most 100 successful runs of this workflow and accepts only completed `main` schedule/manual runs from this repository. Failed, PR, foreign and expired sources are excluded. API or download failures stop the job instead of silently losing history.
- `actions/cache@v4` remains a fallback if no retained eligible artifact is found, with a unique run-ID/attempt key. The artifact takes precedence. If both stores are absent, the run explicitly starts fresh.
- GitHub schedule delays, workflow disablement, retention limits and quota limits can still interrupt progression; this is not an always-on service or permanent archival storage.
- Safety assertions that abort the run on tenant leaks, malformed study protocol or budget excess.

Checkpoints contain only the schema, protocol, evaluator fingerprint, selected
recipe, typed archive and bounded counters. They contain no historical fitness,
holdout results or deployment approvals. SHA-256 detects accidental corruption;
it is **not a signature or authentication**. The checkpoint source remains a
trusted-host boundary, and previous fitness is always recomputed.

A fingerprint covers the evaluator/search module and memory-ledger implementation.
Any change resets the champion, archive and per-version counters, even when the
old champion would still score well. Legacy unversioned reports also reset once
on migration. Malformed data fails closed. Same-directory temporary-file writes,
flush/fsync and atomic replacement preserve the previous checkpoint on failed
writes. Filesystem durability after host power loss is not guaranteed.

Repeated runs reuse this fixed constructed holdout. It is excluded from checkpoint
inputs and candidate search, but repeated reporting does **not** establish fresh,
independent final verification across runs. New independently controlled evaluation
data is required before making generalisation claims. The retained champion is a
validation-selected research recipe, not a holdout-approved operational policy.

GitHub caches and artifacts are **not** a signed scientific evidence ledger. A
production system needs independently authenticated provenance and explicit archival
retention. See [GitHub artifact persistence](https://docs.github.com/en/actions/tutorials/store-and-share-data)
and [cache limits](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

### Restart verification

The cross-process regression test runs the real CLI against a temporary checkpoint,
then resumes from a new process. Seeds 1–3 examine 16, 12 and 6 new candidates,
covering all 35 recipes including the initial baseline. Subsequent runs re-evaluate
the champion but add zero candidates and report `search_space_exhausted`.
Corruption, interrupted writes, evaluator-version resets and artifact-source
selection are covered separately. These checks establish persistence/control-flow
behaviour, not general self-improving intelligence.

## Honest benchmark scope

Only the fixed synthetic retrieval weights evolve. There is no automatic prompt evolution, arbitrary source patch generation, LLM-driven proposal, full WorldCore controller evolution, multi-agent model-weight update or deployment.

**AlphaEvolve itself can generate program changes with LLMs** and verify them with evaluator scripts. That is a future optional, *sandboxed and human-reviewed* integration, not a capability we claim to have shipped here.

The proposed future stages are:

- Typed prompt/tool-routing recipe populations and a multi-objective fitness function for real agent tasks.
- An independently provisioned evaluation sandbox for candidate source patches, isolated from secrets, internal systems and production devices.
- Variation operators (mutation + crossover) supplied by optional LLM adapters; strict limits on tokens, cost, experiments and tool budgets.
- Genuine fresh evaluation data, independent canary tests, ablations and replay before a human reviews any source-code PR.
- A signed evaluator outcome journal and tenant-authenticated memory source. Memory poisoning cannot become a permission or safety policy.
- Repeated independent experiments to establish whether the system **actually** improves on frozen heldout tasks; publish regressions and no-improvement results.

Sources: [DeepMind AlphaEvolve explanation](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/), [AlphaEvolve technical report](https://arxiv.org/abs/2506.13131), [Google Cloud AlphaEvolve API](https://docs.cloud.google.com/gemini/enterprise/docs/alphaevolve/reference-guide/api-reference).

## Second research domain: WorldCore parameter evolution

To ensure recursive research is not limited to search weights,
`src/nerve_awim/worldcore_recursion_v19.py` also runs a typed
multi-generation experiment over WorldCore's two existing parameters:
`max_missing` (bounded 2–12) and `risk_aversion` (bounded 0–2).

```bash
PYTHONPATH=src python -m nerve_awim.worldcore_recursion_v19
```

Research operators cannot change the simulated plant, seeded data,
evaluator, safety thresholds, abort penalties, holdout episodes or
production controllers. Candidates are evaluated by parallel trusted
local worker handlers. Any candidate that fails the independent
`autoresearch_v05.eligibility` absolute rules, worsens completion,
aborts, constraint violations, prediction error, or fails to strictly
improve goal error is rejected. A final independently measured holdout
must pass the same absolute gate and non-regression checks.

The six-hour GitHub workflow runs **both domains**, archives both
research JSON reports and resumes only the bounded retrieval recipe
population from versioned public GitHub Actions artifacts, with cache fallback. WorldCore
simulation generations are rerun from a fixed baseline each time;
no unvalidated control recipe is persisted as an operational setting.

If no admissible controller is found, the correct result is
`no_deployable_improvement`. That is **not a failure of the safety gate**;
it is evidence that the frozen research constraints refused promotion.
Even `candidate_for_human_review` is not permission to change a clinical
or physical device protocol. The WordCore track is synthetic research.
