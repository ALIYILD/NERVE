# Sequential gate ablations and alpha-investing: simulation only

Prospective design: preserve the original 200-proposal seed, order, classes (100 good, 40 harmful, 60 neutral), complete paired outcome streams, 100-item study cap, bet 0.3, futility E <= 0.05, three-net-win plateau and five-stratum coverage. Reproduce all original published metrics exactly before interpreting new variants. The slice power target is 80% of 100/100 good accepts, hence 80/100. The matched-fresh slice sensitivity is separately reported; reuse/correlation differences preclude a causal comparison of gate alone against the naive-reuse arm.

One-component ablations use identical full simulated streams: wallet off changes only primary study alpha from 0.00025 to 0.05; plateau off changes the required net-win floor from three to zero; stratum-veto off disables only the reverse-e-process veto; bet doubled changes the shared betting fraction from 0.3 to 0.6. Stratum coverage, domain veto and every other parameter remain fixed. In particular, wallet off leaves the reverse-veto alpha at 0.00025 so that its safety threshold is not a second intervention. Class labels are available only to generation and reporting, never to decisions or wealth allocation.

The separately registered investing variant keeps original gate parameters and changes only primary study allocation. Start wealth W=0.05; before each study debit phi=min(0.1 W, 0.05/0.95), use alpha=min(0.05, phi/(1+phi)), and on a terminal promotion credit phi+0.05 (refund the debit plus the registered 0.05 bonus). On any nonpromotion credit zero. No overlapping studies, duplicated rewards, negative wealth or post-outcome changes to the allocation are allowed. This is the standard nonrejection-cost/rejection-reward alpha-investing update expressed as an advance debit and refund. The fraction is a prospective choice, not fitted to this rerun. No parameter/seed search or target-driven retuning is planned.

Alpha-investing targets mFDR_1 under its conditional-null assumptions; it is not a replacement for a family-wise error guarantee across arbitrary mixtures. See Foster and Stine, [Alpha-investing](https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Alpha-investing.pdf). We report two distinct empirical null checks: the original 10,000 independent, fair-discordant, 200-item streams at alpha=0.05 with no futility, and the same mechanism at the actual first investing allocation. To exercise wealth updates and rewards, additionally run 10,000 independent all-null portfolios of 200 studies each, with the actual 100-item cap, futility, plateau and round-robin stratum coverage. Report the proportion of portfolios with any false promotion, false promotions per study and mFDR_1. Passing the all-null check does not establish strong FWER under mixtures or prove a population harmful-accept rate <=1% from forty harmful proposals.

All new simulated draws occur only after an exclusive source-hashed registration. This research script does not modify the wallet, journal, gate, registry or installation paths. Network calls are denied during execution. Eight CPU fixture tests passed before study execution, including comparison with the original process, reward/debit discipline and ablation isolation. Stop after reporting: no model calls, real bank/reserve access, signing or installation.

## Results

The original 200 study verdicts, stopping counts, log-e values and net wins reproduced exactly, as did the 436/10,000 original H0 crossings. New registration SHA: `308c41c03a3958e4aca43297d8275305c1c745586907826b503816f9c03e0d0c`. All 200 investing debit/reward transitions independently reconciled; all registered source hashes remained unchanged.

| Variant | Good accepted | Harmful accepted | Items consumed |
|---|---:|---:|---:|
| Slice, naive reuse | 100/100 (100%) | 0/40 (0%) | 20,000 |
| Slice, matched fresh sensitivity | 97/100 (97%) | 2/40 (5%) | 20,000 |
| Original sequential | 0/100 (0%) | 0/40 (0%) | 16,386 |
| Alpha-wallet off | 48/100 (48%) | 0/40 (0%) | 14,457 |
| Plateau off | 0/100 (0%) | 0/40 (0%) | 16,386 |
| Per-stratum veto off | 0/100 (0%) | 0/40 (0%) | 16,386 |
| Bet doubled (0.6) | 4/100 (4%) | 0/40 (0%) | 9,280 |
| Alpha-investing | 0/100 (0%) | 0/40 (0%) | 16,386 |

The investing variant's four operational figures are **0% harmful acceptance, 0% good acceptance, 16,386 items, and 1.75% all-null portfolio type-I rate (175/10,000 portfolios)**. It fails the power target of at least 80%. It earned no rewards in the 200-proposal mixture, so wealth decayed to approximately 3.53e-11; the potential reward could not bootstrap power. The all-null portfolios did exercise rewards: 182 total false promotions occurred in 175 portfolios. No study parameters were retuned after these results.

The original matched H0 diagnostic again gave **4.36% (436/10,000)** at alpha=5%, 200-item horizon, no futility. At the actual first investing allocation alpha=0.004975124378109454, that same diagnostic gave **0.32% (32/10,000)**. This single-study check does not exercise reinvestment. The separate 10,000 all-null investing portfolios each contain 200 studies with the actual gate stopping rules: family-wise type-I was **1.75%**, below the registered 5% empirical target; 182/2,000,000 studies promoted falsely, and empirical mFDR_1 was 1.7875%. These null diagnostics have different estimands and must not be interchanged. All-null FWER does not establish strong FWER for mixtures.

Wallet removal produced the largest observed power gain (48/100), still below target. Removing plateau or stratum veto alone made no difference on these streams. Doubling the bet accepted 4/100 good proposals and stopped earlier overall. This does not establish a universal zero-power result for the baseline or an optimal investing policy. Zero harmful accepts out of forty remains too little evidence to establish a population harmful-accept rate <=1%.

Public receipts: `evidence/sequential-investing-v1-registration.json`, `evidence/sequential-investing-v1-result.json`, and `evidence/sequential-investing-v1-verification.json`. Reproduce in a new exclusive directory with `python3 scripts/study_sequential_investing.py /absolute/new/output`. No canonical code, wallet, retained registry or trust was changed. No gate is installed or signable on these results; all work used simulated scores, zero model calls and zero real holdout access.
