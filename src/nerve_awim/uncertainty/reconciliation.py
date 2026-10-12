"""Host-defined structured normalization; no source is trusted by repetition."""
import json
UNITS={'mg':('mass',.001),'g':('mass',1.),'kg':('mass',1000.),'cm':('length',.01),'m':('length',1.)}
def normalized(claim):
    value=claim.normalized_value;units=claim.units
    if type(value) in (int,float) and units in UNITS:
        units,factor=UNITS[units];value=round(value*factor,12)
    if type(value) is bool:
        value=value if claim.polarity else not value
        polarity=True
    else:polarity=claim.polarity
    return value,units,polarity

def comparable(a,b):
    if (a.subject_ref,a.predicate,a.context)!=(b.subject_ref,b.predicate,b.context):return False
    if max(a.valid_from,b.valid_from)>=min(a.valid_to if a.valid_to is not None else float('inf'),b.valid_to if b.valid_to is not None else float('inf')):return False
    return normalized(a)[1]==normalized(b)[1]

def contradicts(a,b):
    if not comparable(a,b):return False
    av,_,ap=normalized(a);bv,_,bp=normalized(b)
    if av is None or bv is None:return False
    if ap and bp:return av!=bv
    if not ap and not bp:return False
    return av==bv

def family(claim):
    # Applicable interval stays in key to avoid unrelated historical disputes.
    return json.dumps([claim.subject_ref,claim.predicate,claim.context,claim.valid_from,claim.valid_to,normalized(claim)[1]],sort_keys=True)
