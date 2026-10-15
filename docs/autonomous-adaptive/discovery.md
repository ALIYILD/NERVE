# Discovery checkpoint — 13 October 2026

Inspected from clean source revision `5eb16da`. This is an initial audit, not
completed implementation. The [derived CLI prompt](claude-master-prompt.md)
contains seventy proposed subloops and eleven specialist assignments. The
user's original full prompt was absent from the supplied message.

| Component | Existing extension point | Evidence and remaining work |
| --- | --- | --- |
| Coordinator | `scripts/agentos_bridge.py`, `scripts/agentos_autoresearch.py` | Scheduled research, quotas and immutable findings; preserve one scheduler |
| Memory | `src/nerve_awim/memory_v18.py`, `agentos_learning.py`, `adaptive_memory.py` | Scoped approval, expiry and outcome ranking; general generation/workspace handoff incomplete |
| Research inheritance | `scripts/agentos_cohort_study.py` | Frozen training-feedback snapshots; research notes confer no operational authority |
| Hermes | `scripts/agentos_hermes_worker.py`, bridge `native` | Fresh bounded sessions; broad tool/workspace generations not established |
| Evolution | CCE lifecycle, `recursive_evolution_v19.py` | Candidate evaluation and synthetic evolution; general independent gain unproven |
| World model | `src/nerve_awim/world_model/` | Separate incomplete Memento 3 programme, not Anthropic's Memento harness |
| Adaptive inference | CCE local model adapter and Hermes provider selection | Transport/profile work exists; hardware-optimising selector not established |
| Inference fabric | No deployed fabric identified | Reviewed hosts and backend required; no inferred network authority |
| Observer | `safety/nerve_guardian/`, `scripts/verify_watchtower.py` | Separate package and passive telemetry; Mac enforcement and independent identities incomplete |
| Clinical OS | Existing clinical exclusions | Actual DeepSynaps API and clinical release contract not established by this audit |

`runtime_v28.py` and `observed_runtime_v29.py` implement research control/recovery,
not inference hardware adapters.

## Checks performed

The following passed **47 tests** in 0.773 seconds:

```sh
PYTHONPATH=src:scripts:tests python3 -m unittest test_agentos_learning test_memory_v18 test_adaptive_memory test_hermes_agents test_agentos_research_findings -q
```

These verify existing software contracts, not cross-generation model gains.
`PYTHONPATH=safety python3 -m nerve_guardian macos-preflight` reported
**NOT_READY**; see [the receipt](preflight-20261013.json). Passive telemetry was
fresh with collection health OK. Protected Guardian installation, configuration
and LaunchDaemon were absent. The learning job remains a UID 501 user LaunchAgent.

Live gates: implement Mac containment; verify restricted worker identity and
independent administration; provision owner MFA and external alert delivery;
test disposable shutdown/restart. Root ownership alone does not prove independence.
Follow the existing [Mac setup contract](../watchtower/MACOS_SETUP.md). Do not
move deployment to Linux or interrupt the existing learner for containment tests.

## Research and phase status

[Anthropic's report](https://www.anthropic.com/research/self-replicating-ai)
describes workspace/notes inheritance into fresh sessions. Its 45% initial and
61–84% later-generation setup success is task-specific. NERVE requires matched
budgets, independently judged outcomes and untouched held-out evaluation to
establish benefit. No reproduction of these results is claimed here.

Phase 0 is partial: extension points and focused baseline checked; complete
hardware/dependency inventory and frozen experiment design remain. Phases 1–9
remain incomplete. Existing components are foundations, not completed phases.
This checkpoint changes no workload, credential, provider call, clinical setting
or deployment permission.
