# Overnight autoresearch evidence — 17 October 2026

Family B completed one fresh registered 100-item dev experiment: **35 wins,
0 losses, 65 ties**, beating both frozen controls, with zero observed domain
violations. Its registered verdict is **kept**. The run made 100 RunPod model
calls in 198.899 seconds. This is agreement-stratum dev evidence; negative safety
strata were not sampled, and no general safety or holdout claim follows.

Evidence: `research/leaderboard-20261017.jsonl`,
`research/overnight-20261017/B01b-registration.json`, `B01b-result.json`,
`B01b-replay.json`, `B01b-ingestion.json` in that directory. Active registration
SHA256 is `094e6058bac759f3a16824f1124b8f9fd4c5a2cacccb9c6fe84cdae5a873e568`.
The two superseded registrations remain immutable; their changes were transport
hardening before any calls, never outcome-driven design changes.

The run was reconstructed from recorded request claims/wire responses. Both arms'
200 outcomes were imported with zero inference. The generator then re-clustered
only the new dev incumbent v5's failures: none were observed, so it produced zero
next proposals. It did not invent failures to reach the requested iteration count.
The narrow B candidate is handed off as `candidate_requires_review` for a morning
gate decision; no holdout study, signing payload, retention or activation occurred.

Historical B dev evidence was separately replayed: 100 original source-pinned
rows, independently checked task truth, request bodies and win/loss aggregates.
Those 100 v4 outcomes produced two failure clusters and two proposal records of
one identical configuration. They are historical evidence, not fresh experiments
or two distinct candidate ideas. See `historical-b-import.json`.

Family A's prior 7B v3 receipt was 100/100, but that did not establish performance
on bank-v3. A registered CPU routing audit read only the archive's dev and manifest
members and evaluated canonical v3's deterministic behavior on 900 dev items:
all 900 hit `unsupported_evidence`; 300 abstentions were correct and 600 incorrect.
No item needed a model call. This exposes an input-grammar compatibility gap,
not a general estimate of v3's model ability. Evidence: `A-route-registration.json`
and `A-route-result.json`.

All 900 A audit outcomes were ingested. Six genuine failure clusters support one
new routing candidate: use canonical v3 when supported; fall back to retained
family-B v4 when v3 reports unsupported input grammar. This changes one routing
seam. Six clusters are not six novel proposals. A 100-item, nine-stratum next-study
design and candidate source are registered in `A01-planned-registration.json`;
its candidate outcomes remain unobserved. It still needs an execution adapter,
review and explicit authorization. No A candidate was evaluated after the stop.

The original pinned `ExperienceStoreV2` source remains unchanged. The new
`ExperienceStudyStoreV2` companion retains scoped permissions and append-only
chain checks with an explicit dev-study schema. Across W2 imports, 1,200 episodes
were ingested (100 historical B, 200 fresh B arms, 900 deterministic A).
This is not silent migration or invented format-probe provenance.

D1 is partial: A has one proposal iteration; B has one historical proposal pass
and a post-keep pass yielding no candidate. Neither has three fresh cycles, and
no reverted experimental seam exercised rejection memory tonight. Stable rejection
keys are tested, but tests are not experimental rejections. D2 is partial: B meets
its scoped dev keep rule; A has an unexecuted proposal. D3 is not claimed here.

W0's third infrastructure failure triggered early closure. W0 verified all pods
EXITED. No further inference or experiments were initiated. Fifteen W2 focused
and compatibility tests passed (12 selection/store tests and 3 dispatcher tests).
The protected integration fast tier did not pass; W2 does not relabel it green.

All evidence is synthetic. No real-world reward, clinician sign-off, model-weight
training, signing, retention or activation is claimed. Exact counts are in
`research/overnight-20261017/closure.json`.
