# Synthetic registry grounding repair

The preceding real-model study found four wrong-object answers in four irrelevant-evidence controls. The optional `GroundedRegistryAdapter` now checks the exact relationship between a host-selected registry object and its approved evidence before returning an answer.

`RegistryGroundingTask` contains only the requested object identifier, never an answer key. Its exact query must match the memory request. The wrapper reuses the real local inference adapter, rechecks scoped authoritative retrieval after the call, rejects altered or revoked evidence and accepts only a narrow registry grammar. Wrong objects, codes, invented citations, conflicting selected records and additional claims cause fixed abstention. A missing citation can be added from the matching approved source; this correction is explicitly recorded as host canonicalization.

This is deterministic system-level validation, not a general semantic verifier or model learning. It inspects selected records only; it cannot detect a conflicting record omitted by retrieval. Unsupported formatting can cause conservative abstention. No network service defaults or clinical permissions are changed.

## Fresh experiment

Four fresh synthetic cases, each relevant/control, use eight real local completions. An independent frozen evaluator checks the raw and guarded versions of each **same completion**, requiring the correct entity/code/citation or an allowed abstention. Full raw responses are retained in the research artifact. Model identity and source hashes are verified before and after; first failure consumes the run with no retries.

All **8/8 requests completed** on the pinned local qwen2.5-coder:1.5b CPU model, Python 3.10.0, macOS 26.5.2 x86_64. Model identity and implementation hashes matched before/after; the SQLite checkpoint equals the exported report. [Complete protocol, raw responses and guarded responses](evidence/grounded-registry-v1.json).

| Frozen contract result | Raw model | Guarded system |
| --- | --- | --- |
| Relevant code and citation | 2/4 | 2/4 |
| Irrelevant-evidence abstention | 0/4 | 4/4 |
| Total | 2/8 | 6/8 |

Manual inspection: all relevant raw outputs contained the correct code and source, but two used a comma before `source_id`. The strict frozen grammar rejected those, so the guard unnecessarily abstained on two supported answers. All four control responses returned a decoy code; the guard replaced them with abstention. No missing citations were added in this run. Thus this is an observed system filtering improvement on four controls, with a known usability defect; it is not a 75% estimate of general accuracy or learned model improvement. The next repair must address citation punctuation without accepting extra assertions, then use fresh validation rather than relabel these results.

Eight requests used 2,304 prompt and 171 completion tokens, taking 220.439 measured request-wall seconds, plus 4.501 seconds for preload. CPU contention, runtime prefix caching and tokenizer lengths were not controlled for performance attribution. No speedup, first-token, GPU-energy, monetary-cost or KV-restoration claim is made. No prompt, evaluator or guard source was changed during this execution.

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_grounded_registry.py \
  --database /private/tmp/nerve-grounded-registry-v1.sqlite \
  --run-id grounded-registry-v1 \
  --output /private/tmp/nerve-grounded-registry-v1.json \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

For reproduction use unused database/output paths. Model installation, exact digest and local loopback permissions are required. Reusing these published questions is replication, not fresh evaluation.

Full repository regression after the real study: **1,228 tests passed**, zero failures/errors, 72.043 seconds.
