# NERVE Agent OS learning architecture and research roadmap

NERVE now contains a local integration for evaluated evidence-handoff lessons, persistent outcome memory, and recommendations among explicitly capable Agent OS profiles. This follows [DeepSynaps' AWIM architecture](https://deepsynaps.ai/), with NERVE coordinating agents, tools, and evaluated feedback alongside WorldCore. This is one bounded part of AWIM: learning how agents report and reuse operational evidence. It does not train LLM weights, establish a universal world model, or automatically improve clinical protocols or physical control.

Implementation and research reviewed on 11 October 2026. A successful live provider connection, a stored lesson, and a measured task improvement are separate outcomes. The completed native study tied 5/5 baseline and lesson on selection, so no lesson was approved and the final holdout was not opened. This report makes no claim that the live study improved performance.

## Implemented architecture

`Agent OS observations → NERVE judge and ledger → isolated Hermes proposal → selection and retention checks → fresh final check → scoped lesson → monitored reuse`

The local bridge, [`agentos_bridge.py`](../scripts/agentos_bridge.py), imports maintenance mission receipts and runs explicit study, recall, execution, review, and publication commands. Accepted operational completions require QA records, completed worker/verifier runs on distinct profiles, and expected artifacts. Supervisor-confirmed timeouts are negative outcomes. These observations are operational evidence; they do not establish that memory caused a better result.

[`agentos_learning.py`](../src/nerve_awim/agentos_learning.py) owns the deterministic handoff judge and SQLite state. Completion requires exit zero, an existing artifact, and passed QA. Known failures override missing evidence; otherwise missing evidence produces `unknown`. Memory is reported saved only when the host supplies that observation. Agent answers cannot assign their own reward.

The installed Hermes runtime is used through [`agentos_hermes_worker.py`](../scripts/agentos_hermes_worker.py), with a selected profile's identity and an isolated temporary runtime. Native tools, existing memories, background skill review, conversation history, and trajectory saving are disabled for this experiment. This prevents external agent memory from contaminating comparison arms. Free model availability is checked against the provider catalog; configured free alternatives can be selected before a session starts. Runtime failover to a paid model is not enabled.

Approved procedural advice is scoped by profile and `agentos-evidence-handoff-v1`, expires after 30 days, and is ranked using independently judged outcomes. Live receipts, utility credit, and revocation commit in one transaction. Three failures among a lesson's latest five live observations revoke it. This is a conservative heuristic trigger, not statistical proof of distribution drift.

The bridge exports status and approved context under `~/.agentic-os/nerve/`, and readable status to `AgentOS-Vault/Memory/nerve-status.md`. Its explicit `sync-gbrain` command indexes the status note and records a command receipt. Obsidian and gbrain are visibility/retrieval surfaces; the NERVE ledger remains authoritative for lesson approval and revocation.

## Evaluation and adaptation gates

The bridge constructs 18 distinct evidence combinations: three training, five selection, five retention, and five final cases. Development and final cases are durably reserved before inference. Evidence hashes exclude cosmetic task IDs, preventing the same case from becoming a new holdout merely by renaming it. The finite fixture eventually exhausts; more runs do not create independent new task families.

[`improvement_loop.py`](../src/nerve_awim/improvement_loop.py) separates proposal, selection, retention, and final evaluation. The bridge currently proposes one lesson per study. Any observed selection loss blocks replacement; retention checks protect the original baseline and, in multi-iteration use, acquired incumbent capabilities. Final results never reach the proposer. A tie correctly produces no verified improvement.

At least one paired final win and zero losses can admit a lesson as scoped advice. Five final cases are too few for a general capability claim. The host validates count consistency and reserved-task totals, but still trusts its own study callbacks and report provenance. This is a local trusted-host API, not an authenticated remote learning service.

Routing recommendations use the last 20 ingested verified outcomes per eligible profile, with score `(successes + 1) / (observations + 2)`. A challenger needs three observations and a strictly higher score; ties preserve the incumbent. The caller must establish task capability. These scores are neither calibrated probabilities nor causal comparisons, and the published recommendation alone does not prove the dispatcher changed its route.

The automatic cycle can request a repository repair study after three newly observed supervisor failures, at most once per UTC day. It does not diagnose or repair the underlying mission timeout. An explicitly queued study deferred for the daily budget can retry after the UTC day changes without new failures. The installed launch agent invokes the cycle every 15 minutes while the user session is active.

## Research choices

| Primary source | Mechanism | NERVE application |
| --- | --- | --- |
| [MemRL](https://arxiv.org/abs/2601.03192) | Separate relevance retrieval from outcome-learned memory utility | Retain scoped outcome ranking; compare against identical lexical and no-memory agents. Current code is inspired by this separation, not a reproduction. |
| [GEPA](https://arxiv.org/abs/2507.19457) | Reflect on execution feedback to propose and evaluate prompt variants | Extend bounded lesson proposals with failure explanations and archived candidates; freeze the judge and final holdout. |
| [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/) | Reusable procedural skills and staged skill writes | Later export verified, versioned lessons into a dedicated Hermes skill scope. Self-authored skill text is not independent validation. |
| [EvoLib](https://arxiv.org/abs/2605.14477) | Consolidate trajectories into reusable skills and reflective knowledge | Deduplicate repeated lessons while retaining provenance, contradictions, and retention tests. |
| [Memory as Middleware](https://arxiv.org/abs/2609.32091) | Pluggable memory with isolation, provenance, consistency, and lifecycle controls | Keep one authoritative ledger with Hermes, Jev, Obsidian, and gbrain adapters. |
| [River ADWIN](https://riverml.xyz/dev/api/drift/ADWIN/) | Detect changes in a streaming distribution | Benchmark drift alarms against the current failure rule; report detection delay and false alarms. |
| [River progressive validation](https://riverml.xyz/dev/api/evaluate/progressive-val-score/) | Predict before updating, including delayed labels | Evaluate missions chronologically using actual QA arrival times. |
| [Darwin Gödel Machine](https://sakana.ai/dgm/) | Archive and evaluate agent code variants | Future isolated branch experiments only. Its reported reward hacking motivates keeping execution evidence and evaluators outside proposed modifications. |

Published benchmark gains do not transfer automatically to NERVE. The existing repository's strong AST baseline ties the learned repository route, and one matched-feedback experiment favored a single shared learner over specialists. Preserve those comparisons when evaluating more agents.

## Budget and review roles

Native Hermes sessions have a durable daily reservation limit of 20 in this bridge. The limit counts sessions, not individual provider retries. Free-model catalog checks and disabled paid failover bound the selected model class; availability failures remain possible.

Jev is an optional advisory semantic reviewer through local Agent OS. Its reservation permits one review per day and records provider usage when returned; dollar cost remains unknown. It cannot approve lessons or override the deterministic judge.

The optional [`ClaudeReviewer`](../src/nerve_awim/agentos_claude.py) uses a persistent $25 task ledger, reserves before transport, reconciles validated usage, and halts on uncertain charges or incomplete responses. Missing credentials prevent calls. The bridge invokes it only through `claude-review`; automatic cycles do not call Claude. The cap applies to this ledger and configured billing assumptions, not other Anthropic clients or separately created ledgers. Provider credit shown in an account is not an API credential.

## Next engineering experiments

1. Add realistic public-code and operational task families with deterministic artifact checks. Learn from the actual failure class that triggered the cycle, keeping handoff correctness as a separate metric.
2. Compare no-memory, lexical-memory, and adaptive-memory arms with equal models, tools, and budgets. Freeze model identity within each comparison and record any availability fallback. Keep proposal, selection, final, and retention sets separate.
3. Measure paired wins/losses, uncertainty, false completion claims, retained-task accuracy, latency, actual or unknown cost, and restart durability. A live connection or test-suite pass is not improvement evidence.
4. Evaluate controlled regime changes, delayed QA, contradictory advice, and old-task retention. Add statistical drift detection only if it improves recovery delay without excessive false fallback.
5. Integrate routing only after capability filtering and matched-workload evaluation. Observe baseline and candidate traffic, monitor outcomes, and retain rollback provenance using the repository's existing governed canary components.
6. Keep future WorldCore adaptation a separate simulator study with full-episode outcomes and held-out sensor regimes. Agent workflow gains do not establish gains in state estimation, planning, clinical decision-making, or real actuators.

## Verification

The focused command `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_agentos*.py' -q` passed **23 tests** during this review. Coverage includes deterministic reward integrity, duplicate/concurrent receipts, transactional rollback, expiry and profile isolation, holdout nonreuse, advice acceptance, recent-outcome routing, and mocked Claude budget/crash behavior. These tests establish implementation properties; they make no live-provider or task-improvement claim.

The subsequent complete suite passed **632 tests** on Python 3.14. A further model-parity regression test was added and passed with the four bridge tests. Python 3.10 identifier-tokenization compatibility was repaired and its four focused tests passed. Native Hermes completed a probe and four study sessions through an available configured free fallback. Jev `jev-1.13.0` completed an advisory review (970 input, 39 output tokens; dollar cost unknown). The Obsidian status was indexed successfully in gbrain. Claude calls: zero, credential not connected.

## Repository repair extension and measured result

The next implementation adds eleven distinct repository function repairs across normalization, counter validation, JSON canonicalization, safe paths, exact statistics, metric validation, duplicate keys, inventory, redaction, handoffs, and regression gates. These are curated injected faults in actual NERVE functions, not claims of newly resolved production incidents. The 2/3/3/3 training/selection/retention/final split isolates function families. The host supplies hidden behavioral tests and validates reference solutions before any model call.

The evaluator runs generated functions in disposable macOS sandbox processes, with restricted Python capabilities, denied home-file contents and network, and CPU/wall-clock limits. It rejects changes to signatures and attempts to overwrite the judge's JSON reporting function. Kernel denial and timeout behavior were tested. Memory limits are unavailable on this installation and are explicitly reported as unenforced.

`RepositoryExperiments` records immutable task reservations and results, freezes the proposal, enforces matching model and configured budgets, and gates scoped lesson approval on selection gain, retention safety, and paired final gain without losses. Approved advice must match profile, model, scope, and evaluator revision. Monitored paired regression or two failures among the latest five observations revoke it atomically. Interrupted hosts are recorded as failures without recycling reserved tasks.

The [live native experiment receipt](evidence/agentos-repository-repair-v1.json), `repair-e7cfaef475f34e0abd8bf5558a0d53fd`, used `backend-engineer` and `nina-memory-librarian`, with `nvidia/nemotron-3-ultra-550b-a55b:free`. Both selection arms scored **3/3**, with zero paired wins and losses. No lesson was promoted; retention and final tasks were not opened. Four native sessions used the same configured 4096 output-token, two-iteration and 90-second outer limits. Native calls share the existing daily allowance; Claude spending remained zero.

Training inspection subsequently exposed missing raw-input-length and whitespace boundary checks. Five cases were added; the archived training patch now fails two of nine checks, where the earlier four checks all passed. The original report and judge hash remain unchanged. This is an evaluator repair, not evidence that learned advice improved unseen tasks. Future experiments also snapshot the evaluator source and public task manifest before inference for reproducibility.

The repository experiment now has a visible dashboard summary. The recurring cycle can request it after three new supervisor failures, provided independent tasks are fresh. Reusing the finite fixture is rejected. Expanding to naturally occurring work requires new independently tested task families; repeated prompts over the same functions do not establish generalization.

Final validation: **670 tests passed** on the installed Python 3.10 runtime, including evaluator execution and kernel isolation probes. Dashboard regression fixtures, TypeScript validation, and the v2 production build also passed. Claude TLS was verified with a credential-free request returning HTTP 401; targeted paid reviews still require an API credential. The $25 reviewer ledger records zero calls and zero spending.


## Second cohort and deferred execution

A second cohort adds eleven previously unused function identities: text trigrams, format validation, plan parsing, advice validation, JSON extraction, retrieval-genome validation, recipe selection, eligibility thresholds, paired statistics, and execution budgets. Selection tasks share a plan-parsing domain; some mechanisms also resemble the first cohort. Fresh function identities do not establish independent semantic domains or broad generalization. Declared inert constructor adapters keep extracted functions runnable under the same restricted evaluator.

Database reservations now also reject previously used function families across studies, including changed mutations, profiles and evaluator revisions. Versioned cohort selection preserves the first experiment and chooses only an entirely fresh cohort. Current evaluator identities for both cohorts bind evaluator source, cohort source and extracted task contracts, with source snapshots retained before inference. Historical receipts retain their original hashes and are not relabeled.

The next native study was queued on 11 October 2026: seven of the twenty daily native sessions remained, while the complete experiment may need eight. Queueing consumed no task evidence or native calls. The existing 15-minute cycle retries after the UTC day changes while the user session is active. The prior 3/3 versus 3/3 result remains the latest measured repository comparison; no additional improvement has yet been measured.

Validation for this extension: **687 tests passed**, including all eleven new reference repairs and rejection of all eleven injected faults. Queue execution and next-day retry were tested with fake inference; the new live comparison remains pending. Claude remains unconfigured with zero calls and zero spending.

## Overnight second-cohort result — 12 October 2026

The scheduled v2 study ran from 00:04:45 to 00:07:02 UTC (01:04–01:07 London), using four native Hermes sessions. The [unaltered v2 receipt](evidence/agentos-repository-repair-v2.json), `repair-9f4f8735bb274e20a7efbe5b58e9c070`, matches its completed ledger summary and evaluator revision. Its SHA256 is `6f5144094d697441ae1537df1cad103dc0fcbbf583a36a9022754756d2092665`.

Selection again scored **3/3 baseline and 3/3 learned advice**, with no paired wins or losses. No lesson was promoted. Retention and final evaluation stayed unopened. Both training outputs were rejected for including top-level dependency assignments instead of only the replacement function. These format failures do not establish that the function bodies were behaviorally wrong; rejected code was not executed.

The baseline reached the selection ceiling, so this comparison could not demonstrate a higher selection accuracy. It does not prove that advice never helps. Both registered cohorts now contain consumed reservations, and a repeat study request returned `no_fresh_tasks` before any model call. The next meaningful evaluation needs fresh, more challenging task families with independently frozen tests; another renamed or remutated existing function is not fresh evidence.

Added `repository-diagnose` to distinguish ceiling ties, training patch failures, regressions and incomplete evidence, using validated recorded artifacts. It cannot approve a lesson, execute repairs or rewrite historical results. Diagnoses are published to local status and Obsidian. Native dollar cost remains unknown in the receipts; Claude still has no connected credential and its review ledger records $0 used.

Follow-up validation: **697 tests passed**. Diagnostics and the no-fresh-task check made no model calls; the daily ledger still records only the four overnight native sessions. Obsidian and gbrain status synchronization succeeded.
