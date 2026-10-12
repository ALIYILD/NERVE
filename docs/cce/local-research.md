# Local model research and frozen datasets

The optional local adapter uses an already installed Ollama model for bounded
instruction-cue experiments. It does not download models, call a remote API,
attest the production Hermes worker or reproduce the paper's response-prefix
experiment. It preserves NERVE's existing experiment and report contracts.

Inspect the installed model before running inference:

```bash
PYTHONPATH=src python3 -m nerve_awim.cue_cli local-inspect \
  --model qwen2.5-coder:1.5b \
  --digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

This digest identifies the model installed on the implementation host; another
installation must supply its own observed immutable manifest digest. The adapter
checks local artifacts and serving metadata. Model names alone are not pins.

The smoke command performs exactly four generation attempts over two fixed public
arithmetic tasks, alternating no-cue and instruction-cue order:

```bash
PYTHONPATH=src python3 -m nerve_awim.cue_cli local-smoke \
  --model qwen2.5-coder:1.5b \
  --digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 \
  --allow-local-inference --output /tmp/nerve-cce-local-smoke.json
```

The installed bridge exposes equivalent `cce-local-inspect` and `cce-local-smoke`
commands with `--cue-model` and `--cue-model-digest`. Smoke execution additionally
requires `--allow-local-inference`. Results go to the existing host state directory;
no candidate is approved or installed in an operational route.

The first real execution stopped without a complete receipt. After adding sanitized
diagnostics, a second run recorded four attempted calls: three measured receipts,
two truncated responses, and a timeout on the fourth call. Its
[retained failure receipt](local-smoke-failed.json) is incomplete and contains no
scored report. Its token totals cover the measured receipts only. This exposed a
transport setup problem: the generic raw prompt omitted the installed instruction
model's chat boundaries. The follow-up pins a supported Qwen renderer and reduces
the smoke output cap from 96 to 32 tokens; these are separate transport runs, not
repeated holdout evidence or a demonstrated cue improvement.

The [repaired local run](local-smoke.json) completed all four calls with zero
errors/truncations and full usage coverage: 184 input tokens and 12 output tokens.
Each arm answered both tasks correctly (2/2), with zero accuracy delta. Promotion
was rejected for insufficient pairs, no gain, weak paired evidence, missing
calibration and no independent approval receipt. The latency difference includes
model warm-up and host verification on only two tasks; it is not evidence of a
performance benefit. Local compute cost remains unmeasured.

Model-generated observations are measured inference, even though the task set is
small and artificial. Output confidence is unavailable and stays null; Brier
score is unavailable and promotion fails with `missing_calibration`. The grader
checks only an exact integer and arithmetic correctness for these two tasks.
This is not a general safety classifier. Token counts come from actual serving
receipts. Zero external provider fees exclude unmeasured local electricity and
hardware costs. Two pairs cannot establish model effectiveness.

## Frozen benchmark input

`cue_dataset.load_dataset(path)` validates a bounded local JSON file. The strict
schema is documented in that module. It requires dataset identity, source URI and
revision, and discovery/selection/holdout tasks with task ID, family ID, instruction
and expected answer. Duplicate task IDs/content and family overlap between splits
are rejected. Family annotations remain a host responsibility; labels do not prove
semantic independence. Source revision strings are recorded, not authenticated.

```bash
PYTHONPATH=src python3 -m nerve_awim.cue_cli inspect-dataset /path/to/frozen.json
```

Inspection prints only digest, source and partition metadata. Pass the returned
manifest to discovery; keep expected answers in trusted host graders. The existing
`run_experiment` accepts the resulting task tuples. No arbitrary dataset receives
the arithmetic smoke grader automatically.

## Durable research reservations

For governed research, use `CueHost.run_dataset_cycle(profile, dataset, ...)`
with a loaded dataset and the same trusted callbacks/budgets as `run_cycle`.
It validates the complete frozen object again, binds the actual selection and
holdout tasks, and atomically reserves IDs, stripped instruction hashes and
declared family hashes before invoking discovery. Candidate summaries and release
readiness retain the dataset digest; raw instructions and answers are not stored
in the reservation tables.

The first successful reservation upgrades that tenant/agent scope to dataset-bound
evidence. Later ID-only studies cannot downgrade it. Legacy candidates cannot be
evaluated, approved or served after the upgrade; selection falls back to no cue
while existing audit records remain intact. Collect fresh bound evidence rather
than attaching new metadata to an old approval. The upgraded protection survives
restart and contract revisions. Inspect its counts without a provider call:

```bash
python3 scripts/agentos_bridge.py cce-dataset-status --profile qa-release
```

Previously reserved holdout content or families cannot be reused in any partition,
even when IDs, source metadata, expected answers or other labels change. Discovery
and selection content may recur only in the same partition. Failed discovery does
not release reservations; conflicting reservations roll back atomically.

This protection is per tenant/agent, not a global cross-agent corpus registry.
Historical ID-only studies lack enough data for content backfilling. Semantic
paraphrases with changed family labels remain a host curation responsibility.
The two-task local transport smoke is deliberately separate from this governed
cycle and cannot satisfy its untouched-holdout gate.

## Retained-capability screening

Schema 2 adds a required nonempty `regression` array alongside discovery,
selection and holdout. Each entry uses the same task fields. Task IDs, instruction
content and families must remain disjoint across all four partitions. Schema 1
and historical report digests remain supported for scopes that have not upgraded.

The dataset-bound cycle budgets every call before discovery, then runs selection,
regression and the untouched holdout in that order. Regression requires an
independent evaluator receipt, measured nonsynthetic outcomes, no loss of any
previously correct paired answer, safe candidate outcomes, available nonworsening
calibration, and nonworsening mean/p95 latency and provider fees. Improvement on
other examples cannot cancel a lost capability. These are conservative screening
rules; reusable regression results do not establish unbiased effectiveness.

The first regression reservation upgrades its tenant/agent scope. Later studies
cannot omit the gate, including across contract revisions. Older candidates fall
back to no cue until fresh qualifying evidence is collected. The coordinator
persists the regression verdict before accepting holdout evidence and checks it
again during approval and selection. Release readiness independently recomputes
its verdict and bindings. A passing gate never grants deployment or clinical
permission. Reuse is permitted only within the regression partition; holdout
content remains reserved even when screening fails.

No real retained-capability benchmark has been run by this implementation. Hosts
must curate representative tasks, authenticate graders and collect actual model
receipts before relying on this gate operationally.

## Serving limitations and sources

Ollama's generation response identifies a model name, while its model inventory
and running-model APIs expose digests. Surrounding identity checks are observations,
not cryptographic per-response attestations. Embedded GGUF tokenizer identity also
does not prove equivalence to a Hugging Face tokenizer or exact boundary token IDs.
See the official [generation API](https://docs.ollama.com/api/generate),
[model inventory](https://docs.ollama.com/api/tags),
[running models](https://docs.ollama.com/api/ps),
[model metadata](https://docs.ollama.com/api-reference/show-model-details), and
[GGUF tokenizer specification](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md#tokenizer).

## Scheduled research admission

The bridge accepts immutable CCE jobs through `cce-job-submit --task` and reports
them through `cce-job-status`. The existing autoresearch tick handles one eligible
job under its host lock and calls `CueHost.run_dataset_cycle`; it does not create
a second agent architecture. Scheduled jobs require schema 2 data, explicit
research permission and a complete discovery/selection/regression/holdout budget
(at least 65 calls for the smallest permitted partitions). The host must supply
the registered discovery, provider and grader callbacks; task JSON cannot import
them. Missing adapters wait without inference. Interrupted execution is not
replayed and never resets consumed dataset reservations.

The local smoke adapter is not installed as a scheduled research adapter. Its
confidence remains unknown, it has no discovery callback, and it cannot attest
the production worker. Its measured arithmetic result does not satisfy calibration
or representative handoff/regression evidence requirements. Neither local smoke
nor queued job admission approves a cue.

## Historical feedback as discovery input

The governed cycle can freeze a scoped snapshot of `trusted_evaluator_feedback`
before asking the existing research callback for a new cue. Only revalidated cue
text/content hashes, approved/revoked state and bounded aggregate outcome counts
reach discovery. The snapshot excludes candidate IDs, task/episode identifiers,
answers and heldout metrics; limits are eight candidates, 64 observations each
and 8 KiB. An empty snapshot leaves the historical request contract unchanged.

These rows are evaluator observations, not proof of operational application or
a causal cue benefit. Existing records do not bind each outcome to an actual
worker application receipt. Historical cue text remains untrusted data, and its
safety check does not grant authority. The audit keeps only a snapshot digest
and aggregates. Fresh dataset reservations, regression screening, independent
evaluation and operator approval remain mandatory for new candidates.

Historical `cue_digest` is SHA256 of the exact UTF-8 cue text, not the
metadata-bound `Cue.content_hash` used by experiment receipts. Duplicate text
keeps only the most recent eligible candidate's latest 64 observations; counts
are not pooled across versions. The snapshot digest binds the frozen in-memory
discovery invocation. No full snapshot is retained for later reconstruction.
Cue safety validation is a bounded instruction filter, not a privacy classifier;
hosts must keep sensitive data out of historical cue text.
