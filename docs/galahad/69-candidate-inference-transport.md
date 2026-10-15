# Candidate inference transport

`scientific_candidate_transport.py` connects the bounded candidate executor to
NERVE's existing `LocalInferenceAdapter`. The endpoint is fixed to literal
loopback, the host-selected local model remains fixed, and the CPU research
limits remain 128 output tokens and a 90-second socket timeout. This is not a
new remote API, clinical deployment or GPU compatibility claim.

## Request and authority contract

The adapter checks the exact parent HTTP method, URL, headers, bounded payload,
model, temperature, streaming flag, token limit and original messages before
rewriting the system instruction to the prepared candidate contract. Selected
evidence remains serialized data in the user message. An explicit constrained
mode adds only the generic JSON schema; unsupported constraints fail without a
plain-output retry. The smoke probe uses unconstrained mode, so it cannot prove
runtime schema enforcement.

The existing client supplies no-proxy/no-redirect behavior, response-size bounds,
model/finish-role/tool-call validation, capacity limits and its circuit breaker.
A separate nonblocking transport slot prevents per-call bindings from mixing.
The callback returns actual complete token usage or fails; deterministic conflict
abstention never initializes transport and reports usage null. Missing or
inconsistent extra usage fields fail after the parent response validator and do
not increment the inherited circuit breaker. The one-attempt host budget remains
mandatory; no broader circuit coverage is claimed.

The executor's authorization and immutable-input checks surround the model call.
The caller must supply source/permission revalidation; payload hashes alone grant
no authority. The smoke host uses synthetic evidence proposed and approved through
the existing scoped gateway, then re-retrieves it before exposing a result. Nothing
here approves a clinical workflow or converts model output into trusted facts.

## One-attempt smoke protocol

The separate smoke runner defines one fresh synthetic supported measurement query
and a decoy. It selects the registered conflict-check configuration, which must
route this nonconflicting example to the model. No task bank, development answer
file, holdout or private seed is read.

An external shared journal and private local state bind the protocol before any
network operation. Exactly one model attempt, one preload, two metadata checks and
two runtime-version checks are budgeted. Existing incomplete claims are consumed;
failed or interrupted work is not silently restarted. Successful receipts require
matching pre/post model digest and runtime version, complete measured token usage,
fixed response bindings and independently recomputed formatting/exact-answer scores.
Failed attempts preserve their status without creating negative efficacy records.

A completed response is still one transport probe, not evidence of improved
scientific performance. A timeout or other infrastructure failure is not evidence
that the candidate is ineffective. Comparative evaluation and retention remain
separate requirements.

## Validation boundaries

Transport unit tests use fake opener responses and verify exact outbound requests,
wrong-model/tool/finish/size/usage rejection, constrained-mode failures without
retry, revoked access, circuit behavior and binding isolation. Smoke-run unit
tests use explicit mocked transport/metadata. Actual runtime evidence is recorded
separately below when available.

## Actual runtime evidence

The probe completed one real call to `qwen2.5-coder:1.5b`, with immutable digest
`d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`
and Ollama `0.20.2` verified before and after. Preload took 3.433 seconds; the
transport interval took 78.891 seconds and reported 526 prompt tokens, 127
completion tokens and 653 total tokens. These are one-sample CPU measurements
without a comparison baseline, not a speedup or representative latency estimate.

The raw output copied a schema-like object into a JSON code fence. Inside its
`properties` object it included `32.6`, `mg` and `smoke-candidate-a`, but failed
the required top-level response shape and entity convention. Schema validity,
format validity and strict correctness were all false. We do not equate malformed
output with a separately established factual error. No repair/parser relaxation
was applied to turn this result into success.

The transport and accounting succeeded; the task contract did not. No efficacy
rejection, skill, reward or policy promotion was written. The historical sixteen-
episode importer does not yet automatically ingest this new smoke receipt.

A fresh process disabled metadata, preload, runtime-version and transport calls,
then reopened the completed receipt. Five checked files retained identical bytes
and modification times. No extra network calls or task-bank access occurred.
[Actual receipt](evidence/scientific-candidate-transport-smoke-v1.json),
[restart verification](evidence/scientific-candidate-transport-smoke-v1-verification.json).

The full regression passed **1,970 tests in 167.376 seconds**, including 26 new
transport/smoke tests; independent review reran all 26.
[Test evidence](evidence/scientific-candidate-transport-v1-tests.json).

## Remaining work

The preregistered matched development study, statistical comparison, sealed holdout,
verified study-to-rejection ingestion, skill retention and full unattended conductor
remain incomplete. The requested GPU host/budget, Galahad licensing/compatibility
and durable KV restoration are still unverified. No neural weights or active
clinical policies are changed; nothing is deployed, pushed or merged.

## Reproduction

The CLI performs one real local attempt on a fresh shared claim. On an existing
terminal claim, it only validates and returns its recorded result. It does not
retry failed attempts. No remote endpoint or patient data is involved.

```bash
PYTHONPATH=src .venv/bin/python scripts/smoke_scientific_candidate_transport.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-transport-smoke-v1 \
  --journal /Users/aliyildirim/nerve-research-runs/scientific-candidate-transport-smoke-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_candidate_transport*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

CPU regression testing and real inference should run separately to avoid creating
an unnecessary competing workload on this laptop.
