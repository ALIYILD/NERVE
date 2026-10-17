# Family A routing replay: historical dev reuse

The A01 routing proposal is evaluated separately from its planned fresh model
study. The original A01 registration pins model seed `20261015`; the existing
Sweden Family B v4 journal used `20261016`. Reusing those outputs cannot fulfill
A01 unchanged. Neither the original registration nor the retained skills were
modified.

`research/overnight-20261017/A01-replay-registration.json` registers a distinct
historical dev replay at seed `20261016`, before computing the new candidate's
metrics. Its SHA-256 is
`f52dbba67eb10500a5614c8348212c64fc2199d3af02392bbfb358f16cffef01`.
It retains the 100 A01-selected items, all nine strata, original controls and
keep rule. Task selection was not changed after inspecting outcomes.

The binding audit confirmed all 100 tasks exactly match the original 900-item
Sweden dev input. It checks all original executable source hashes, the complete
schedule hash, candidate prepared input and request payload, model digest and
seed, registration-bound transport claims, retry sequence and completed wire
responses. Only the genuine v4 candidate arm supplies fallback outputs.
Canonical v3's own deterministic abstention supplies the incumbent; the older
`adapted_v1` arm is never relabeled as canonical v3. The new composite router is
not a retained skill.

The runner is `scripts/replay_overnight_family_a.py`. Its register command does
not calculate correctness. Its evaluate command requires a W0 authorization
bound to the registration hash and the scope `CPU historical replay only`.
Evaluation rechecks every binding. Changed requests, inputs, executable sources
or receipt bytes fail closed. There is no inference transport call in this
runner, and it never opens holdout items or writes registry/trust.

Safety requires zero domain violations and zero errors on expected-abstain
safety items; both frozen controls remain hard gates. Results are historical dev
reuse, not fresh inference, independent confirmation or a sealed promotion.
Authorized evaluation completed under the shared CPU test lock. The registered
keep rule returns **kept: 59 wins, 0 losses, 41 ties**, zero safety errors and
strictly better correctness than both controls. A second fresh process reproduced
the same immutable result and rows. All three fail-closed unit tests passed.
There were zero new model calls and zero incremental inference cost.

Evidence: `research/overnight-20261017/A01-replay-result.json`,
`A01-replay-rows.json`, and `A01-replay-verification.json`. The historical
replay is recorded separately in `research/leaderboard-20261017.jsonl`.

Reproduction requires the exact pinned executable checkout on
`overnight/resume-a` (runner introduced at `88c84f4`), with the registration's
source hashes intact. Later ARC/governed test-runtime fixes change original
historical executable hashes and intentionally cause this replay to fail from a
merged checkout. Use this preserved worktree or an equivalent checkout whose
hashes match; do not relax the source checks to obtain a successful replay.

| Stratum | Items | Wins | Losses | Candidate correct |
| --- | ---: | ---: | ---: | ---: |
| conflict | 12 | 0 | 0 | 12 |
| dissenter | 11 | 0 | 0 | 11 |
| entity-decoy | 11 | 11 | 0 | 11 |
| format-variant-agreement | 11 | 8 | 0 | 8 |
| measurement-decoy | 11 | 11 | 0 | 11 |
| multi-source-agreement | 11 | 7 | 0 | 7 |
| stale-vs-current | 11 | 11 | 0 | 11 |
| supported-measurement | 11 | 11 | 0 | 11 |
| unit-mismatch | 11 | 0 | 0 | 11 |
