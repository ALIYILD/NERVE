"""Second fixed repository repair cohort; curated faults, not production incidents.

No v1 function is repeated. Shared modules/domains mean these small fixtures
are not evidence of broad generalization. All three selection functions share
the plan/advice domain and must not be counted as independent domains. Constructors are replaced by declared
inert value adapters; candidate functions are extracted unchanged from source.
"""
from hashlib import sha256
from pathlib import Path
from .agentos_taskbench import RepairTask, _function, _BUILTINS, _ATTRS

PLAN = '''EXTRACT = ('raw','json-field')
NORMALISE = ('lower-only','trim-lower')
ALLOWED = {(a,b) for a in EXTRACT for b in NORMALISE}
def Plan(extract_strategy, normalise_strategy):
    if extract_strategy not in EXTRACT or normalise_strategy not in NORMALISE:
        raise ValueError('unregistered plan')
    return (extract_strategy,normalise_strategy)
'''
GENOME = '''def RetrievalGenome(token_weight=3,trigram_weight=0):
    if type(token_weight) is not int or not 0<=token_weight<=5:
        raise ValueError('token weight')
    if type(trigram_weight) is not int or not 0<=trigram_weight<=5:
        raise ValueError('trigram weight')
    if token_weight+trigram_weight<1:
        raise ValueError('empty features')
    return (token_weight,trigram_weight)
'''
COPY = '''def deepcopy(value):
    if type(value) is dict:
        return {k:deepcopy(v) for k,v in value.items()}
    if type(value) is list:
        return [deepcopy(v) for v in value]
    if type(value) is tuple:
        return tuple(deepcopy(v) for v in value)
    return value
'''


def dataset(repo_root=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    specs = [
        ('train','recursive_evolution_v19.py','grams','TOKENS = re.compile(r"[a-z0-9]+")\n',
         'len(value)-2','len(value)-3',
         'Lowercase, extract ASCII alphanumeric tokens, join with one space, return the SET of every contiguous length-3 substring (including spaces). Empty/short normalized text yields empty set.',
         ('assert fn("ABC") == {"abc"}', 'assert fn("abcd") == {"abc","bcd"}',
          'assert fn(" A!!B  C ") == {"a b"," b ","b c"}', 'assert fn("ab") == set()',
          'assert fn("") == set()', 'assert fn("AAAAA") == {"aaa"}', 'assert fn("éA") == set()')),
        ('train','agent_study_v15.py','_format','FORMATS = ("json_email","plain_email")\n',
         'value not in FORMATS','value in FORMATS',
         'Return only an exact str equal to json_email or plain_email. Reject every other value with ValueError, including str subclasses.',
         ('assert fn("json_email") == "json_email"','assert fn("plain_email") == "plain_email"',
          'raises(ValueError,fn,"")','raises(ValueError,fn,"JSON_EMAIL")','raises(ValueError,fn,None)',
          'raises(ValueError,fn,[])','raises(ValueError,fn,type("Text",(str,),{})("json_email"))')),
        ('selection','agent_study_v15.py','_plan_from_id',PLAN,
         'tuple(parts) not in ALLOWED','tuple(parts) in ALLOWED',
         'Accept only exact strings of at most40 characters split by | into exactly two registered identifiers from ALLOWED; return Plan(*parts). Plan is the supplied inert tuple adapter.',
         ('assert fn("raw|lower-only") == ("raw","lower-only")',
          'assert fn("json-field|trim-lower") == ("json-field","trim-lower")',
          'assert fn("raw|trim-lower") == ("raw","trim-lower")',
          'raises(ValueError,fn,"raw|unknown")','raises(ValueError,fn,"raw|trim-lower|extra")',
          'raises(ValueError,fn,True)','raises(ValueError,fn,type("Text",(str,),{})("raw|trim-lower"))','raises(ValueError,fn,"x"*41)','raises(ValueError,fn,"")')),
        ('selection','llm_agent_v14.py','parse_plan',PLAN,
         'set(raw) != {','set(raw) < {',
         'Parse nonempty string JSON of at most1024 characters with EXACTLY extract_strategy and normalise_strategy string fields; reject extra/missing fields with ValueError; return validated Plan using supplied tuple adapter.',
         ('assert fn(\'{"extract_strategy":"raw","normalise_strategy":"trim-lower"}\') == ("raw","trim-lower")',
          'raises(ValueError,fn,\'{"extract_strategy":"raw","normalise_strategy":"trim-lower","extra":"text"}\')',
          'raises(ValueError,fn,"{}")','raises(ValueError,fn,"[]")','raises(ValueError,fn,False)',
          'raises(ValueError,fn,\'{"extract_strategy":true,"normalise_strategy":"trim-lower"}\')',
          'raises(ValueError,fn,\'{"extract_strategy":"unknown","normalise_strategy":"trim-lower"}\')',
          'raises(ValueError,fn," "*965+\'{"extract_strategy":"raw","normalise_strategy":"trim-lower"}\')','assert fn(" "*964+\'{"extract_strategy":"raw","normalise_strategy":"trim-lower"}\') == ("raw","trim-lower")')),
        ('selection','llm_agent_v14.py','_advice',PLAN,
         'advice["extract"] not in EXTRACT or advice["normalise"] not in NORMALISE',
         'advice["extract"] not in EXTRACT and advice["normalise"] not in NORMALISE',
         'None returns the exact existing no-feedback sentence. Otherwise require a dict with exactly extract and normalise, both registered in EXTRACT/NORMALISE; return json.dumps with sorted keys. Invalid recommendations raise ValueError.',
         ('assert fn(None) == "No previous outcome feedback was retrieved."',
          'assert fn({"normalise":"trim-lower","extract":"raw"}) == \'{"extract": "raw", "normalise": "trim-lower"}\'',
          'raises(ValueError,fn,{"extract":"unknown","normalise":"trim-lower"})',
          'raises(ValueError,fn,{"extract":"raw","normalise":"unknown"})',
          'raises(ValueError,fn,{})','raises(ValueError,fn,False)',
          'raises(ValueError,fn,{"extract":"raw","normalise":"lower-only","extra":1})')),
        ('retention','agent_bridge_v13.py','_extract_json',_function(root,'agent_bridge_v13.py','_validate_email'),
         'set(document) != {"email"}','"email" not in document',
         'Parse JSON object with exactly one email field. Pass its value unchanged to _validate_email (string raw length1..180). Reject extra/missing keys, nonobjects or bad field values with ValueError; do not normalize.',
         ('assert fn(\'{"email":" A@B.COM "}\') == " A@B.COM "','raises(ValueError,fn,\'{"email":"a","extra":1}\')',
          'raises(ValueError,fn,"{}")','raises(ValueError,fn,"[]")','raises(ValueError,fn,\'{"email":false}\')',
          'raises(ValueError,fn,\'{"email":""}\')','assert fn(\'{"email":"\'+"a"*180+\'"}\') == "a"*180',
          'raises(ValueError,fn,\'{"email":"\'+"a"*181+\'"}\')')),
        ('retention','research_checkpoint_v19.py','_genome',GENOME,
         'set(value) != {','set(value) > {',
         'Require exact dict with exactly token_weight and trigram_weight keys before constructing RetrievalGenome. Reject any missing/extra keys with ValueError. Supplied constructor enforces exact integers0..5 and positive combined weight and returns their tuple.',
         ('assert fn({"token_weight":3,"trigram_weight":0}) == (3,0)',
          'assert fn({"token_weight":0,"trigram_weight":5}) == (0,5)',
          'raises(ValueError,fn,{})','raises(ValueError,fn,{"token_weight":3})',
          'raises(ValueError,fn,{"token_weight":3,"trigram_weight":0,"extra":1})',
          'raises(ValueError,fn,{"token_weight":0,"trigram_weight":0})',
          'raises(ValueError,fn,{"token_weight":True,"trigram_weight":1})','raises(ValueError,fn,[])')),
        ('retention','recipe_selection.py','select_recipe',COPY+_function(root,'learning_study.py','canonical'),
         '(scores[index], -index)','(scores[index], index)',
         'Preserve all schema, size, independent-bool and call-budget checks. Evaluate every recipe/task pair once on deep copies. Choose highest score, retaining FIRST recipe on ties. Output remains proposal-only. Host deepcopy supports JSON-like values and tuples; canonical is supplied.',
         ('r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; out=fn(r,[1,2,3],evaluate=lambda r,t:True); assert out["recipe"] == r[0] and out["hits"] == [3,3] and not out["improved_on_selection"]',
          'r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; out=fn(r,[1,2,3],evaluate=lambda r,t:r["strategy"]=="y"); assert out["recipe"] == r[1] and out["calls"] == 6 and out["tasks"] == 3 and out["improved_on_selection"] and not out["promotion_authorized"] and out["requires_fresh_evaluation"]',
          'r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; raises(ValueError,fn,r,[1,2,3],evaluate=lambda r,t:True,max_calls=5)',
          'r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; raises(ValueError,fn,r,[1,2,3],evaluate=lambda r,t:1)',
          'r={"prompt":"a","strategy":"x"}; raises(ValueError,fn,[r,r],[1,2,3],evaluate=lambda r,t:True)',
          'r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; raises(ValueError,fn,r,[1,2,3],evaluate=lambda r,t:True,max_calls=True)',
          'r=[{"prompt":str(i),"strategy":"x"} for i in range(17)]\nfor recipes,tasks in ((r[:1],[1,2,3]),(r,[1,2,3]),(r[:2],[1,2]),(r[:2],list(range(101)))):\n raises(ValueError,fn,recipes,tasks,evaluate=lambda r,t:True,max_calls=1000)',
          'r={"prompt":"a","strategy":"x"}\nfor bad in ({"prompt":"b"},{"prompt":"b","strategy":"y","extra":1},{"prompt":"","strategy":"y"},{"prompt":"b"*2049,"strategy":"y"}):\n raises(ValueError,fn,[r,bad],[1,2,3],evaluate=lambda r,t:True)',
          'r=[{"prompt":"a","strategy":"x"},{"prompt":"b","strategy":"y"}]; before=str(r); fn(r,[1,2,3],evaluate=lambda r,t:r.update(prompt="changed") is None); assert str(r)==before')),
        ('final','autoresearch_v05.py','eligibility',
         'MIN_COMPLETION=.95\nMAX_ABORT_FRACTION=0.0\nMAX_VIOLATIONS=0.0\ndef Eligibility(eligible,reasons):\n    return dict(eligible=eligible,reasons=reasons)\n',
         'metrics["completion"]<MIN_COMPLETION','metrics["completion"]<=MIN_COMPLETION',
         'For already validated metrics: completion below .95, abort above0, or violations above0 each add their existing reason in that order. Return Eligibility(not reasons,tuple(reasons)); host constructor is an inert dict adapter. Exact thresholds must pass.',
         ('assert fn(dict(completion=.95,abort=0,violations=0)) == dict(eligible=True,reasons=())',
          'assert fn(dict(completion=1,abort=0,violations=0))["eligible"]',
          'assert fn(dict(completion=.949999,abort=0,violations=0))["reasons"] == ("completion_below_absolute_minimum",)',
          'assert fn(dict(completion=.9,abort=.01,violations=1))["reasons"] == ("completion_below_absolute_minimum","episode_abort_detected","constraint_violation_detected")',
          'assert fn(dict(completion=.95,abort=.000001,violations=0))["reasons"] == ("episode_abort_detected",)',
          'assert fn(dict(completion=.95,abort=0,violations=.000001))["reasons"] == ("constraint_violation_detected",)')),
        ('final','study_statistics_v16.py','_simple','',
         '(with_mem - without) / n','(without - with_mem) / n',
         'For a nonempty list of validated paired boolean rows, preserve counts and accuracies, and compute signed delta as with-memory accuracy minus no-memory accuracy. Error flags count independently of success.',
         ('r=[dict(no_memory=False,with_memory=True,no_memory_error=True,with_memory_error=False)]; out=fn(r); assert out["paired_accuracy_delta"] == 1 and out["memory_only_success"] == 1 and out["no_memory_task_errors"] == 1',
          'r=[dict(no_memory=True,with_memory=False,no_memory_error=False,with_memory_error=True)]; out=fn(r); assert out["paired_accuracy_delta"] == -1 and out["no_memory_only_success"] == 1 and out["with_memory_task_errors"] == 1',
          'r=[dict(no_memory=a,with_memory=b,no_memory_error=False,with_memory_error=False) for a in (True,False) for b in (True,False)]; out=fn(r); assert out["task_pairs"] == 4 and out["both_success"] == out["both_fail"] == out["memory_only_success"] == out["no_memory_only_success"] == 1 and out["paired_accuracy_delta"] == 0 and out["no_memory_accuracy"] == out["with_memory_accuracy"] == .5',
          'out=fn([dict(no_memory=True,with_memory=True,no_memory_error=True,with_memory_error=True)]); assert out["both_success"] == out["no_memory_task_errors"] == out["with_memory_task_errors"] == 1',
          'r=[dict(no_memory=False,with_memory=True,no_memory_error=False,with_memory_error=False)]*2+[dict(no_memory=True,with_memory=True,no_memory_error=False,with_memory_error=False)]; assert abs(fn(r)["paired_accuracy_delta"]-2/3)<1e-12')),
        ('final','agentos_experiments.py','checked_budget',_function(root,'agentos_experiments.py','encode'),
         'type(v) is not int','not isinstance(v, int)',
         'Require exact dict with exactly max_tokens,max_iterations,timeout_seconds, each EXACT int1..100000 inclusive (bool forbidden); return encode(value). Invalid schemas or values raise ValueError.',
         ('assert fn(dict(max_tokens=1,max_iterations=100000,timeout_seconds=90)) == \'{"max_iterations":100000,"max_tokens":1,"timeout_seconds":90}\'',
          'raises(ValueError,fn,dict(max_tokens=True,max_iterations=2,timeout_seconds=90))',
          'raises(ValueError,fn,dict(max_tokens=1,max_iterations=True,timeout_seconds=90))',
          'raises(ValueError,fn,dict(max_tokens=1,max_iterations=2,timeout_seconds=True))',
          'raises(ValueError,fn,dict(max_tokens=1,max_iterations=0,timeout_seconds=90))',
          'raises(ValueError,fn,dict(max_tokens=1,max_iterations=2,timeout_seconds=100001))',
          'raises(ValueError,fn,dict(max_tokens=1.0,max_iterations=2,timeout_seconds=90))',
          'raises(ValueError,fn,{})','raises(ValueError,fn,[])',
          'raises(ValueError,fn,dict(max_tokens=1,max_iterations=2,timeout_seconds=90,extra=1))',
          'base=dict(max_tokens=1,max_iterations=2,timeout_seconds=90)\nfor key in base:\n for value in (0,-1,100001,False,type("Int",(int,),{})(1)):\n  bad=dict(base); bad[key]=value; raises(ValueError,fn,bad)',
          'assert fn(dict(max_tokens=100000,max_iterations=100000,timeout_seconds=100000)) == \'{"max_iterations":100000,"max_tokens":100000,"timeout_seconds":100000}\'',
          'raises(ValueError,fn,type("Map",(dict,),{})(max_tokens=1,max_iterations=2,timeout_seconds=90))')),
    ]
    splits={phase:[] for phase in ('train','selection','retention','final')}
    for phase,module,name,preamble,old,new,requirements,checks in specs:
        original=_function(root,module,name)
        if original.count(old)!=1:
            raise ValueError('repository source changed; re-review v2 mutation')
        family=module.removesuffix('.py')+':'+name
        public=dict(id='repair-'+sha256(family.encode()).hexdigest()[:12],family=family,
                    source=preamble+original.replace(old,new,1),function=name,
                    requirements=requirements+' Return JSON {"code":"..."} with exactly one replacement function, same signature. No imports, decorators, annotations, nested functions, global/nonlocal, file/network access, introspection or print. Supplied dependencies are immutable. Available globals: json,re,PurePosixPath,comb,isfinite. Safe builtins: '+','.join(_BUILTINS)+'. Allowed attributes: '+','.join(sorted(_ATTRS))+'. Hidden tests run in an isolated process.',
                    revision=sha256((module+original+preamble).encode()).hexdigest())
        splits[phase].append(RepairTask(public,original,preamble,tuple(checks)))
    return splits
