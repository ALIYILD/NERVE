# NERVE: research-to-implementation roadmap

Research checked 11 October 2026. This is a selected primary-source review, not
an exhaustive survey or a claim that published benchmark gains transfer to NERVE.

## Sources and decisions

| Resource | Date / status | Relevant idea | NERVE decision |
|---|---|---|---|
| [Memory as Middleware / ALTK-Evolve](https://arxiv.org/abs/2609.32091), [code](https://github.com/AgentToolkit/altk-evolve) | 25 September 2026; paper lists conditional Middleware acceptance | Pluggable memory with tenancy, provenance and lifecycle controls | Retain authoritative local ledger; evaluate middleware adapters separately |
| [EvoLib](https://github.com/microsoft/EvoLib), [paper](https://arxiv.org/abs/2605.14477) | May 2026 research | Consolidate trajectories into reusable skills and reflective knowledge | Plan proposed skill records with provenance; do not equate self-reflection with verified truth |
| [ALMA](https://arxiv.org/abs/2602.07755) | February 2026 preprint | Meta-learn memory designs, including executable retrieval/update mechanisms | Later sandboxed research only; no generated memory code in the trusted service |
| [MemRL](https://arxiv.org/abs/2601.03192) | January 2026, revised February | Separate relevance retrieval from outcome-based memory utility, without model-weight updates | First step: opt-in outcome-based reranking described below |
| [GEPA](https://github.com/gepa-ai/gepa), [paper](https://arxiv.org/abs/2507.19457) | 2025 foundation with maintained implementation | Use execution feedback to propose and select prompt variants | Next: offline typed prompt proposals, explicit inference budgets and independent evaluation |
| [Darwin Goedel Machine](https://sakana.ai/dgm/), [paper](https://arxiv.org/abs/2505.22954) | May 2025 foundation | Archive diverse coding-agent variants and empirically evaluate changes | Future isolated branch/PR experiments; never direct production self-modification |

Newer is not automatically better. ALTK's architecture paper is the newest item
in this selected set; GEPA and MemRL are particularly actionable mechanisms.
No external package above is installed or claimed to be integrated by this change.
Licensing, dependency security and provider/data terms require review before adoption.

## Implemented first increment: outcome memory ranking

`src/nerve_awim/adaptive_memory.py` adds `OutcomeMemoryRanker`, integrated as an
explicit `mode='adaptive'` in `SecureMemoryRetriever`. Existing lexical and
semantic modes remain unchanged. This is a small original research prototype
inspired by the separation of relevance and utility, **not a MemRL reproduction**.

1. A trusted host configures an independent evaluator and explicit evaluator revision.
2. The host supplies a fresh synthetic/public task, its actual output and the one
   credited memory. An approval-capable actor is required; clients cannot supply rewards.
3. The evaluator returns a strict boolean. Failed or interrupted evaluation does
   not become a success; the episode remains consumed, preventing retry bias.
4. Relevant candidates come from the existing exact-scope approved lexical ledger.
5. A bounded recent window of judged outcomes ranks those candidates using
   `(successes + 1) / (judged episodes + 2)`. Relevance order breaks ties.
6. Revocation/expiry is checked again while ranking, and after evaluation before
   credit is written. Evaluator revisions isolate utility evidence.

Example host integration (the host owns the evaluator and capabilities):

```python
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_retrieval_v18 import SecureMemoryRetriever

utility = OutcomeMemoryRanker(ledger, evaluator=independent_judge,
                             evaluator_revision='task-evaluator-v1', window=20)
utility.observe(reviewer, memory_id=used_memory_id, episode_id=unique_episode_id,
                task=public_task, output=actual_output)
retriever = SecureMemoryRetriever(ledger, utility=utility)
memories = retriever.retrieve(reader, context='planning', query='sorting',
                             mode='adaptive', limit=5)
```

Only hashes, IDs, evaluator revision and outcome status are persisted; no raw
task/output transcripts. Hashes are not anonymization. Use public/synthetic data.
The database is not encrypted and evidence retention is not yet automated.
The trusted host must enforce dataset separation and attribution: the ranker
cannot independently prove that an episode really used the credited memory.

Important limitations: recent-window scores are heuristic preferences, not
calibrated confidence or causal estimates. No exploration, embeddings, learned
consolidation, LLM reflector or model fine-tuning was added. The first-stage pool
is limited to 20 relevant lexical records. An old skill can fall out of favor;
retention/regression testing remains necessary. This mode is **not enabled in the
repository HTTP host**, clinical agents, or the scheduled synthetic recipe search.
Tests establish control flow and trust boundaries, not improved agent accuracy.

## Next implementation stages and acceptance gates

1. **Chronological study:** no-memory, lexical-memory and adaptive-memory arms;
   same capable model/tools/budget; separate training, selection and fresh final
   evaluation tasks; repeated seeds; confidence intervals, latency and actual cost.
   Check tenant isolation, forgetting, contradictory memory and distribution shifts.
2. **Skill consolidation:** extract proposed lessons from failures/successes;
   deduplicate, attach source traces, independently verify, approve or expire.
   Raw retrieved text is data, never authority or a replacement system prompt.
3. **Reflective optimization:** use GEPA-style proposals over bounded prompt/tool
   recipes. Keep evaluator and final holdout outside the optimizer. Archive
   rejected candidates and negative results as well as successful ones.
4. **Controlled adaptation:** shadow evaluation, operator-reviewed canary,
   independent outcome monitoring and automatic rollback. Do not auto-promote
   from an in-sample utility score or a research-paper result.
5. **Code evolution:** only after an isolated execution environment, resource
   budgets, secret/network exclusion, independent tests and reviewed PRs exist.

NERVE already has scoped memory, bounded offline evolutionary search, governed
repository training, canaries and monitored rollback. Those pieces do not yet
constitute a connected, generally self-improving live agent. The immediate missing
evidence is task-level improvement on independently held-out realistic workloads,
not more runs against the same small synthetic search space. Clinical protocols,
device controls and access policies must not be modified by these learning loops.
