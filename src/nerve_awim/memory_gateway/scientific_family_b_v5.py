"""Doc113 deterministic numeric agreement and smallest-source candidate.

Uses only query/evidence, never a task ID, stratum, expected label or model.
The existing family-B parser and input bounds are unchanged.
"""
from decimal import Decimal,InvalidOperation
from . import scientific_family_b_adapter as adapter
from .scientific_candidate_execution import ABSTAIN

def decide(query,evidence):
    try:
        prepared=adapter.prepare(query,evidence,'adapted_v1')
        entity=adapter.QUERY.fullmatch(query).group(1)
        matching=[r for r in prepared['records'] if r['current'] and
                  (r['entity'],r['measurement'],r['unit'])==(entity,'mass','mg')]
        if not matching or len({Decimal(r['value']) for r in matching})!=1:
            return dict(ABSTAIN)
        selected=min(matching,key=lambda r:r['source_id'])
        return {'status':'answer','entity':selected['entity'],'measurement':selected['measurement'],
                'value':format(Decimal(selected['value']),'f'),'unit':selected['unit'],'source_id':selected['source_id']}
    except (ValueError,TypeError,KeyError,InvalidOperation):
        return dict(ABSTAIN)
