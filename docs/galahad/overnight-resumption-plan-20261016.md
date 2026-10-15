# NERVE — Overnight Orchestration Plan, 15→16 October 2026

**Unattended run. Goal by 07:30 London:** a sealed adversarial task bank v3 (template family B);
skill v1 (v3 @ 7B) measured on it; if it fails anywhere, a registered v4 from stratum-level
failures, evaluated on dev and on one pre-authorised bank-v3 holdout slice, leaving a
`promote_proposal` or a documented negative result waiting for signature; the sequential gate
(Loop 40.2) implemented and validated on the 200-proposal simulation; everything committed and
pushed; pod stopped; morning handoff written.

Grounded in `feature/galahad-persistent-memory` at `fc1fd4f`. Module and script names below are
the ones in the repo; where a new file is named it is new.

---

## 0 · Non-negotiables for an unattended run

1. **Human key stays human.** Nothing is signed, retained, activated or installed as canonical. The
   loop may produce `promote_proposal`; it may not act on it. `registry/` is read-only tonight.
2. **Protected paths are read-only:** `scientific_policy_gate_v2.py`, `scientific_substrate_gate.py`,
   `holdout.py`, `seal_scientific_holdout_v2.py`, `verify_galahad.py`, `tests/suite_tiers.json`,
   the task contract (`RULES`, `SCHEMA` in `scientific_task_bank.py` / `scientific_structured_tasks.py`),
   `registry/`, the α-wallet ledger once created. Hash them at start (L1.1) and before every loop;
   mismatch → halt with `degraded — integrity`.
3. **One holdout consumption is pre-authorised** (L6.3), under the stated conditions only. No other
   sealed data is opened. Item-level holdout outputs stay gate-private.
4. **No external communication.** No email, PR comments, messages. Commits and pushes to the
   feature branch only.
5. **Register, then run.** Every study has a registration hash before its first model call;
   calibrations are flagged exploratory; no retries from results; transport retries only as registered.
6. **Budgets** (L0 enforces before every GPU loop): wall clock hard stop 07:30, wrap-up begins at
   07:00 regardless; GPU ≤ 6 h on pod `lg0svvuenxvbno` (A40, $0.59/h); model calls ≤ 6,000;
   two consecutive `incomplete_infrastructure` → wrap-up.
7. **Honest status file.** `docs/galahad/84-overnight-run.md` is appended at the end of every loop
   with: loop id, start/end, verdict, calls, cost, blockers. If the run dies, this file is the record.
8. **Laptop does CPU only.** All inference is on the pod. Test suites on the laptop are allowed
   while the pod runs inference (the harness only journals locally), but never two laptop suites at once.

---

## L0 · Conductor

**Runs:** continuously, in the galahad window. The outcome-release window runs L2 only.

**Sequence:** L1 → (L3 ∥ L2) → L4 → L5 → L6 → L7. L2 is independent and may finish any time before L7.

**Before every loop:** re-hash protected paths; check wall clock and budgets; read the previous
loop's status line; if the previous loop ended in a blocker, skip to L7.

**After every loop:** commit (`git add` only the loop's files; never `registry/`), push, append status.

**Pod lifecycle:** start the pod in L1.4; stop it in L7.1 *or* immediately after L6 if L5 produced no
candidate (no further GPU work); verify `EXITED` by readback before continuing.

---

## L1 · Pre-flight (CPU + pod start) — budget 20 min

- **1.1 Integrity.** `git status` clean on `fc1fd4f` or later; write `protected_paths.sha256`
  for the paths in §0.2 to `docs/galahad/evidence/overnight-protected-paths.json`.
- **1.2 Fast tier.** `verify_galahad.py fast --timings …`; must pass. Record seconds.
- **1.3 Retained skill sanity.** `verify_retained_skill_consumption.py` — 16/16 checks, zero inference.
  If it fails, stop: the baseline for tonight is skill v1 and it must be loadable.
- **1.4 Pod.** Start `lg0svvuenxvbno`; readback until `RUNNING`; confirm Ollama 0.40.5 serves
  `qwen2.5-coder:7b` with digest `dae161e27b0e…`; mismatch → stop with blocker (never substitute a model).
- **1.5 Transport smoke + latency.** `smoke_scientific_candidate_transport.py` (≤ 5 calls);
  record median/max; set tonight's per-attempt timeout = 3 × max (expect ≈ 3–5 s), two identical
  resends, journaled — the frozen Runpod policy already in `run_scientific_runpod_gate.py`.
- **Done-when:** all five green, status line written. Any red → L7 with blocker.

---

## L2 · Sequential gate, Loop 40.2 (CPU, outcome-release window) — budget 3 h

*Build only. Not installed. The canonical gate stays `scientific_policy_gate_v2`.*

- **2.1 Module** `src/nerve_awim/memory_gateway/scientific_sequential_gate.py`:
  paired per-item outcome stream (candidate vs incumbent: win/loss/tie); test-supermartingale on
  win probability among discordant pairs, H0 p ≤ 0.5, registered mixture/betting e-process;
  promote at e ≥ 1/α, α registered (default 0.05); per-stratum e-processes vs always-abstain as
  vetoes; futility bound; verdicts `promote_proposal | retain_incumbent | insufficient_power |
  incomplete_infrastructure`; marginal-delta semantics (candidate installed, then reverted);
  plateau rule: net wins − losses ≥ noise floor taken from the robustness study (doc 82: seed
  variance 0 → use a registered minimum of 3).
- **2.2 α-wallet** `scientific_alpha_wallet.py`: per-bank ledger of α spent per registered study;
  refuses to open when exhausted; hash-chained; this file becomes a protected path once created.
- **2.3 Tests** `tests/test_scientific_sequential_gate.py`: type-I control under H0 across 10,000
  simulated streams (≤ α); early stop under H1; stratum veto; wallet exhaustion; resume mid-stream
  with identical e-value and zero repeated calls; tampered history detected.
- **2.4 Simulation** `scripts/simulate_sequential_gate.py`: 200 proposals, 20 % harmful
  (true win-prob 0.35), 30 % neutral (0.5), 50 % good (0.65); simulated outcomes, **zero model calls**;
  arm A = current slice gate with naive reuse, arm B = sequential gate with wallet. Report
  harmful-accept rate, good-accept rate, items consumed. Target: harmful < 1 %, fewer items than A.
  Evidence → `docs/galahad/evidence/sequential-gate-sim-v1.json`.
- **2.5 Doc** `docs/galahad/85-sequential-gate.md` citing Lewis (ICML 2026) and Regimes.
- **Done-when:** tests green, simulation target met, doc written, committed. Not canonical.

---

## L3 · Adversarial bank v3, template family B (CPU) — budget 60 min

*Same task contract (`RULES`, `SCHEMA`, `parse`) so results are comparable; harder instances;
different phrasing family so template memorisation is tested. Zero model calls.*

- **3.1 Generator** `src/nerve_awim/memory_gateway/scientific_task_bank_v3.py` — must not import
  or copy the sentence templates of `scientific_task_bank.py`. `VERSION='task-bank-v3'`.
  Nine strata, 100 dev + 43/42 holdout each:
  - the seven existing strata, re-instanced with the hardening below;
  - `format-variant-agreement`: two current records, same numeric value, different strings
    (`123.4` / `123.40` / `0123.4`) → **answer** (agreement). Tests whether the conflict rule compares
    numerically or textually.
  - `dissenter`: three current records, two agree, one differs → **abstain** (conflict).
  Hardening applied across strata: entity names differ from decoys by one interior character of
  the same length (`N7f3a…9c` vs `N7f3a…9d`), never by prefix; measurement decoys use qualified names
  (`dry mass`, `mass fraction`) and the same unit; evidence lists of 6–12 records with 3–8
  distractors about other entities; three sentence patterns per record, chosen by hash
  (`"Mass of sample X: 123.4 mg (current)."`, `"X was measured at 123.4 mg."`, `"…recorded 123.4 mg for X."`);
  record order shuffled by hash; stale records keep the explicit `current=false` flag (contract
  unchanged) but appear *after* the current one. Values stay exact one-decimal strings.
- **3.2 Build + seal.** `scripts/build_scientific_task_bank_v3.py` mirroring the v1 builder:
  private 256-bit seed, registration before generation, manifest hash, separate ground-truth
  check for all 1,300 items (every expected answer derivable from the contract by a second,
  independent implementation), sealing receipt via `seal_scientific_holdout_v2.py` with mode 000.
  Store the holdout where v2 lives (pod-local `/root`, backed up locally outside `/private/tmp`).
- **3.3 Tests** `tests/test_scientific_task_bank_v3.py`: manifest reproducibility; dev never reads
  holdout; stratum counts; no sentence template shared with v1 (string-set intersection empty);
  distractor entities never equal the target.
- **Done-when:** manifest hash recorded, sealing receipt, tests green, `docs/galahad/86-task-bank-v3.md`.
  Status line carries the manifest hash. **No candidate may be designed before this line exists.**

---

## L4 · Skill v1 on bank v3 dev (GPU) — budget 30 min, ≈ 1,800 calls

- **4.1 Register** with the `run_scientific_runpod_robustness.py` harness pattern (`register`):
  arms = skill v1 (v3 @ 7B, exact registry config), incumbent bootstrap, always-abstain, random;
  bank-v3 dev split (900 items); seed 20261016; one shuffled order; temperature 0; the L1.5
  transport policy; flagged **exploratory**; registration hash recorded.
- **4.2 Run** (`run`), then **4.3 Verify** (`verify`) — replay with zero additional calls.
- **4.4 Report** per stratum with Wilson intervals; five-axis summary (accuracy, efficiency,
  robustness n/a single seed, safety = wrong answers + false abstentions, UX n/a);
  diagnosis labels per failed item (dev, so item-level allowed) using the deterministic classes:
  `abstained_when_answerable, answered_when_should_abstain, wrong_value, wrong_unit,
  wrong_provenance, format_invalid, decoy_selected, stale_selected, conflict_not_detected`.
- **Done-when:** verdict + replay + report committed as `docs/galahad/87-skill-v1-on-bank-v3.md`.
- **Branch:** if skill v1 scores 100 % on every stratum → status `bank_v3_saturated`, skip L5–L6,
  stop the pod, go to L7 (this is a real finding: synthetic difficulty is exhausted; escalate to real data).

---

## L5 · Diagnosis → generator → screen (CPU) — budget 45 min

- **5.1 Episodes.** `import_scientific_episodes.py` on the L4 receipt → `experience_store_v2`.
- **5.2 Cluster.** Failure histogram by stratum × diagnosis label. Expected hotspots:
  `format-variant-agreement` (textual compare), `dissenter`, `near-duplicate entity` via `decoy_selected`.
- **5.3 Propose.** `register_scientific_candidates.py --max-proposals 3` with the research agent
  enabled; each proposal must name its seam (`abstention-rule` | `extraction-schema` |
  `prompt-fragment` ≤ 400 chars) and its predicted regression stratum. Expected seam patches:
  numeric-equality normalisation in the conflict rule; dissenter → conflict rule; `entity` field
  as a schema enum of entities present in the prompt (mirrors the `source_id` enum).
- **5.4 Screen.** `screen_scientific_candidates.py` against negative-evidence history; refuse
  near-duplicates of rejected hashes; static checks per seam (no new keys, size cap, import whitelist).
- **5.5 Select v4** = the proposal addressing the largest cluster; record the other two as archived.
- **Done-when:** `docs/galahad/88-v4-registration.md` with hypothesis hash. If no seam-reachable
  cluster exists → record the wall (Loop 46 trigger), skip L6, go to L7.

---

## L6 · Candidate v4: dev study, then one pre-authorised holdout slice (GPU) — budget 40 min

- **6.1 Register + run dev** with the `run_scientific_candidate_v3_study.py` pattern:
  v4 vs skill v1 vs always-abstain vs random, bank-v3 dev, seed 20261016, nine strata. Verify replay.
- **6.2 Decision rule (pre-registered):** proceed to holdout only if v4 ≥ skill v1 on **every**
  stratum and strictly greater overall, and the domain checks (unit consistency, value present in
  cited evidence, source resolves) show zero violations. Otherwise verdict `retain_incumbent` on
  dev, archive v4 with its study, go to L7.
- **6.3 Holdout — pre-authorised once.** Partition bank-v3 holdout (300) into three sealed slices
  of 100 (≈ 11 per stratum); consume **slice 1 only**: v4 vs skill v1 vs always-abstain vs random;
  acceptance rule = beats all three controls, no stratum below skill v1, intervals reported;
  item-level outputs gate-private; stratum counts public. Verdict `promote_proposal` or
  `retain_incumbent`. **Stop there.** Slices 2–3 stay sealed.
- **Done-when:** `docs/galahad/89-v4-holdout-slice1.md`; verdict in the status line; nothing signed.

---

## L7 · Wrap-up (CPU) — must begin by 07:00

- **7.1 Pod.** Stop `lg0svvuenxvbno`; readback `EXITED`; record GPU hours and cost.
- **7.2 Suites.** Fast tier, then slow tier once, single process each, measured timeouts.
- **7.3 Integrity.** Re-hash protected paths; compare with L1.1; any difference is reported at the
  top of the handoff in bold.
- **7.4 Commit + push** everything; `git log origin/feature/galahad-persistent-memory -1` in the handoff.
- **7.5 Handoff** `Desktop/NERVE_MORNING_20261016.md`:
  - one line per loop: ran / skipped / blocked, with the verdict and the doc number;
  - the single decision waiting for the human key, if any (v4 `promote_proposal`), with the
    stratum table and the exact signing instruction;
  - bank v3 manifest hash and where the holdout lives;
  - sequential-gate simulation result and whether it met target;
  - cost: GPU hours, calls, $;
  - anything the run could not do, with the reason;
  - the 8/8 handler result explicitly excluded as learning evidence (carry-over from doc 83).

---

## Expected outcomes, in order of likelihood

1. **Skill v1 fails on 1–3 new strata; v4 fixes them on dev; holdout slice 1 returns
   `promote_proposal`** → morning: sign, Loop 41 retains skill v2. The loop has learned from a
   bank it had never seen the phrasing of.
2. **Skill v1 fails; v4 regresses somewhere** → `retain_incumbent`, v4 archived, failure clusters
   public → v5 is a daytime design task with a clean holdout still sealed.
3. **Skill v1 scores 100 % on bank v3** → `bank_v3_saturated` → the synthetic route is finished;
   Loop 38 real cases become the only next step. Also a real finding.
4. **Infrastructure blocker** → the status file says exactly where; nothing consumed except what
   the file records.

Every outcome leaves the repo committed, the pod stopped, and no human decision taken by the loop.

---

## Kick-off prompts

**Galahad window (pod-backed):**

> Execute `NERVE_OVERNIGHT_ORCHESTRATION_20261016.md` from L0, unattended, until L7 completes or a
> stop rule fires. You run L1, L3, L4, L5, L6, L7. The outcome-release window runs L2 separately.
> You are authorised to start pod lg0svvuenxvbno (A40, $0.59/h) and use it for all inference tonight, up to 6 GPU hours total across all pods. If that pod cannot start, you may create one replacement pod of the same GPU class, pull qwen2.5-coder:7b and verify the full digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364 before any study; a different digest is a blocker, not a substitute. Never have more than one pod running at once; confirm the original is stopped before starting a replacement. Stop every pod you started and verify EXITED before writing the morning handoff; record pod IDs, GPU hours and cost in it.
> The 6 GPU-hour cap includes startup, preparation and idle running time. Retain the 6,000-model-call cap and 07:00 wrap-up / 07:30 London hard stop. No model substitution or additional replacement pod is authorised.
> You are pre-authorised for exactly one holdout consumption, bank-v3 holdout slice 1, under L6.2's
> rule and nothing else. Never sign, retain, activate, modify `registry/` or any protected path,
> or contact anyone. Append `docs/galahad/84-overnight-run.md` after every loop and commit+push
> after every loop. Stop the pod when GPU work ends and verify `EXITED`. Write
> `Desktop/NERVE_MORNING_20261016.md` last. If anything is ambiguous, choose the more conservative
> reading, record it, and continue.

**Outcome-release window (laptop, CPU only):**

> Execute L2 of `NERVE_OVERNIGHT_ORCHESTRATION_20261016.md`: build and validate the sequential gate
> (Loop 40.2) as a non-canonical module with tests, the α-wallet, and the 200-proposal simulation
> with zero model calls. Do not install it as the canonical gate, do not touch `registry/` or any
> protected path, do not run inference, do not contact anyone. Run only one test suite at a time.
> Commit and push on completion with `docs/galahad/85-sequential-gate.md`, then stop.


## Resumption amendment — 16 October 2026, user-authorised

After the initial protocol-blocked run was published at `48286fcc`, the user supplied the restarted pod connection and replied “do it all” to the pending proposal for a revised registered input-adapter protocol and CPU preflight time budget. This authorizes proceeding with those revisions, preserving the original records and results.

- A separately versioned input adapter may translate the required family-B sentence formats for both frozen comparator pipelines. It may not read expected answers, choose supporting evidence, remove distractors or change the task contract. Register and freeze the adapter before bank generation. Report the resulting pipeline as **adapted skill v1**, not unchanged retained skill v1.
- Preserve the full harder bank: nine strata, 900 development and 300 holdout instances (1,200 total). Seal before candidate design; only slice 1 of three balanced 100-item holdout slices may be consumed, under the original development eligibility rule.
- A separate versioned CPU preflight runner may use a declared 20-minute aggregate budget with the same fast-tier test selection. Do not edit the protected historical verifier or tier manifest. Preserve earlier timeout evidence. One laptop suite at a time.
- A prospective sequential-gate power study may be separately registered with fresh validation draws and an explicit beneficial-acceptance requirement. Preserve the completed zero-good-acceptance study. Do not claim success merely by rejecting all proposals or tune on the new validation results.
- Original model digest, registry, trust, canonical gates and task contract remain unchanged. No new signing, retention or activation.
- Pod `lg0svvuenxvbno` was already RUNNING when checked, started at 2026-10-15T23:08:59.019Z according to Runpod. Count running startup/preparation/idle time from that point toward the cumulative six-GPU-hour limit; stop earlier when work ends. In the absence of pauses, the GPU deadline is 2026-10-16T05:08:59.019Z. The original 6,000-model-call limit and 07:00 wrap-up / 07:30 London deadlines also apply. Only one running pod, one same-class replacement if necessary, exact model digest only.
- Commit and push the revised registrations, evidence and final handoff to the same feature branch. Fresh EXITED readback is required before closing the run.

### CPU preflight continuation — 16 October 2026

The separately registered 1,200-second preflight timed out at 1,201.563 seconds without completing all 2,228 selected tests; its source hashes were unchanged. This remains a timeout, not a pass. Under the user's instruction to continue all work, the next prospective CPU-only protocol uses a fresh full run of the identical selection with a 3,600-second budget. No partial verbose-log results are spliced into a claimed pass. The original 180-second verifier and tier manifest stay unchanged. One laptop suite at a time; the pod remains stopped during preparation.
