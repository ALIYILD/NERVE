#!/usr/bin/env python3
"""Validate a saved study and decompose training prediction errors; no trials."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway import evidence_window_study as study


def audit(directory, claims, supervisor):
    path = Path(directory)/'report.json'
    before = path.read_bytes()
    study.validate_receipt(directory, claims, supervisor)
    if before != path.read_bytes(): raise ValueError('receipt_changed')
    report = json.loads(before)
    aggregates = {}
    maximum_residual = 0.
    for row in report['rows']:
        if row['split'] != 'train': continue
        previous = 0.
        for step in row['episode']['trace']:
            state = .82*(step['estimated_velocity']-previous)
            gain = (step['estimated_gain']-step['true_gain'])*step['action']
            residual = abs(state+gain-(step['predicted_velocity']-step['true_velocity']))
            maximum_residual = max(maximum_residual, residual)
            if residual > 1e-10: raise ValueError('prediction_identity_failed')
            key = (row['arm'],row['episode']['scenario'],step['action_source'])
            item = aggregates.setdefault(key, {'steps':0,'state':0.,'gain':0.,'error':0.,'cancellation':0.})
            item['steps'] += 1
            item['state'] += abs(state); item['gain'] += abs(gain)
            item['error'] += step['prediction_error']
            item['cancellation'] += abs(state)+abs(gain)-abs(state+gain)
            previous = step['true_velocity']
    return {'protocol':'prediction-error-identity-audit-v1',
            'identity':'error = retention*(estimated_velocity - previous_true_velocity) + (estimated_gain - true_gain)*actual_action',
            'maximum_identity_residual':maximum_residual,
            'groups':[{'arm':key[0],'scenario':key[1],'action_source':key[2],
                       'steps':value['steps'], **{'mean_absolute_'+name: value[name]/value['steps']
                                               for name in ('state','gain','error')},
                       'mean_cancellation':value['cancellation']/value['steps']}
                      for key,value in sorted(aggregates.items())],
            'new_episodes':0, 'heldout_outcomes_analyzed':False,
            'interpretation':'Exact algebra, not independent additive causal contributions; ground truth for retrospective scoring only.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('study','claims','supervisor'): parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.study,args.claims,args.supervisor),sort_keys=True,indent=2))
