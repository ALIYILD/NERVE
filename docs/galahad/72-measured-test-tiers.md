# Measured fast and slow test tiers

The original two-line change to `scripts/verify_galahad.py` added
`test_experience_store_v2.py`, `test_scientific_format_episode_import.py` and
`test_scientific_format_feedback.py` to both the CPU and security groups.
These exercise the new storage and outcome feedback path. That original diff
did not change baseline discovery or timeouts. Subsequent requested changes add
`profile`, `fast` and `slow` gates with an explicit timing report and manifest.

## Clean profile

A single serial unittest runner completed 2,044 tests in 225.761 seconds
(226.770 seconds including discovery/report setup), with zero failures,
errors or skipped tests. Exact IDs are captured before test execution, because
some tests mutate attributes named `id`. The runner has a multiprocessing-safe
main guard and propagates `PYTHONPATH` to subprocess fixtures. Existing tests may
launch child processes; there are no parallel suite workers.

An earlier baseline command timed out after 600 seconds. Temporary completion
harness attempts had import-path, multiprocessing-entry-point and post-run ID
collection bugs; those runs are not counted as passing evidence. This clean
profile supersedes them. The profile ceiling was 1,800 seconds because the
600-second attempt was incomplete; it is not the fast-tier deadline.

## Twenty slowest tests

| Full test ID | Seconds |
|---|---:|
| `test_recovery_gain_diagnostic.RecoveryGainDiagnosticTests.test_missing_duplicate_changed_identity_rejected` | 4.773 |
| `test_recovery_gain_diagnostic.RecoveryGainDiagnosticTests.test_receipt_validation_and_snapshot_changes` | 4.147 |
| `test_evidence_gated_study.EvidenceGatedStudyTests.test_actual_claim_selection_freeze_and_full_graph` | 3.594 |
| `test_evidence_gated_study.EvidenceGatedStudyTests.test_journal_and_roster_cannot_be_omitted_or_relabelled` | 3.523 |
| `test_scientific_candidate_route_audit.ScientificCandidateRouteAuditTests.test_replay_bytes_mtime_and_sources_unchanged` | 3.281 |
| `test_research_orchestrator.ResearchOrchestratorTests.test_journal_fail_closed` | 2.755 |
| `test_evidence_window_study.EvidenceWindowStudyTests.test_actual_claim_selection_freeze_and_full_graph` | 2.667 |
| `test_online_optimisation.OnlineOptimisationTests.test_selected_once_before_holdout_and_exact_accounting` | 2.629 |
| `test_memory_automation.AutomaticLearningTests.test_durable_episode_quota_covers_failed_and_pending_claims` | 2.514 |
| `test_evidence_window_study.EvidenceWindowStudyTests.test_journal_and_roster_cannot_be_omitted_or_relabelled` | 2.433 |
| `test_online_optimisation.OnlineOptimisationTests.test_holdout_regression_no_retuning` | 2.401 |
| `test_scientific_candidate_route_audit.ScientificCandidateRouteAuditTests.test_private_output_and_bank_required` | 2.287 |
| `test_scientific_candidate_route_audit.ScientificCandidateRouteAuditTests.test_real_700_three_candidates_2100_preparations_no_answer_metadata` | 2.165 |
| `test_scientific_candidate_route_audit.ScientificCandidateRouteAuditTests.test_cli_real_audit_no_execution` | 2.099 |
| `test_recovery_gain_diagnostic.RecoveryGainDiagnosticTests.test_tampered_trace_and_learning_evidence_rejected` | 2.042 |
| `test_research_campaign.ResearchCampaignTests.test_real_spawn_trial` | 1.975 |
| `test_evidence_gated_study.EvidenceGatedStudyTests.test_validation_rejection_does_not_try_runner_up_or_holdout` | 1.951 |
| `test_recovery_gain_diagnostic.RecoveryGainDiagnosticTests.test_heldout_payload_is_never_analyzed` | 1.893 |
| `test_configurable_online_trial.ConfigurableOnlineTrialTests.test_legacy_baseline_and_candidate_execution_preserved` | 1.869 |
| `test_dynamics_factorial_study.DynamicsFactorialStudyTests.test_actual_claim_selection_freeze_and_full_graph` | 1.790 |

## Partition and deadlines

The initial 120-second measured budget predicted 116.853 seconds for fast, but
its actual run reached the hard 180-second deadline near the end. It is recorded
as a timeout, not a passing fast-tier run. The checked-in manifest was rebalanced
from the same measured module costs to a 60-second target; 43 modules now belong
to slow. Two compact transport guard tests were added after the profile, and the
seed setting was hardened; the updated transport remains in fast.

The final estimates are 58.810 seconds fast and 181.097 seconds slow, including
all measured discovery/fixture overhead in each tier. The fast deadline remains
180 seconds. Slow receives `ceil(2 × 181.097 + 60) = 423` seconds, justified by the
observed first-fast variability rather than the original 1.5 multiplier. Timeout
terminates the whole gate process group to avoid orphaned fixtures.

The actual rebalanced fast tier passed **1,547 tests in 87.578 seconds**, or
**89.318 seconds including discovery/setup**. Zero failures, errors or skips;
all selected IDs are covered. New test modules default to fast, so later changes
must be measured again before asserting the same bound. Timing is an observation
on this machine, not a universal runtime guarantee.

[Full profile](evidence/suite-profile-v1.json). The manifest is
`tests/suite_tiers.json`; raw test and module durations remain inspectable.

```bash
.venv/bin/python scripts/verify_galahad.py profile --timings /private/tmp/nerve-suite-profile.json --timeout-seconds 1800
.venv/bin/python scripts/timed_test_runner.py freeze --profile /private/tmp/nerve-suite-profile.json --manifest tests/suite_tiers.json --fast-budget-seconds 60
.venv/bin/python scripts/verify_galahad.py fast --timings /private/tmp/nerve-suite-fast.json
.venv/bin/python scripts/verify_galahad.py slow --timings /private/tmp/nerve-suite-slow.json
```

The `freeze` command above recomputes a split from a fresh current profile; it
uses its default timeout multiplier. The checked-in adjusted manifest preserves
the original measurement and explicitly records the observed-timeout adjustment.

## Clean tier acceptance

The slow tier ran once in a clean serial runner: **499 tests passed in
168.745 seconds**, or 169.922 seconds including discovery/setup,
within its 423-second deadline. No failures, errors or skips. The two selected-ID
sets are disjoint and together cover all **2,046 current tests**. The two extra
tests relative to the profile exercise compact transport callback guards.

[Fast run](evidence/suite-fast-v2.json), [single clean slow run](evidence/suite-slow-v1.json).
