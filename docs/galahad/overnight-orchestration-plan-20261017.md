# NERVE overnight orchestration — 17 October 2026

Authority: Ali’s full plan supplied in the conversation. No matching 20261017 Desktop file was found; this is the execution specification transcribed from that instruction, not a claimed verbatim Desktop copy.

Schedule London: 00:45 start; 07:00 wrap-up; 07:45 hard stop; 08:00 human review. RunPod compute cap $12 (stop at $11), <=2 concurrent pods, <=12,000 calls. CPU only on laptop, one test suite at a time. Two consecutive infrastructure failures on a pod retire it; three across night trigger wrap-up. Stop pods before writing halt ledger.

Human-only signing, retention, activation, installation. registry/ and trust/ read-only. Signed protected manifest and gate/holdout/seal/verifier/test-tier/bank manifests read-only. Hash before each loop; mismatch halts affected loop with integrity reason. Register before first call; no result-driven retries, only two registered identical transport resends. Holdout exclusively through signed gate; private item outputs inaccessible outside gate. No external communication or pushes except ALIYILD/NERVE feature branches.

W0 owns L0 conductor, L1 preflight, integration, ledger/budget/signing queue and L7 reviewer/report. W1 owns L2 evaluator and L4 sealed holdouts. W2 owns L3 autoresearch. W3 owns L5 adaptation and L6 SDK. Shared state ~/nerve-orchestration; atomic pod locks before SSH/inference, test lock for laptop suites. Worker branches remain in place. Failed merges stay on worker branch, never force resolve.

L1: signed hashes and signature; bank ledger counts; fast tier; MCP inventory; orphan shutdown; canonical model digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364, five latency calls, ten historical dev identity replays. No inference until registration and pod lock.

L2: fixed m=12,14,16; zero-in-60 bound; primary300 cap1000; broad75/narrow64/measured-v5/silent5/10 profiles, registered then fresh seeds. Targets good>=80%, regressed nonpromotion>=90%, H0<=5%, harmful0. Register scope; distinguish v3 non-evaluation from G2 detection. Queue full-form payload only if qualifying, never sign. Existing doc129 at b97aabf already fails harmful0; verify rather than reroll seeds.

L3: one typed seam per experiment, 100 fresh dev items, <=240sec, <=4 concurrent. Family A bankv3 dev incumbentv3; B bankv5 dev incumbentv4 with v5 first. Up to12/family or3 consecutive reverts. Keep iff wins-losses>=6, losses<=1, safety errors0, beats always-abstain and random. Propose from recorded failures; register/run/replay/keep-or-revert; rejection memory seam+cluster. Every attempt in research/leaderboard-20261017.jsonl. Hand best candidate to L4 after2 keeps or loop stop. Optional larger substrate only at05:00 with >=$4 remaining, exploratory dev-only.

L4: broad candidates only under canonical signedv3 unless human has signed qualifyingv3.2. Fresh exclusive bank reserve allocation; registered controls/risk/caps. Replay and queue full-form promote_proposal; no activation.

L5: preregister outcome drift monitor, retained-only router, verification and rollback. 1200 dev items 300A/300B/300hardB/300A, broken served skill60 items, three shifts, switch/switch-back/rollback, kill9/resume without repeated inference. Replay real receipts where available. Same orchestrator on CPU PerfFlux/Clinical OS synthetic sandboxes.

L6: nerve_awim.loop Loop.learn/propose/evaluate/adapt/status; CLI demo for scientific/perfflux-sandbox/clinicalos-sandbox with controls and hashed receipt bundle. Document guarantees, no auto-promotion, real reward integration boundary. Tests/CI must not modify protected suite manifest.

L7: fresh independent reviewer replays all studies without inference, checks hashes/registry/trust/banks, queue full form, MCP EXITED and spend. Report D1-D8 achieved/partial/not achieved with evidence, final verified merge and allowed push.

D1 all tonight studies ingested v2, >=3 autonomous proposals/family and rejection memory. D2 >=1 dev keep/family beating incumbent and controls. D3 >=1 sealed promote_proposal queued human. D4 qualifying fresh-seed gatev3.2. D5 registered scientific drift and restart. D6 both sandbox adaptations. D7 complete SDK/demos/contracts. D8 independent verification and shutdown/spend.

All learning synthetic; real clinician sign-off and real PerfFlux workload reward remain future inputs.

## Recorded launch deviations
- Dirty local feature/galahad-persistent-memory preserved. W0 isolated at overnight/w0-orchestrator from remote b97aabf, which descends from requested1992f11. W1-W3 share that base.
- Existing doc129 is a negative v3.2 result; cannot queue a qualifying gate payload.
- Canonical signature verifies; legacy combined checker fails stale bankv4 empty-ledger assertion (100 already consumed). No bank reset allowed.
