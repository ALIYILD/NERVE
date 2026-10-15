# Experience store and AWIM learning boundaries

Loop 37 now has an executable synthetic experience journal and a trusted importer
for the sixteen recorded scientific validation outputs. The actual import and
fresh-process resume passed without inference. This completes that historical
import milestone, not all of Loop 37 or Tier 6, and establishes no new model gain.

## Implementation and reuse

`memory_gateway/experience_store.py` reuses the existing Memory Gateway's
host-issued scoped capabilities. Reads require read permission; appends require
propose permission. It does not create approved facts or reward records. The
SQLite journal binds its tenant/agent/session scope, validates canonical payloads,
indexes and a complete hash chain, and rejects updates/deletes through triggers.
Batch inserts are atomic; exact repeats do not rewrite the journal. Conflicting
identifiers fail the entire batch. Bounds limit rows, batch size and storage.

Private files and directory permissions are enforced. Missing stores return no
data; corruption reports degraded status and refuses writes. Only an explicit
fresh initialization creates a store. The importer refuses to reconstruct a
missing database when prior authority or output artifacts exist. Revocation is
checked again before returning data or committing an append. Concurrent append
fixtures preserve one chain.

Exports have deterministic JSONL bytes and a rolling-hash manifest. An interrupted
publication can resume only a byte-exact private payload with a missing manifest,
or a byte-exact private pending report. Corrupt, public or symlinked files are not
silently repaired. These are fixture-tested interruption paths, not a claim of
power-loss testing on every filesystem. Hashes detect partial/accidental tampering;
a privileged host rewriting all state remains outside this protection.

`scientific_episode_import.py` validates the completed historical receipt, its
fixed sixteen-call roster, outputs, scores and source pins before import, before
export and before completion. Policy identity includes model/runtime protocol.
It preserves raw output and separates format compliance from synthetic answer
agreement: malformed output has unknown evidence agreement. Historical timestamps
and real-world outcomes remain null. A synthetic marker is a trusted importer
assertion, not a PHI detector. This export path is not authorized for patient data.

## Validation

Full regression: **1,883 tests passed in 174.557 seconds**, including 15 store
and 18 importer tests. Independent review reran all 33 new tests and checked the
actual artifacts read-only. [Test evidence](evidence/scientific-episodes-v2-tests.json).

## Actual evidence

Final current-source store:
`/Users/aliyildirim/nerve-research-runs/scientific-episodes-v2`.
An earlier `scientific-episodes-v1` import remains untouched as pre-hardening
historical evidence; neither import initiated model calls.

- 16 imported outputs from 8 paired tasks; 0 new model, metadata or preload calls.
- Candidate conflict/non-abstaining query returns exactly 2 failures:
  `Poplar|mass|20.1|mg|validation-m` and
  `Alder|volume|23.8|mL|validation-p`.
- A fresh process with inference/metadata/preload calls forbidden repeated the
  import and preserved journal, report, JSONL and manifest bytes and modification
  times. Original validation database and call-claim journal also stayed unchanged.
- No rewards, approved knowledge, model weights or active policies were changed.
- Existing validation remains candidate 2/8 versus baseline 4/8 exact answers;
  baseline retention is still the result. Importing failures is not improvement.

Evidence: [import receipt](evidence/scientific-episodes-v2-import.json),
[synthetic episodes](evidence/scientific-episodes-v2.jsonl),
[export manifest](evidence/scientific-episodes-v2.jsonl.manifest.json), and
[fresh-process verification](evidence/scientific-episodes-v2-verification.json).

## AWIM mapping and remaining work

| Phase | Current evidence | Remaining work |
|---|---|---|
| Sense | Sixteen synthetic historical outputs stored with provenance | Live outcome ingestion, signed clinical outcomes, device analyzers |
| Understand | Queryable failure classes and separate format/evidence fields | Learned clustering, calibrated abstention, drift sensing (43.3) |
| Act | Existing scoped orchestration and guarded policies | New scientific skill routing and evaluated canaries |
| Learn | Existing bounded candidates, controls and baseline retention; protected task bank | Powered fresh-task gains, evidence-linked skill retention, governed weight learning |
| Adapt | Existing bounded synthetic adaptation experiments | Site-specific signed evidence, cross-site skill propagation (43.4), search-space expansion (46) |

The supplied AWIM mapping adds 43.3, 43.4 and 46 beyond the saved Loops 36–45
plan. They are tracked requirements, not implemented capabilities. New modalities
need specific analyzers/evaluators; shared journal machinery alone does not prove
modality-independent scientific reasoning. Learned digital twins remain separate
future work. Patient-facing promotion still requires the separately approved
workflow and responsible human authorization.

The task bank plus a GPU host would enable experiments. Demonstrable improvement
requires gains on appropriately independent tasks, retained lessons, and verified
adaptation. A GPU endpoint and compute budget remain unavailable. Galahad licensing,
GPU compatibility and durable KV restoration remain unverified. No deployment or
clinical training is claimed.

## Reproduction

From the repository root (the completed historical validation receipt is required):

```bash
PYTHONPATH=src .venv/bin/python scripts/import_scientific_episodes.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-episodes-v2 \
  --validation-directory /Users/aliyildirim/nerve-research-runs/scientific-interface-validation-v1 \
  --validation-journal /Users/aliyildirim/nerve-research-runs/scientific-interface-validation-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_experience_store.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_episode_import.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

The unit tests use temporary synthetic fixtures. They work without the private
historical database, GPU, remote service or model. Full-suite validation is recorded
in the accompanying test evidence. No pull request, push, merge or release occurred.

To independently query the imported failures through the host-scoped gateway:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from nerve_awim.memory_gateway import scientific_episode_import as imp
root = Path('/Users/aliyildirim/nerve-research-runs/scientific-episodes-v2')
gateway, _, _, _, reader = imp.pilot._state(root / 'authority.sqlite')
store = imp.ExperienceStore(root / 'experiences.sqlite', gateway, imp.SCOPE)
rows = store.query(reader, stratum='conflict', candidate_id='trusted_task',
                   failure_class='conflict_non_abstaining')['episodes']
assert len(rows) == 2
for row in rows:
    print(row['episode_id'], row['output'])
PY
```

This is a trusted local host command, not a remote authentication endpoint.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
