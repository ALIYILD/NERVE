"""Reproduce bounded cross-task learning on actual source, without providers.

Known repository files are regression fixtures, not an independent holdout.
Each invocation owns disposable state and invokes the normal CLI in fresh processes.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
TRAIN='src/nerve_awim/arc_contracts.py'
EVALUATE=('src/nerve_awim/arc_provider.py','src/nerve_awim/arc_operations.py')


def verify():
    with tempfile.TemporaryDirectory(prefix='nerve-arc-learning-') as state:
        def run(arm, source, *, learn=False, weak=False):
            command=[sys.executable,str(ROOT/'scripts/agentos_bridge.py'),'adaptation-run',
                     '--state',str(Path(state)/arm),'--repository',str(ROOT),'--source',source]
            if learn: command.append('--learn')
            if weak: command.extend(['--scenario','recover-regex'])
            completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            if completed.returncode: raise RuntimeError('repository learning CLI failed: '+completed.stdout)
            return json.loads(completed.stdout)
        training=run('learned',TRAIN,learn=True,weak=True)
        rows=[]
        for source in EVALUATE:
            arms={
                'learned':run('learned',source,learn=True,weak=True),
                'no_memory_recovery':run('no-memory',source,weak=True),
                'strong_ast':run('strong',source),
            }
            rows.append({'source':source,'source_sha256':hashlib.sha256((ROOT/source).read_bytes()).hexdigest(),
                         'arms':{arm:{key:value[key] for key in ('success','attempts','review_probes','memory_decision_id','outputs')} for arm,value in arms.items()}})
        if not training['success'] or len(training['learned_episode_ids'])!=1:
            raise AssertionError('verified recovery was not learned')
        for row in rows:
            a=row['arms']
            if not all(v['success'] for v in a.values()): raise AssertionError('task regression')
            if not a['learned']['memory_decision_id']: raise AssertionError('memory not inherited')
            if not (a['learned']['outputs']==a['strong_ast']['outputs']==a['no_memory_recovery']['outputs']):
                raise AssertionError('outputs differ')
        return {'schema':'arc-cross-task-learning-v1','scope':'local-read-only-repository',
                'training':{'source':TRAIN,'source_sha256':hashlib.sha256((ROOT/TRAIN).read_bytes()).hexdigest(),
                            'actions':len(training['attempts']),'review_probes':training['review_probes']},
                'evaluation':rows,
                'totals':{arm:{'successes':sum(row['arms'][arm]['success'] for row in rows),
                               'tasks':len(rows),'actions':sum(len(row['arms'][arm]['attempts']) for row in rows),
                               'review_probes':sum(row['arms'][arm]['review_probes'] for row in rows)}
                          for arm in ('learned','no_memory_recovery','strong_ast')},
                'provider_calls':0,'production_activation':False,
                'limitation':'Known-source regression. Reuses verified tool recovery; no gain over capable AST, model training, or general self-improvement claim.'}


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
