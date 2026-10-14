# Structured scientific output preflight

This is a bounded compatibility and output-contract preflight, not an efficacy or
promotion study. Two fresh synthetic tasks are paired across two output modes,
for four real completions. The implementation records raw responses and separates
schema validity, task-format compliance and answer correctness.

## Registered tasks and matched requests

`scientific_structured_tasks.py` freezes one supported mass question with an
entity decoy, and one conflicting-mass question requiring abstention. Both have
two approved records. Names, values and source identifiers are new relative to
the preceding measurement registries.

The required object has six string fields: `status`, `entity`, `measurement`,
`value`, `unit` and `source_id`. All are required; additional properties are
forbidden. Only `status` has an enum, containing `answer` and `abstain`. The schema
does not encode task-specific names, values, units, sources or answer keys.

Both `unrestricted_json` and `schema_json` receive the same registered system task,
question, serialized generic schema and approved evidence. Instructions require a
bare entity name, exact units without conversion, and abstention for any matching
conflict. An abstention must set all five non-status fields to empty strings. Only
the constrained arm adds a `response_format` JSON-schema request with `strict: true`.
The messages, model, temperature and completion budget remain matched.

`scientific_structured_inference.py` checks the original bounded request before
rewriting it. Task identifiers are whitelisted; arbitrary caller instructions
cannot become system tasks. Evidence remains untrusted user data. The adapter
retains the existing loopback transport, no-proxy/no-redirect behavior, response
validation and post-call gateway authorization checks.

Ollama documents structured output through JSON schemas and recommends including
the schema in the prompt. Its OpenAI-compatible endpoint supports the
`response_format` mechanism used here. These upstream capabilities motivate the
probe; installed-runtime compatibility still requires local evidence.
[Structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).

## Separate evaluation layers

The parser rejects duplicate JSON keys, nonfinite constants, wrong field types,
unknown status values, missing or additional fields, multiple objects, prose and
code fences. No output repair or answer substitution occurs.

- `schema_valid` checks the generic JSON shape and field types.
- `format_valid` additionally checks that abstention leaves all five other fields
  empty. The generic schema itself does not encode this conditional rule.
- `strict_correct` requires the complete parsed object to equal the frozen answer
  or abstention object.
- `unsupported_selection` is true only for a parsed answer on the task whose
  evidence requires abstention. A malformed response is not classified as a
  factually unsupported selection, and a wrong field on the supported task is
  recorded as a strict failure without this broader semantic label.

Thus an abstention with nonempty fields can be schema-valid but format-invalid.
A schema-valid answer can also name the wrong entity, value or source. Successful
serialization does not establish factual correctness.

## Execution bounds and evidence

`scientific_structured_preflight.py` permits at most four inference calls, one
preload, two model metadata checks and two runtime-version requests. Completions
use temperature zero, a 128-token cap and a 90-second socket timeout. These are
socket limits, not a hard whole-run wall-clock deadline.

The runtime version is read before and after inference from the fixed loopback
`GET /api/version` endpoint. Each lookup has a five-second timeout, reads at most
4,097 bytes and rejects a response larger than 4,096 bytes. Version strings must
match the bounded 1–80-character allowed pattern. The version and pinned model
digest must remain unchanged. Source hashes and exact evidence identities are
also verified.

The runner claims work durably before calls, stores raw outputs, measured usage,
latency and judgments, and checks completed receipts on restart. An interrupted
or failed consumed run is not permission to repeat its model calls. The shared
journal stays outside the experiment directory. No feedback utility is updated;
no weights are trained and no candidate is promoted.

## Verification and results

**1,838 regression tests passed in 166.770 seconds**, including 29 new tests.
Independent source/test review passed. The actual preflight on 14 October 2026
failed on its first `unrestricted_json` request with a sanitized `timeout` reason.
There was one claimed attempt, zero accepted output rows and **zero schema-constrained
calls**. No claim about installed structured-output support or answer accuracy can
be made from this run. The runner exited with code 1 and retained the consumed claim.

Ollama reported version `0.20.2` before and after the attempted call. The pinned
`qwen2.5-coder:1.5b` digest matched both checks; all 30 source hashes matched.
The run used Python 3.10.0 on macOS x86-64 and the CPU research profile. Preload
took 4.657 seconds. No accepted token usage or completion latency is available;
none is inferred from the timeout. No feedback utility was written.

A separate Python process attempted resume with metadata, version, preload and
inference patched to fail if called. It refused the failed receipt with
`invalid_complete_receipt`, made zero network/inference calls and preserved all
report and claim rows. Independent review confirmed the failed receipt and limits.

- [Raw failure receipt](evidence/scientific-structured-preflight-v1.json), SHA256
  `6dd4898e04d8b8435d817ee890c248c7941e3046873611b14580d89f0de8db3a`.
- [Failed-resume proof](evidence/scientific-structured-preflight-resume.json).
- [Test evidence](evidence/scientific-structured-preflight-tests.json).

The user subsequently supplied the Tier-6 self-learning plan. Its GPU substrate
requirement is now an explicit external dependency. The current laptop reports
Intel UHD 630 and AMD Radeon Pro 5500M (4 GB); no `nvidia-smi` is installed.
No GPU-backed ≥7B endpoint, throughput result or commercial resource budget is
verified. CPU-independent evaluator work can proceed without retrying this probe.

Even four valid outputs would demonstrate only those observed responses. They
would not prove that the server enforces arbitrary JSON schemas, that a schema
improves general extraction accuracy, or that NERVE has achieved reliable
self-improvement. An ignored constraint can coincidentally produce valid JSON.
This small preflight has no efficacy acceptance or promotion gate.

## Reproduction

From the repository root, after source freeze and model-digest verification:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_scientific_structured_preflight.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-structured-preflight-v1 \
  --journal /Users/aliyildirim/nerve-research-runs/scientific-structured-preflight-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

The digest was checked before and after this failed run. Preserve the original journal and
experiment directory. Repeating the same command now refuses the failed consumed receipt; changing directories or deleting journals is not an authorized
retry of consumed work.
