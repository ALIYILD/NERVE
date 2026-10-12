# Source-backed reproduction protocol

Sources checked 2026-10-12: [paper v1](https://arxiv.org/html/2610.06851v1), [arXiv record](https://arxiv.org/abs/2610.06851), [author repository](https://github.com/sophicle/cues). Local unit fixtures do not reproduce the paper.

## Research baseline

The paper studies response-prefix tokens, mainly in base models. Selection uses beam width 20 and depth two, retains 20 openings, samples 16 continuations on 30 training problems, excludes candidates exceeding the baseline missing-answer rate by 0.10, and minimizes mean answer entropy. Evaluation uses 32 rollouts per problem, temperature 0.6, top-p 0.95 and a 31,744-token limit. Olmo-3-7B uses the RL-Zero prompt; Qwen3-14B uses the boxed prompt. The reported MATH-500 changes are approximately 42%→78% and 72%→87%, respectively. These are external results, not NERVE measurements. Prefix effects depend on model and prompt, and safety behavior can change. See [§2, §4 and Appendix B](https://arxiv.org/html/2610.06851v1).

## Author implementation discrepancy

The [author README](https://github.com/sophicle/cues) describes 100 beam-proposal problems followed by 30 screening problems, whereas paper §2.1 describes 30 proposal problems. Also, `cues eval` defaults to 16 rollouts; `scripts/eval_grid.sh` combines two batches of 16. The documented runtime needs Linux, NVIDIA CUDA 13 support and downloaded model weights. Its five-problem demo is explicitly incomplete. Do not report a README-default run as an exact paper reproduction without recording these differences.

## NERVE experiment contract

The following requirements are NERVE engineering decisions, separate from paper claims:

1. Pin the author repository commit, model weight revision, tokenizer files, dataset revision, grading package versions and container digest before generation. Save hashes and license references. `git ls-remote` resolved author-code HEAD to `cd9caabe748307df0565502f630e3a834a9f998d` on 2026-10-12; use that immutable revision rather than a moving branch. Weights, datasets and GPU container still require provisioning and recorded hashes.
2. Maintain two explicit proposal variants (`paper-30` and `author-code-100`) when investigating the discrepancy. Never tune a variant against final benchmark answers. A smaller local fixture must carry `fixture` status.
3. Declare a maximum GPU runtime, generation-call budget and spending cap before starting. Reserve budget before each call. A missing price is unknown, not zero. Persist failures and exhausted budgets in the denominator.
4. Keep training, repeated selection, safety regression and sealed final holdout identifiers/content hashes disjoint. Final holdout is consumed once after candidate selection freezes. Detect renamed duplicate content. Do not send expected answers to candidate generation or Hermes discovery.
5. Compare the same model without cues and with a frozen cue using matched problems, sampling settings and budgets. Include a reviewed prompt-instruction control as a separate experimental arm; never label it token prefill. If available, evaluate the separately pinned RL reference as another arm.
6. Preserve prefix bytes, leading spaces and newlines, full rendered prompt hash and actual token IDs. Verify concatenation at the response boundary using the exact tokenizer; separately encoding a cue can differ from encoding the complete prompt.
7. Grading must be independent of discovery. Freeze math extraction and equivalence rules before the final run. Execute generated code only in a reviewed resource-limited sandbox. Infrastructure failure is recorded distinctly but never dropped from the completion denominator.
8. Report per-arm coverage, pass@1, paired accuracy change with uncertainty, missing-answer rate, invalid-answer rate, token-cap rate, latency and measured token usage. Report safety failures separately from correctness. Keep JEV opinion separate from deterministic evaluation and do not relabel it calibrated probability of answer correctness.
9. Save resumable receipts keyed by complete experiment identity. Reuse is invalid after changing model, tokenizer, cue, template, dataset, grader or sampling settings. Raw responses remain in the approved research environment; public artifacts contain synthetic/public aggregates and provenance.
10. Require complete expected coverage before marking a benchmark reproduced. Predeclare a numerical replication tolerance and comparison method; investigate any mismatch without retroactively changing acceptance rules. Negative or null findings are publishable outcomes.

## Execution handoff

On a provisioned research GPU host, follow the pinned author setup and review its commands before execution. The following are reference invocations documented by the author; they have **not** been executed in this implementation session:

```bash
python -m cues demo --model olmo7b --dry-run
python -m cues search --model qwen14b --prompt boxed
python -m cues eval --model olmo7b --benchmark math500 --cues none auto --n-rollouts 32
```

Before the last command, supply the frozen prompt, sampling, seed, dataset and output settings from the experiment manifest. The no-cue and cue arms must both complete. Do not install the GPU stack into NERVE's ordinary CI environment.

## Current evidence boundary

Full benchmark reproduction, model/tokenizer profiling on downloaded weights, live provider compatibility, clinical evaluation and external staging are not evidenced by this document. A functioning offline harness may satisfy its software contract while all these empirical gates remain open. Required evidence is an immutable manifest plus independently graded run receipts, not a screenshot or an agent's completion statement.
