# Runpod slice 2 — frozen v3 at 7B

This is the user-authorized, versioned remote execution of the existing slice-2
rule. It does not install a skill, supersede an incumbent, or supply a human
signature. Work stops at the verdict. The existing historical gates and receipts
are unchanged.

The substrate is pod `lg0svvuenxvbno`, measured NVIDIA A40, Ollama 0.40.5,
`qwen2.5-coder:7b`, immutable model digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
The pod remains running. Inference is denied on Darwin; Linux and the explicitly
bound pod ID are required. The pod ID is supplied to the remote SSH command
because the SSH shell does not inherit Runpod's container environment. It is an
execution guard, not cryptographic remote attestation.

## Frozen configuration and admission

The script uses the original preparation, deterministic routes, seeded random
control, ordering and scoring from commit `cb65c81`. Every original development
Python source hash was matched. The 100 development tasks recreate exactly the
400-entry schedule and request payloads in the Runpod development registration:
seed 20261015, temperature zero, maximum 128 output tokens, identical prompts,
JSON schema and abstention rules. The earlier complete 7B receipt was replayed
with zero additional calls before registering this run.

The measured maximum Runpod development call latency was 13.329198110848665 s.
Every model arm uses exactly three times that global maximum:
39.987594332545996 s per attempt. At most two identical-request resends follow
transport timeouts only. Every attempt has a durable claim before dispatch and a
terminal record containing elapsed time and outcome. HTTP/parser/identity errors
are not retried. A timed-out server operation may continue; this is not an
exactly-once server-execution guarantee. No preload or timeout extension was used.

The same frozen harness completed the dry run with 400 arm rows, 160 logical
calls, 160 physical attempts and zero timeouts in 150.39458256587386 s.
Its allocated cost estimate is $0.024648001031629327. Slice-2 registration binds
the verified dry receipt, implementation, runtime and original slice manifest.
A private one-use export marker was created before opening slice 2; its bytes
were hash-checked, copied into private gate storage and immediately resealed.
The original combined holdout, slice 1, reserve and bank seed were not opened.

The Runpod live inventory read quoted $0.59/hour for this existing pod. Reported
costs allocate that rate to measured run wall time; they are estimates, not an
invoice or total evening spend. Replay, preparation and idle time are excluded.

## Interpretation and evidence boundary

The fixed acceptance rule requires a complete evaluation, candidate strict total
above each control, and no candidate stratum below always-abstain. Intervals are
95% marginal Wilson intervals, descriptive rather than a multiplicity-adjusted
significance test. Only aggregate strata are exported. Raw requests, responses,
item identities, expected answers and scores remain gate-private; the final
storage-permission correction is recorded below.

The incumbent comparator is precisely the frozen compact-with-abstain pipeline
from the Runpod development study. Its earlier development errors were largely
format-invalid. Any advantage here is evidence about the complete output-contract
and rule pipeline, not a matched improvement in underlying model reasoning.
Multi-source agreement and stale-vs-current remain untested. This is synthetic
instance generalization using the existing generation templates.

Nine focused CPU tests cover local inference denial, identical timeout retries,
non-timeout failure, retry ceiling, incomplete verdict, Wilson endpoints,
reference-source mismatch, wrong slice manifest and failed dry admission.
Full-suite results belong to the separate outcome-release workstream.

## Verdict and stop

**`promote_proposal` — awaiting the user’s explicit signature.** No skill was
installed and no incumbent superseded. No robustness run, bank-v2 generation or
v4 work was started.

| Stratum | v3@7B | Incumbent@7B | Always abstain | Random |
|---|---:|---:|---:|---:|
| conflict | 20/20 (83.9–100.0%) | 0/20 (0.0–16.1%) | 20/20 (83.9–100.0%) | 7/20 (18.1–56.7%) |
| entity-decoy | 20/20 (83.9–100.0%) | 0/20 (0.0–16.1%) | 0/20 (0.0–16.1%) | 4/20 (8.1–41.6%) |
| measurement-decoy | 20/20 (83.9–100.0%) | 0/20 (0.0–16.1%) | 0/20 (0.0–16.1%) | 12/20 (38.7–78.1%) |
| supported-measurement | 20/20 (83.9–100.0%) | 0/20 (0.0–16.1%) | 0/20 (0.0–16.1%) | 9/20 (25.8–65.8%) |
| unit-mismatch | 20/20 (83.9–100.0%) | 20/20 (83.9–100.0%) | 20/20 (83.9–100.0%) | 8/20 (21.9–61.3%) |

Parentheses contain 95% Wilson intervals. Slice 2 completed all 400 arm rows
with 160 logical calls, exactly 160 physical attempts and zero timeouts in
138.62984653934836 seconds. Allocated slice cost estimate: $0.02271989151617098;
combined dry-run and slice allocation: $0.0473678925478003.

The `format_valid` aggregate field counts only `score.schema_valid is True`,
meaning JSON-schema-valid responses; it does **not** measure generic format
validity for abstention and plain-text baseline/control outputs. Strict accuracy
and its intervals above use the frozen scorer and are unaffected.

Both receipts replayed on the pod; the downloaded private slice receipt also
replayed locally with zero inference. Public evidence consists only of frozen
registrations and aggregate counts/intervals. Private receipt and archive are
under `/Users/aliyildirim/nerve-research-runs/runpod-slice2-20261015/`, and remote
private evidence is under `/root/nerve-slice2-20261015/`. Original sealed
slices and combined holdout remain mode 000; private study directories are 0700.
The final Runpod read confirms the pod remains running.

The final audit found that Runpod’s `/workspace` mount reported mode 0777
despite requested 0700 permissions. After execution, this run’s entire private
remote directory was moved to pod-local `/root` storage, actual 0700 directory
and 0600 file modes were verified, and its former `/workspace` location was
confirmed absent. Local extracted evidence permissions were likewise explicitly
enforced. No evidence was published or committed while correcting storage.
Frozen source and receipt contents were unchanged.
