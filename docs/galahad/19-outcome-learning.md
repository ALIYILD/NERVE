# Host-verified adaptive memory sessions

This continuation connects NERVE's existing `OutcomeMemoryRanker` to actual `DemoAgentBridge` sessions through the verified gateway. It is an opt-in research mechanism, not model-weight training, arbitrary source rewriting or clinical decision authority.

## Data and authority flow

The trusted host approves a bounded set of memories, freezes its independent evaluator and issues a separate unprivileged agent capability. `VerifiedOutcomeLearning` attaches the existing ranker to the gateway's `SecureMemoryRetriever`. `session(reader)` selects adaptive retrieval with a host-owned one-record budget. The caller cannot increase this budget or choose an evaluator, grant permissions, assign a reward or approve a memory.

The host executes actual registered tools, passes their actual output and its own task fixture to `observe`, and the independent evaluator judges success/failure. Existing replay protection permits one credited memory per fresh episode/task. Failed/non-boolean evaluation is consumed without utility. Raw task/output text is not persisted by the outcome ranker. The host must not accept agent-supplied answer keys as independent evidence.

Only the same approved, relevant, unexpired and intact sources remain eligible. Exact tenant/agent/context, source integrity and permissions are checked before and after observation. Revoked scopes fail closed even after restart. Utility preferences never change approval, source content or the registered tool allowlist. Default sessions remain lexical and retain their existing conflicting-hint rejection; adaptive single-candidate selection is an explicit host choice suitable for these tested strategy alternatives, not general clinical contradiction resolution.

Observation storage has a durable per-tenant/agent admission cap (default10,000, configurable1–100,000); reaching it stops new credit instead of trimming replay history. Reopening cannot silently raise the stored cap. This is local SQLite enforcement, not distributed service admission. Explicit source deletion removes associated utility as required by the lifecycle policy; replay guarantees do not promise to retain data after authorised deletion.

The recent-window Beta heuristic can reverse preferences after changed verified outcomes. It measures observed success association, not causal benefit or calibrated confidence. Evaluator revisions isolate utility histories; reopening the same revision preserves learned preferences. An existing evaluator cannot silently be overwritten.

## Executable evidence

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python scripts/memory_learning_demo.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_memory_learning*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The bounded demo runs12 host evaluations across two synthetic task phases using actual registered string-transform tools. It first learns `lower-only` for a whitespace-preserving phase, then switches to `trim-lower` when the host's task requires trimming. A reopened gateway/agent retains the latter preference. Durable scope revocation then prevents its reuse. This is a constructed drift demonstration, not an LLM benchmark or proof of improvement on unseen clinical tasks. No generalisation or speedup claim follows.

No evaluator callable/import path or reward endpoint is exposed through JSON configuration, HTTP or MCP. Their feedback remains a pending proposal. Production integration needs an independently validated host evaluator and separately approved workflow; this file does not authorise either. Galahad/GPU/licence/encryption and Clinical OS blockers from the acceptance matrix remain unchanged.

## Host integration example

```python
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.agent_bridge_v13 import DemoAgentBridge

# gateway, scope, reviewer, reader and evaluator are trusted host-owned objects.
# reader has read/propose only; never give the agent reviewer or learning.
learning = VerifiedOutcomeLearning(
    gateway, reviewer, scope, evaluator=independent_evaluator,
    evaluator_revision="frozen-host-evaluator-v1", window=3,
    max_observations=1000,
)
agent = DemoAgentBridge(agent_database, memory_session=learning.session(reader))
# Execute host-owned fixtures with actual tools, then credit only the used source.
learning.observe(memory_id=used_approved_source, episode_id=fresh_episode,
                 task=host_fixture, output=actual_tool_result)
```

Constructing this host integration does not deploy it or grant HTTP/MCP reward privileges. The demonstration is limited to12 evaluations with a three-outcome recent window; no indefinite autonomous loop is started.

## Validation checkpoint

Full regression: **1,055 tests passed** in57.318seconds, zero failures/errors/skips. A final deletion-semantics regression was then added; the complete learning-specific suite passed **18 tests** in1.306seconds. Executable production code was unchanged after the full run (only a clarifying comment and the extra test). Compileall and whitespace checks passed. The actual demo passed with12 independent host evaluations. Remote CI has not run.

Independent read-only review found no additional privilege, cross-context or fallback defect in the defined paths. It highlighted authorised deletion erasing replay history; that exception is explicitly documented and covered by the added regression. One frozen learning evaluator is supported per gateway, so this is not general multi-context adaptive service wiring.

Branch: `feature/galahad-persistent-memory`. Previous checkpoint: `02f36552d21e0294d413aa9f444b483b4c6b934b`. This continuation is committed separately; `git log -1` identifies it. No push, PR, merge, deployment, weight training or real GPU execution.

Added: `memory_gateway/learning.py`, `scripts/memory_learning_demo.py`, two learning test files and this report. Modified: `memory_gateway/session.py` (opt-in host retrieval policy), `scripts/verify_galahad.py` (learning gates), CPU CI (demo execution), and historical-report pointer. Existing approved-memory and utility implementations are reused.
