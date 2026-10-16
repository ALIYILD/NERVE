# Bank v3 development verdict: exploratory failures

The completed registered L4 study measured adapted v1 at **581/900 (64.6%)**, adapted bootstrap at 356/900, always-abstain at 300/900 and random at 136/900. This is a harder synthetic development bank, not a holdout result or a measurement of the unchanged retained skill. No promotion is authorized.

| Stratum | Adapted v1 | 95% Wilson interval | Bootstrap | Abstain | Random |
|---|---:|---:|---:|---:|---:|
| conflict | 100/100 | 96.3%–100.0% | 6/100 | 100/100 | 29/100 |
| dissenter | 100/100 | 96.3%–100.0% | 1/100 | 100/100 | 26/100 |
| entity-decoy | 39/100 | 30.0%–48.8% | 41/100 | 0/100 | 11/100 |
| format-variant-agreement | 49/100 | 39.4%–58.7% | 55/100 | 0/100 | 8/100 |
| measurement-decoy | 33/100 | 24.6%–42.7% | 41/100 | 0/100 | 11/100 |
| multi-source-agreement | 48/100 | 38.5%–57.7% | 57/100 | 0/100 | 8/100 |
| stale-vs-current | 64/100 | 54.2%–72.7% | 63/100 | 0/100 | 7/100 |
| supported-measurement | 48/100 | 38.5%–57.7% | 41/100 | 0/100 | 11/100 |
| unit-mismatch | 100/100 | 96.3%–100.0% | 51/100 | 100/100 | 25/100 |

Intervals are marginal descriptive intervals; this single-seed study does not measure seed variance or establish independence across generated items. The largest failure cluster is measurement-decoy: 67 decoy selections. Other adapted-v1 failures are entity-decoy61, supported-measurement52, multi-source25 decoys+27 provenance, format-variant25 decoys+26 provenance, and stale-vs-current27 decoys+9 stale selections.

Efficiency: 1,500 logical calls and physical attempts, zero timeouts, 2,076.0616 seconds study wall time, allocated compute estimate $0.34024. Total startup/idle billing is tracked separately. Pod `b7qj6qyx9ij6gg`, NVIDIA A40, $0.59/hour, Ollama0.40.5, model digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. Cumulative physical attempts through this study:1,510.

Safety: adapted-v1 has319 wrong answers, zero false abstentions, zero format-invalid outputs and zero domain violations. A domain-valid answer can still cite the wrong entity/quantity or violate the lexical provenance rule; zero domain violations is not zero harm. Robustness across seeds/orders is unmeasured here; UX is n/a.

Root run84145 and verify39198 completed with matching aggregate and no verification calls. Public registration and aggregate are preserved under `evidence/attended-canada-l4-*`. Item-level evidence remains private. Candidate design may now use only these final aggregate counts; no holdout has been consumed.
