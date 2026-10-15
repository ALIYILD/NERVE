# External workload goal: close the task-intake connection

The parent aim is to run the existing NERVE adaptation loop against a supplied,
fixed offline workload and complete only if that workload's declared measurable
target is achieved. This extends the synthetic demonstration; it does not turn
fixture results into evidence about real clinical or GPU performance.

| Subloop | Aim | Dependency | Evidence required |
|---|---|---|---|
| Intake/preflight | Accept bounded, typed local tasks and labels | Caller supplies manifest | Schema, domain, exact task and label contracts, declared source and labeler, no duplicate IDs or exact task payloads across partitions |
| Bind goal | Prevent changing data or lowering targets during a run | Validated intake | Canonical SHA-256 of full manifest, including targets/provenance, bound into persistent goal ID |
| Observe | Execute incumbent before applying outcome | Prior phase's monitored state | Exact scope, version, chronological unique observations |
| Detect | Decide whether deterioration warrants adaptation | Observations | Existing minimum-sample, healthy-baseline, cooldown and switch-budget checks |
| Evaluate | Compare allowed strategies on separate tasks | Trigger and remaining evaluation budget | Equal comparison tasks, retained checks, independent Boolean labels, actual call count |
| Switch | Change the next execution strategy within scope | Qualified evaluation | Exact history/version binding, measured improvement, no retained-task loss |
| Monitor | Verify the changed strategy on withheld tasks | Persisted switch state | Fresh outcomes, rollback/cooldown updates, fixed-control measurements |
| Verify goal | Decide whether supplied target was achieved | Every phase and its receipts | Minimum accuracy gain over the best fixed control, each monitoring window's accuracy floor, minimum switches, maximum evaluation calls, and separate synthetic rollback mechanism check |

The parent uses `GoalOrchestrator`, not a second scheduler. Unmet targets block
the parent. A zero candidate-evaluation budget prevents calls before execution;
it cannot become an overspent successful run. Budget, data, scope, labels,
provenance, and thresholds are frozen together. Resuming requires the same
manifest. Changed content fails before any further execution.

## Run it

```sh
python scripts/export_adaptation_workload.py --domain clinical_os --output /tmp/clinical-workload.json
PYTHONPATH=src python -m nerve_awim auto-adapt run --state /tmp/clinical-workload-goal --workload /tmp/clinical-workload.json
PYTHONPATH=src python -m nerve_awim auto-adapt status --state /tmp/clinical-workload-goal --workload /tmp/clinical-workload.json
```

The exporter produces synthetic examples and refuses to overwrite an existing
file. Use `--domain perfflux` for the CPU batch example. Supply independently
prepared workloads using the same contract to evaluate other task collections.
In either application repository:

```sh
python scripts/nerve_auto_adapt.py run --state /tmp/application-goal --workload /path/to/workload.json
```

The application entrypoint pins its domain; a foreign-domain manifest is rejected.
The Agent OS bridge accepts the manifest as `--suite` with `auto-adapt-*` commands.
`tick`, `status`, and `cancel` use the same manifest and state path as `run`.

## Input and target contract

Top-level fields: `schema` (`nerve-adaptation-workload-v1`), `goal_id`, `domain`,
`scope`, `provenance`, `target`, and `phases`. Provenance requires `source_ref`,
`labeler_ref`, and `data_kind`. Allowed kinds are `synthetic` or
`public_nonpatient` for research retrieval, and `synthetic` or `local_cpu` for
batch tasks. These are declarations by a trusted local operator, not automatic
proof of permission, absence of sensitive content, or independent label quality.

Two to four chronological phases each contain four `observe`, four `selection`,
four `retained`, and eight `monitor` episodes. An episode has `id`, `task`, and
`expected`. Clinical tasks contain a query and 2–8 documents with ID, title,
abstract; the expected result references a candidate document. CPU tasks contain
bounded payload strings, a hash-call limit, and a cache-entry limit. CPU digest
labels are recomputed and rejected if incorrect. Retrieval labels need external
expert review; the tool cannot validate relevance from a reference ID alone.

Targets require positive `min_gain` (difference in operational accuracy from
the best fixed strategy), `min_monitor_accuracy` of at least 0.75,
`min_switches` from 1–4, and `max_evaluation_calls` from 0–64. The input file
is capped at one million bytes; duplicate JSON keys and unknown fields fail
validation. Exact duplicate tasks are rejected across all partitions; semantic
overlap and previous studies require external dataset governance.

## What is and is not connected

Connected: local workload intake, fixed measurable goals, scoped strategy registry,
deterministic execution, supplied/recomputed labels, evaluation call accounting,
durable subloop supervision, verified switching and rollback. Existing fallback,
deadline, cancellation, and restart behavior remains active.

Not connected: authenticated remote task ingress, production scheduler activation,
patient workflows, live GPU controls, and independently certified representative
datasets. No model/provider calls or arbitrary commands are accepted from a
manifest. All tasks execute through the existing two registered strategies for
their domain. Successful replay establishes results only on the supplied labeled
tasks; a manifest claiming to be real does not establish real-world efficacy.

Current validation uses exported synthetic workloads. Real representative
workload improvement remains unproven until suitable reviewed data is supplied.
