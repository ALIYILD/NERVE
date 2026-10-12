"""Budgeted CPU sequence experiment; masked predict-before-write evaluation."""
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np
from .module import DIM, VERSION, FastMemory
from .sequence_model import SequenceModel


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def sequence(seed,length):
    rng=np.random.default_rng(seed); mapping=rng.permutation(DIM)
    examples=[]
    for t in range(length):
        if t and t%32==0: mapping=rng.permutation(DIM) # changed task preference
        key=int(rng.integers(DIM))
        examples.append({'key':key,'target':int(mapping[key]),'valid':True,'update':True,'supervise':True})
    return examples


def train_step(examples,rate, *, segment=16):
    # Forward-mode exact derivative of within-segment unrolled inner updates.
    # Reset derivative at truncation boundaries, retain numeric memory state.
    w=np.zeros((DIM,DIM)); derivative=np.zeros_like(w); loss=0.; grad=0.; count=0
    eye=np.eye(DIM)
    for t,event in enumerate(examples):
        if t%segment==0: derivative=np.zeros_like(w)
        if not event['valid']: continue
        k,v=eye[event['key']],eye[event['target']]
        prediction=k@w
        if event['supervise']:
            loss+=np.mean((prediction-v)**2)
            grad+=2*np.mean((prediction-v)*(k@derivative)); count+=1
        if event['update']:
            g=2*np.outer(k,prediction-v)/DIM
            derivative=derivative-g-rate*2*np.outer(k,k@derivative)/DIM
            w=w-rate*g
    return loss/max(count,1),grad/max(count,1)


def validate_budget(budget):
    if type(budget) is not dict or set(budget)!={'max_seconds','max_epochs','max_events','device'}: raise ValueError('explicit complete compute budget required')
    for name,maximum in (('max_seconds',60),('max_epochs',100),('max_events',100000)):
        if type(budget[name]) is not int or not 1<=budget[name]<=maximum: raise ValueError('bounded CPU budget required')
    if budget['device']!='cpu': raise ValueError('this experiment supports CPU only')


def train(config,budget):
    validate_budget(budget)
    if set(config)!={'seed','epochs','episodes','length','segment'} or any(type(v) is not int or v<1 for v in config.values()): raise ValueError('exact positive integer training config required')
    if config['epochs']>budget['max_epochs'] or config['epochs']*config['episodes']*config['length']>budget['max_events']: raise ValueError('training exceeds compute budget')
    start=time.perf_counter(); model=SequenceModel(config['seed']); history=[]
    for epoch in range(config['epochs']):
        losses=[]; gradients=[]
        for i in range(config['episodes']):
            if time.perf_counter()-start>budget['max_seconds']: raise TimeoutError('training compute budget exhausted')
            loss,grad=model.gradients(sequence(config['seed']+i,config['length']),segment=config['segment'])
            losses.append(loss); gradients.append(grad)
        model.optimize({name:np.mean([g[name] for g in gradients],axis=0) for name in model.parameters},step=2.)
        history.append(float(np.mean(losses)))
    artifact=model.memory().checkpoint()
    return dict(schema='fast-memory-experiment-v1',memory=artifact,configuration=config,budget=budget,configuration_digest=digest(config),data_manifest={'generator':'permuted-keys-v1','seeds':list(range(config['seed'],config['seed']+config['episodes'])),'synthetic_only':True},framework={'name':'numpy','version':np.__version__,'license':'BSD-3-Clause','device':'cpu','python':platform.python_version()},slow_parameters=['key_projection','query_projection','value_projection','W0','learning_rate'],fixed_parameters=['one-hot-encoder'],model_parameters=model.serialise(),model_parameters_digest=digest(model.serialise()),training_loss=history,elapsed_seconds=time.perf_counter()-start,sequence_action_forcing='not applicable',production_approved=False)


def evaluate(artifact,suite,budget):
    validate_budget(budget)
    if set(suite)!={'seeds','lengths'} or suite['lengths']!=[16,64,256,1024] or not 2<=len(suite['seeds'])<=10 or any(type(x) is not int or x<1 for x in suite['seeds']): raise ValueError('fixed scaling suite with 2..10 seeds required')
    if set(suite['seeds']) & set(artifact['data_manifest']['seeds']): raise ValueError('training/evaluation seed overlap')
    if sum(suite['lengths'])*len(suite['seeds'])*4>budget['max_events']: raise ValueError('evaluation exceeds event budget')
    if digest(artifact['model_parameters'])!=artifact['model_parameters_digest']: raise ValueError('model parameter digest mismatch')
    trained=SequenceModel(parameters=artifact['model_parameters'])
    FastMemory.restore(artifact['memory'])
    if trained.memory().checkpoint()!=artifact['memory']: raise ValueError('W0 or rate checkpoint mismatch')
    start=time.perf_counter(); result=[]
    for length in suite['lengths']:
        for seed in suite['seeds']:
            examples=sequence(seed,length)
            for variant in ('structured','untrained','trained-static','trained-online'):
                model=trained if variant.startswith('trained') else SequenceModel(101)
                memory=model.memory()
                exact={}; correct=0; eligible=0; mse=0.; updates=0.; reads=0.
                for event in examples:
                    if time.perf_counter()-start>budget['max_seconds']: raise TimeoutError('evaluation compute budget exhausted')
                    k=np.eye(DIM)[event['key']]; v=np.eye(DIM)[event['target']]
                    before=time.perf_counter()
                    prediction=np.eye(DIM)[exact[event['key']]] if variant=='structured' and event['key'] in exact else (np.zeros(DIM) if variant=='structured' else model.read(memory,k))
                    reads+=time.perf_counter()-before
                    if event['valid'] and event['supervise']:
                        correct+=int(np.argmax(prediction)==event['target']); eligible+=1; mse+=float(np.mean((prediction-v)**2))
                    before=time.perf_counter()
                    if event['valid'] and event['update']:
                        if variant=='structured': exact[event['key']]=event['target']
                        elif variant!='trained-static': model.write(memory,k,v)
                    updates+=time.perf_counter()-before
                result.append(dict(length=length,seed=seed,variant=variant,correct=correct,opportunities=eligible,accuracy=correct/eligible,mse=mse/eligible,read_seconds=reads,update_seconds=updates,memory_bytes=memory.weights.nbytes,structured_entries=len(exact),provider_tokens=0,provider_cost_usd=0))
    paired=[]
    for row in result:
        if row['variant']=='trained-online':
            baseline=next(r for r in result if r['seed']==row['seed'] and r['length']==row['length'] and r['variant']=='structured')
            paired.append(row['accuracy']-baseline['accuracy'])
    # Independent seed is the bootstrap unit, not correlated context lengths.
    groups=[float(np.mean([d for d,r in zip(paired,[r for r in result if r['variant']=='trained-online']) if r['seed']==seed])) for seed in suite['seeds']]
    rng=np.random.default_rng(81); bootstrap=np.sort([np.mean(rng.choice(groups,len(groups))) for _ in range(2000)])
    return dict(schema='fast-memory-scaling-v1',suite=suite,suite_digest=digest(suite),checkpoint_digest=artifact['memory']['sha256'],rows=result,paired_accuracy_difference=float(np.mean(groups)),paired_seed_bootstrap_95=[float(bootstrap[49]),float(bootstrap[1949])],benefit_demonstrated=False,interpretation='Toy evidence-class selection only. Structured exact memory is the strong baseline. No agent-level benefit claim.',elapsed_seconds=time.perf_counter()-start,model_generation_seconds=0,total_system_event_storage='variable; not included in fixed weight bytes')
