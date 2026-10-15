# Autonomous research campaign and bounded subloops

The trusted host can now execute a finite campaign without asking an agent to generate or execute source code. This adds orchestration to the existing verified outcome-learning path. It does not turn repeated benchmark runs into model-weight training.

## Loop structure

1. **Campaign:** freeze experiment, source hashes, all seed ranges, maximum work and UTC deadline. Own the ledger and report through process locks. Advance automatically through eligible cycles.
2. **Cycle:** use fresh predeclared seeds for four regimes (stationary, abrupt, recurrent, mixed), each with the existing adaptive baseline, fixed discount candidate and two fixed no-learning controls. Save every completed matched cycle's evidence.
3. **Trial:** spawn only the registered evaluator, with a bounded timeout. Each trial contains 32 actual two-stage tool executions. Score each output before writing its independently verified feedback. Only the selected strategy receives the observation.
4. **Episode:** reuse `AutomaticLearningRun`, `VerifiedOutcomeLearning`, scoped approved memory and `DemoAgentBridge`. Agents cannot select authentication, manufacture rewards or relax budgets.

Each trial starts a fresh learner to preserve matched comparisons. Adaptation is real within each trial; the campaign replicates fixed policies across cycles. It does not persist one learner across all experiments, tune candidates on their test outcomes or improve the base language model. The existing durable learning API is separate from this experimental reset policy.

## Stop and recovery rules

The fixed maximum is 32 cycles × 4 seeds × 4 regimes × 4 arms × 32 episodes = **65,536 pipeline episodes**, or 131,072 primitive tool invocations. There are no paid model calls in this campaign. The separate real-model grounding study has its own eight-call budget.

The campaign stops at its deadline, a stop file, source drift, a failed trial or exhausted budget. It does not restart a consumed experiment merely to remain busy. Seed ranges and trial claims are committed before work. Abandoned claims remain consumed after a crash; a new invocation records their interruption rather than replaying them. Starting fresh ledgers to evade this protection is outside the protocol.

The child process is terminated on timeout, with bounded cleanup. Stop files are checked between trials and every second during the optional interval; an active trial can take up to its timeout plus process startup/cleanup. The machine must stay powered and awake. This is a local process, not a remote always-on service or a deployment.

Source hashes are checked before and after every trial. Reports use exclusive temporary files and atomic replacement. Independent review repaired lock-path collisions and stale deadline allowances. Evidence is operator-owned, public synthetic research, not sealed external evaluation custody.

## Operation

Planned overnight window: stop by **07:00 Europe/London on 13 October 2026** (06:00 UTC), or earlier on a stop condition. Ten-minute intervals between cycles pace local CPU use. Work never continues simply to achieve a favorable result.

```sh
PYTHONPATH=src .venv/bin/python scripts/run_research_campaign.py \
  --database /Users/aliyildirim/nerve-research-runs/overnight-20261013/campaign.sqlite \
  --output /Users/aliyildirim/nerve-research-runs/overnight-20261013/report.json \
  --run-id overnight-v1 \
  --deadline-utc 2026-10-13T06:00:00Z \
  --stop-file /Users/aliyildirim/nerve-research-runs/overnight-20261013/STOP \
  --cycles 32 --seeds-per-cycle 4 --first-seed 10000 \
  --trial-timeout 60 --cycle-interval 600
```

To request a stop, create `/Users/aliyildirim/nerve-research-runs/overnight-20261013/STOP`. The current JSON report is `/Users/aliyildirim/nerve-research-runs/overnight-20261013/report.json`; SQLite contains durable per-trial claims and evidence. For independent reproduction use a preserved, separate ledger, fresh output and a future UTC deadline; published seeds are then replication, not unseen evaluation.

## Evidence and acceptance

Full repository regression: **1,228 tests passed**, zero failures/errors, 72.043 seconds. This includes 19 grounding guard tests, 10 mocked model-study tests and 17 campaign tests (including a real spawned 32-episode trial). [Validation metadata](evidence/research-campaign-validation.json). The detached process was launched and verified running from commit `3970f2e6e2f20d9f1e04f5b8b22ccf1a24ac4dd5`. Its first cycle completed 2,048 real pipeline episodes before automatically entering the scheduled interval. [Timestamped launch and first-cycle evidence](evidence/overnight-launch-v1.json). This snapshot is not the final overnight outcome; consult the live report for subsequent progress. The process-scoped wake lock ends with the command; shutdown or process termination still stops the run. The goal remains partial until measured behavior satisfies its specific gates. No general “fully self-learning” state can be inferred from a campaign completing. Real GPU KV restoration, broad scientific validation and clinical deployment remain separate unresolved requirements. Candidate reports never modify defaults or deploy themselves.

## Morning outcome

The campaign completed all **32 cycles / 2,048 child trials / 65,536 pipeline episodes**, with 32,768 independently verified feedback observations. The final report was written at 06:36 London time, before the 07:00 deadline. Baseline scored 12,604/16,384 (76.93%) and candidate 13,750/16,384 (83.92%). Despite the aggregate gain, mixed-regime performance fell by 202/4,096 cases (4.93 percentage points), so the frozen gate **retained the baseline**. No default was promoted. See [morning report](32-morning-report.md), [summary and integrity hashes](evidence/overnight-campaign-v1-summary.json), and [complete compressed evidence](evidence/overnight-campaign-v1.json.gz). The process has finished; the earlier launch snapshot remains historical evidence.
