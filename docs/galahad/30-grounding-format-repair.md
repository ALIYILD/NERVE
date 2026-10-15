# Grounding format repair — second bounded cycle

The first guarded real-model study blocked four wrong-object answers but unnecessarily withheld two supported answers formatted as `CODE, source_id: SOURCE`. The opt-in `GroundedRegistryAdapterV2` accepts exactly this additional punctuation form, then applies the existing entity, code, citation, evidence and authorization checks. It records normalization explicitly and preserves the raw response captured by the research harness. V1 source and evidence remain unchanged.

The second study freezes four new cases before eight local-model calls. Its independent answer-contract evaluator accepts the same narrow comma form. It compares raw versus V2-filtered versions of each same completion; there is no new-case V1 baseline and no model-weight or outcome-policy learning in this study. Historical V1 results are not rescored as fresh evidence.

## Results

All **8/8 real requests completed**. The raw model met the frozen answer contract on 3/8; V2 met it on 8/8 (4/4 supported answers with citations, 4/4 unsupported controls abstaining). One missing citation was explicitly supplied from approved evidence. Three relevant comma-form responses were accepted after the narrowly defined normalization. [Full raw and guarded responses](evidence/grounded-registry-v2.json).

Model identity and all source hashes matched before/after; SQLite matches the exported evidence. The pinned qwen2.5-coder:1.5b CPU model used 2,310 prompt and 154 completion tokens. Measured request-wall time totaled 254.132 seconds, plus 4.129 seconds for preload. No retries or source changes occurred. No speedup or general accuracy claim follows from these four synthetic cases.

Before the run, all 22 V2 guard/benchmark tests passed, including rejection of wrong codes, invented citations, extra assertions and changed authorization. The final complete repository suite passed **1,261 tests**, zero failures/errors, in 65.388 seconds.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_grounded_registry_v2.py \
  --database /private/tmp/nerve-grounded-registry-v2.sqlite \
  --run-id grounded-registry-v2 \
  --output /private/tmp/nerve-grounded-registry-v2.json \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

Use fresh output/database paths for replication and preserve consumed attempts. These public synthetic cases do not establish broad scientific or clinical reasoning capability. The guard validates selected evidence only and remains separately opt-in; normal service defaults are unchanged.
