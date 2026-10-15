"""Fresh repository-code evaluation, including a capable fixed-tool control."""
import random
import tempfile
import time
from pathlib import Path
from .adaptation_repository import run_sources


def benchmark_repository(manifest, *, split):
    scenarios=[e for e in manifest['episodes'] if e['split']==split]
    if not scenarios:raise ValueError('empty repository evaluation split')
    rows={p:[] for p in ('baseline','structured','corrections','strong-baseline')}
    with tempfile.TemporaryDirectory() as root:
        for i,scenario in enumerate(scenarios):
            # Rotate order to reduce systematic warm-cache timing bias.
            order=list(rows);order=order[i%4:]+order[:i%4]
            for policy in order:
                started=time.perf_counter()
                value=run_sources(str(Path(root)/(scenario['id']+'-'+policy+'.db')),scenario['files'],policy=policy,mode='off' if policy in ('baseline','strong-baseline') else 'active-development',restart=scenario['restart'],task_id=scenario['id'])
                rows[policy].append({'id':scenario['id'],'family':scenario['family'],'success':value['success'],'seconds':time.perf_counter()-started,'actions':len(value['attempts']),'review_probes':value['review_probes'],'correction_reuse':value['correction_reuse'],'resumed':value['resumed'],'receipt_count':value['receipt_count'],'verified_outputs':len(value['outputs']),'required_outputs':len(scenario['files']),'provider_calls':value['provider_calls']})
    for values in rows.values():values.sort(key=lambda r:r['id'])
    def difference(control):
        delta=[int(a['success'])-int(b['success']) for a,b in zip(rows['corrections'],rows[control])]
        rng=random.Random(730); means=sorted(sum(rng.choices(delta,k=len(delta)))/len(delta) for _ in range(2000))
        return {'difference':sum(delta)/len(delta),'paired_bootstrap_95':[means[49],means[1949]]}
    vs_fixed=difference('baseline');vs_strong=difference('strong-baseline')
    summary={}
    for policy,values in rows.items():
        timings=sorted(v['seconds'] for v in values)
        summary[policy]={'successes':sum(v['success'] for v in values),'episodes':len(values),'p95_total_seconds':timings[min(len(timings)-1,int(.95*len(timings)))],'actions':sum(v['actions'] for v in values),'review_probes':sum(v['review_probes'] for v in values),'correction_reuse':sum(v['correction_reuse'] for v in values),'rows':values}
    overhead=summary['corrections']['p95_total_seconds']/summary['strong-baseline']['p95_total_seconds']-1
    return dict(schema='adaptation-repository-report-v2',split=split,suite_digest=manifest['episodes_digest'],policies=summary,paired_success_difference=vs_strong['difference'],paired_bootstrap_95=vs_strong['paired_bootstrap_95'],against_fixed_regex=vs_fixed,overhead_ratio=overhead,overhead_gate_passed=overhead<=.2,hard_gates_passed=all(v['actions']+v['review_probes']<=5 and v['provider_calls']==0 and (not v['success'] or v['verified_outputs']==v['required_outputs']) for values in rows.values() for v in values),benefit_claim='Compared against the capable AST fixed baseline; recovery from an inferior tool is not general learning superiority.',uncertainty_unit='synthetic episode; related templates limit generalisation',provider_verified=False,production_approved=False,prior_attempt='adaptation-v1 rejected; old heldout never reused')
