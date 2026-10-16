# Overnight autoresearch evidence — 17 October 2026

No fresh keep/revert result is claimed at this checkpoint. The registered program
is `research/program-20261017.md`; its hash receipt and B01 registration are under
`research/overnight-20261017/`. `scripts/overnight_dev_study.py` implements a fresh
100-item B-v5 versus retained B-v4 dev run with frozen controls, four concurrent
SSH requests at most, two identical timeout resends, immutable request claims,
and offline reconstruction. It needs W0 preflight authorization and pod-B lock.

The historical B dev study was independently reconstructed from 100 request-body
claims and wire responses, with row equality and aggregate win/loss checks. Its
100 v4 outcomes were imported with no inference into an explicit typed dev-study
journal. Two failure clusters generate two registered configuration proposals;
these are unevaluated. See `research/overnight-20261017/historical-b-import.json`.
The private journal is `~/nerve-research-runs/overnight-20261017-b-experiences/`.

The original `ExperienceStoreV2` is pinned by retained-skill registry configs and
only accepts four-position format probes. Its source remains unchanged. The new
`ExperienceStudyStoreV2` companion shares the same append-only chain and scoped
permissions, while explicitly recording dev-study provenance, model digest,
registration hash and domain. This is not a silent migration or a claim that
bank rows were format probes. SDK callers must replay before importing.

The available Family A 7B dev receipt records v3 at 100/100; its old baseline's
80 failures cannot serve as retained-v3 failure clusters. B has 43 historical
v4 failures across two agreement strata. Those facts do not establish tonight's
D1 (three fresh proposal iterations per family) or D2 (fresh kept improvements
per family). No holdout handoff or promotion request is available yet.

Synthetic-only boundary: replay validates the fixed evaluator against recorded
synthetic ground truth. No real-world reward, clinician sign-off, model-weight
training, signing, retention or activation is claimed.
