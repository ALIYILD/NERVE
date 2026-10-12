# Track B: bounded external memory experiment

Joint sequence training ran for 25 epochs on CPU in 1.566 seconds. Downstream training MSE changed from 0.09180 to 0.06093. Slow parameters were key/query/value projections, initial fast weights and learning rate. Numerical derivatives were checked independently against finite differences. These are actual NumPy runs, not fabricated GPU or hosted-model results.

| Authorized events | Exact structured | Untrained memory | Trained, no updates | Trained, online |
|---:|---:|---:|---:|---:|
| 16 | 61.3% | 56.2% | 1.2% | 56.2% |
| 64 | 78.4% | 59.1% | 8.1% | 68.1% |
| 256 | 78.3% | 44.1% | 10.4% | 60.9% |
| 1024 | 78.2% | 41.3% | 12.2% | 59.9% |

Paired trained-online minus structured accuracy: -12.74 percentage points; seed-cluster bootstrap 95% interval [-13.50, -11.99]. Five seeds are a small engineering study. Each length uses matched sequences across four variants. Predictions precede current-label writes; mappings change every 32 events to exercise forgetting and changed preferences.

The benefit gate fails. Training loss improvement does not establish adaptation benefit. Keep exact structured task memory; external weights remain experimental. This is an evidence-class microbenchmark, not an end-to-end agent benefit evaluation or a robotics reproduction.

Per-row read/update times, correct/eligible denominators and 512-byte fast-weight storage are in track-b-scaling.json. Slow parameters, event ledgers and retrieval indexes are additional storage. No model generation or provider calls occurred, so generation latency, provider tokens and provider cost are zero. All data are synthetic; seeds and manifests are frozen separately from training.
