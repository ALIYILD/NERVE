"""Dev-only one-seam router; never installs or alters retained implementations.

Fallback targets retained B-v4 only when canonical A-v3 declares unsupported
input grammar. This is a new unevaluated composite candidate, not a retained skill.
"""
from . import scientific_candidate_v3 as family_a
from . import scientific_family_b_v4 as family_b


def prepare(query,evidence):
    incumbent=family_a.prepare(query,evidence,arm='candidate')
    if incumbent['gate_reason'] in ('unsupported_query','unsupported_evidence'):
        return {'selected_skill':'family-b-v4','prepared':family_b.prepare(query,evidence)}
    return {'selected_skill':'scientific-v3','prepared':incumbent}
