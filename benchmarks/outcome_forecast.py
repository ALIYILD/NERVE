"""Frozen synthetic evaluation: changing environments AND stationary adverse control."""
import json
from pathlib import Path
import random
from statistics import mean
from nerve_awim.outcome_forecast import summarize_outcomes


def run():
    protocol=json.loads(Path(__file__).with_name('outcome_forecast_protocol.json').read_text())
    results={}
    for name,probabilities in protocol['regimes'].items():
        runs=[]
        for seed in protocol['evaluation_seeds']:
            rng=random.Random(seed)
            rows=[]
            for probability in probabilities:
                for _ in range(protocol['observations_per_regime']):
                    i=len(rows)
                    rows.append(dict(id=str(i),observed_at=i,success=rng.random()<probability))
            value=summarize_outcomes(rows,window=protocol['window'],warmup=protocol['warmup'])
            runs.append({'seed':seed, **value})
        metrics={arm:mean(row['brier'][arm] for row in runs) for arm in runs[0]['brier']}
        results[name]={'mean_brier':metrics,'runs':runs,
            'adaptive_beats_expanding_seeds':sum(r['brier']['adaptive']<r['brier']['expanding'] for r in runs),
            'adaptive_beats_frozen_seeds':sum(r['brier']['adaptive']<r['brier']['frozen'] for r in runs)}
    return {'protocol':protocol,'results':results,'production_promotion':False,
        'claim_scope':'Synthetic sequential prediction; host integration and live efficacy are separate evidence.',
        'selection_or_retuning_performed':False}


if __name__=='__main__': print(json.dumps(run(),indent=2))
