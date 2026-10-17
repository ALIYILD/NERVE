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
Execution and test results are pending the shared CPU test lock.
