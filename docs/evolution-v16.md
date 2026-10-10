# NERVE Evolution v1.6 — Paired agent-learning evidence

## Why this release exists

Previous NERVE demos established that feedback can alter a registered
agent's strategy selection, but a capable non-learning baseline performed
equally well. v1.6 improves **measurement methodology** rather than
claiming a new model-learning breakthrough.

The study runs the same NERVE MCP task set for two arms:
`no_memory` and `with_memory`. Both receive the same fixed training
experience observations, with only the second arm receiving a
context-specific, allowlisted recommendation. The agent makes one model
decision per task and only registered string handlers can execute.

## New analysis

- Task-level *paired* success/failure indicators retained in memory only.
- Per-format and overall success, gain/loss discordances and error counts.
- An **exact McNemar p-value** as a descriptive paired comparison only;
  repeated tasks inside each synthetic seed are not independent, so
  this value is **not** a definitive significance claim.
- Seed-cluster bootstrap for the paired accuracy delta with a fixed
  random seed, reported **only when >=5 distinct seed clusters** are
  present. Smaller studies report a null interval instead of
  an artificially precise bound.
- Failed model planning requests count as unsuccessful held-out tasks;
  they do not silently disappear from evaluation denominators.
- Actual executed tool stages, model planning failures, stage errors,
  reported token usage, and wall-clock/model latency are tracked.
- The evaluation report contains **no input strings, expected answers,
  raw model responses, conversation content, or credentials**.

## Run the credential-free reproducible checks

```bash
python -m pip install 'mcp==2.3.0'
export PYTHONPATH=src
python scripts/agent_study_v15.py --seeds 5 --cases 2
python scripts/agent_study_v15.py --failure-fixture --seeds 2 --cases 2
python -m unittest discover -s tests -p 'test_study_statistics_v16.py' -v
```

The first invocation checks that the capable fixture performs well with
or without NERVE memory. The second intentionally injects failed model
decisions in one task format; the errors remain in the accuracy
denominator and are reported explicitly.

## Scientific and operational boundaries

These are synthetic, hand-authored tools, and deterministic fixtures.
Five seed clusters do not establish sufficiently powered LLM-agent
learning gains. Statistical intervals are descriptive; interpretation
requires a frozen protocol, more independent holdout environments,
task diversity, realistic model costs and model-to-model controls.

A separately configured protected workflow
`.github/workflows/llm-study-v15.yml` can optionally test a real model.
It does not run automatically and must use a fresh private credential.
No released NERVE component edits its own safety policies, changes
production model weights or authorises clinical/physical actions.
