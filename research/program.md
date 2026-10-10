# NERVE AutoResearch experimental programme

Inspired by the research-loop methodology in [Andrej Karpathy's autoresearch](https://github.com/karpathy/autoresearch).

## Objective
Evaluate bounded, auditable learning-rule candidates on a fixed synthetic dynamics benchmark. Keep only candidates improving the **validation** metric without relaxing rules.

## Fixed evaluation
- Python entrypoint: `python -m nerve_awim.autoresearch_v01`
- Ten selection seeds (0–9); ten independent reporting-only seeds (100–109)
- Eighty timesteps per run, single regime switch at step 40
- Validation objective: lower mean post-change absolute prediction error
- Candidates modify **only** the scalar learning rate
- Holdout is evaluated after selection and must never influence which candidate is kept

## Isolation and limitations
- No agent can modify the evaluation code through the research runner
- No arbitrary generated code execution, network access, credentials, or patient data
- No model weights trained beyond one synthetic parameter estimator
- No scientific claim of general intelligence or quantum acceleration

## Research history
Use `write_ledger(report, path)` for local JSONL records. Preserve failed experiments.
