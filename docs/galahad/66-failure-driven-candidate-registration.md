# Failure-driven candidate registration

NERVE now turns the historical experience journal into bounded, hash-bound
scientific hypotheses. This is executable CPU groundwork for Loops 39.1–39.2.
Loop 36's powered evaluator remains incomplete, so these are **unevaluated
proposals**, not results from a completed Tier-6 learning cycle.

## Behavior

`scientific_candidates.py` reads only scoped episode evidence through the existing
ExperienceStore. It clusters failures by stratum and failure class, prioritizes
conflict/non-abstaining failures, and selects from four fixed data configurations:
conflict detection, output-contract emphasis, larger retrieval coverage, and an
evidence-sufficiency check. Each configuration contains a boolean pre-step flag,
an allowlisted prompt-template identifier, bounded retrieval count, enumerated
abstention rule and evidence-only tool rule. Arbitrary code, commands and prompt
text are not accepted. These configurations still need an execution adapter and
a preregistered evaluation protocol; their names do not prove implementation of
the corresponding inference behavior.

The generator is a deterministic rule-based proposer, not a newly trained research
model. No caller instruction is needed to choose conflict detection from the
recorded conflict failures. Disabled research mode honestly enumerates the fixed
space. An empty or all-success journal produces no proposals. Access denial is
not converted into a fallback that exposes data.

Candidate hashes bind configuration alone. Hypothesis hashes additionally bind
the cluster's episode IDs and payload hashes, source versions, journal head,
predicted effect and anticipated regression stratum. Changing evidence does not
change the candidate identity. Validation rechecks current authorized evidence
and requires the mutation to match its failure rule in deterministic mode.
Enumeration is explicitly distinguished. A hash is an integrity reference, not
an independent signature or proof that a hypothesis is correct.

`scientific_candidate_registration.py` verifies the completed sixteen-output
import, generates and validates proposals, then publishes a private deterministic
report. It reuses the existing importer, scope checks, exclusive lock and exact
publication/recovery helper. Missing original data is not initialized. Changed
source, evidence, output or configuration fails closed. Reopening the same
registration never dispatches inference. Authority metadata retains the existing
ledger's file mode inside its private 0700 directory; episode/export/report files
remain 0600.

The existing successful-outcome skill proposal API is intentionally not invoked:
it requires 3–20 successful approved references. Two negative conflict episodes
cannot satisfy that contract. Prior scientific inference modules and source-pinned
receipts remain unchanged.

## Actual registration

The real sixteen-output journal produced three proposals:

| Mutation | Selected failure cluster | Episodes | Interpretation |
|---|---|---:|---|
| Conflict check | conflict / conflict_non_abstaining | 2 | Test conflict handling; monitor false abstention on agreeing sources |
| Format contract | entity_decoy / format_failure | 1 | Test output contract emphasis; monitor supported answers |
| Evidence coverage | entity_decoy / supported_abstention | 3 | Speculative retrieval hypothesis; the failure does not prove retrieval was the cause |

The conflict configuration hash is
`3a541718149f7c5c0b203f6d7488897f93b04975e4e52b2aa89761b42f79a0d8`.
It links exactly the Poplar and Alder candidate failures from the original
validation. No new model calls were made. A separate disabled-mode run registered
all four fixed candidates as enumeration fallback, not failure-driven findings.

A fresh process reran the main registration while model response, metadata,
preload and protected task-bank/seed opens were forbidden. It preserved report,
episode database/export and original validation database/claims bytes and
modification times. The generator did not consume development or holdout items.

Evidence: [main registration](evidence/scientific-candidates-v1.json),
[enumeration fallback](evidence/scientific-candidates-enumeration-v1.json), and
[fresh-process verification](evidence/scientific-candidates-v1-verification.json).

## Validation

Full regression: **1,902 tests passed in 163.982 seconds**, including 19 new
candidate/registration tests. Independent review reran all 19 tests and verified
the actual proposal artifacts read-only. [Test evidence](evidence/scientific-candidates-v1-tests.json).

## Remaining work and boundaries

Loop 39.3's durable negative-evidence journal and near-duplicate rejection are not
implemented by this module; reports explicitly say so. A subsequent gate must
validate rejection receipts and bind exceptions to genuinely new evidence, not
renamed episode identifiers. Registration alone must never trigger repeat trials
of known rejected candidates.

Loop 40 still needs an executable candidate adapter, matched controls, development
screen, one-use independent holdout, confidence intervals and meaningful power.
No complete generate → evaluate → retain → shadow conductor is claimed here.
GPU endpoint/budget and runtime validation remain outstanding. Clinical rewards,
weight learning, skill activation, cross-site propagation and clinical deployment
remain incomplete. The actual model's last validation remains candidate 2/8
versus baseline 4/8; no new accuracy or performance advantage is asserted.

## Reproduction

From the repository root with the completed local import present:

```bash
PYTHONPATH=src .venv/bin/python scripts/register_scientific_candidates.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-candidates-v1 \
  --episode-directory /Users/aliyildirim/nerve-research-runs/scientific-episodes-v2
PYTHONPATH=src .venv/bin/python scripts/register_scientific_candidates.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-candidates-enumeration-v1 \
  --episode-directory /Users/aliyildirim/nerve-research-runs/scientific-episodes-v2 \
  --disable-research-agent
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_candidate*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Tests use synthetic temporary fixtures and need no GPU/model service. Historical
receipt validation is mocked in registration unit fixtures; the actual registrations
above revalidated real completed receipts. No push, PR, merge or deployment.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
