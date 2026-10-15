import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from collections import Counter
from nerve_awim.memory_gateway import scientific_v3_holdout as h
from nerve_awim.memory_gateway import scientific_task_bank as bank


class HoldoutTests(unittest.TestCase):
    def rows(self):
        return [bank._item(bytes.fromhex('ab'*32),'holdout',s,i)
                for pos,s in enumerate(bank.STRATA) for i in range(43 if pos<6 else 42)]

    def test_partition_disjoint_stratified_stable(self):
        rows=self.rows();g=h.partition_rows(rows)
        self.assertEqual(g,h.partition_rows(list(reversed(rows))))
        self.assertEqual(len({r['task_id'] for group in g.values() for r in group}),300)
        for name in ('slice1','slice2'):
            self.assertEqual(Counter(r['stratum'] for r in g[name]),{s:20 for s in h.STRATA})
        self.assertEqual(Counter(r['stratum'] for r in g['reserve']),dict({s:3 for s in h.STRATA},**{'multi-source-agreement':43,'stale-vs-current':42}))

    def test_partition_not_answer_dependent(self):
        original=self.rows();changed=json.loads(json.dumps(original))
        for r in changed:r['expected']={'ignored':'not read by partitioner'}
        a=h.partition_rows(original);b=h.partition_rows(changed)
        self.assertEqual({k:[r['task_id'] for r in v] for k,v in a.items()}, {k:[r['task_id'] for r in v] for k,v in b.items()})

    def test_invalid_bank_rejected(self):
        with self.assertRaises(ValueError):h.partition_rows(self.rows()[:-1])

    def test_wilson_extremes(self):
        self.assertAlmostEqual(h.wilson(20,20)[0],0.8388748419471806)
        self.assertAlmostEqual(h.wilson(0,20)[1],0.16112515805281938)
        with self.assertRaises(ValueError):h.wilson(2,1)

    def make_rows(self):
        out=[]
        for t in h.partition_rows(self.rows())['slice1']:
            for arm in h.ARMS:
                p=h.dev.prepared_for(t,arm)
                if arm=='candidate' and p['route']=='model':
                    alias=next(a for a,r in p['aliases'].items() if r['source_id']==t['expected']['source_id'])
                    raw=json.dumps({'value':float(t['expected']['value']),'unit':'mg','source_id':alias})
                else:raw=h.dev._random_raw(t,p) if arm=='random' else 'ABSTAIN'
                out.append(dict(task_id=t['task_id'],stratum=t['stratum'],arm=arm,model_calls=int(h.dev._route(t,arm)=='model'),score=h.dev.score(raw,t,p)))
        return out

    def test_acceptance_and_aggregate_privacy(self):
        rows=self.make_rows();report=h.aggregate(rows,complete=True)
        self.assertEqual(report['verdict'],'promote_proposal')
        self.assertEqual(report['strict_totals']['candidate'],100)
        exported=json.dumps(report)
        for row in rows:self.assertNotIn(row['task_id'],exported)
        for field in ('raw_output','expected','query','evidence','source_id'):self.assertNotIn('"'+field+'"',exported)
        self.assertEqual(h.aggregate(rows,complete=False)['verdict'],'retain_incumbent')
        self.assertEqual(h.aggregate(rows[:-1],complete=True)['verdict'],'retain_incumbent')
        for row in rows:
            if row['arm']=='candidate' and row['stratum']=='conflict':row['score']['strict_correct']=False;break
        self.assertEqual(h.aggregate(rows,complete=True)['verdict'],'retain_incumbent')

    def test_tie_retains(self):
        rows=self.make_rows()
        for r in rows:
            if r['arm']=='candidate':r['score']['strict_correct']=r['stratum'] in ('conflict','unit-mismatch')
        self.assertEqual(h.aggregate(rows,complete=True)['verdict'],'retain_incumbent')

    def test_guard_denies_unused_paths_in_child(self):
        code="""from pathlib import Path
from nerve_awim.memory_gateway.scientific_v3_holdout import guard
guard(Path('/tmp/test-sealed'),Path('/tmp/test-bank'))
for p in ('/tmp/test-sealed/slice2.json','/tmp/test-sealed/reserve.json','/tmp/test-bank/holdout.json','/tmp/test-bank.seed'):
 try: open(p)
 except PermissionError: pass
 else: raise AssertionError('not blocked')
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_complete_mocked_run_private_and_one_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=root/'bank';study=root/'study'
            built=bank.build(b,host_seed='ab'*32)
            with patch.object(h,'MANIFEST_PIN',built['manifest_sha256']):
                p=h.register(study,b)
            for path in (b/'holdout.json',study/'slice1.json',study/'slice2.json',study/'reserve.json'):
                self.assertEqual(path.stat().st_mode & 0o777,0)
            identity={'model':h.dev.pilot.MODEL,'digest':p['expected_digest']}
            calls=[]
            def transport(prepared,*,authorize,timeout_seconds):
                authorize();self.assertEqual(timeout_seconds,30);calls.append(prepared['arm'])
                # Mock tests select exact matching current facts, not real held-out inputs.
                if prepared['arm']=='baseline':raw='ABSTAIN'
                else:
                    alias,source=next((a,r) for a,r in prepared['aliases'].items() if r['entity'].startswith('N') and r['measurement']=='mass' and r['unit']=='mg')
                    raw=json.dumps({'value':float(source['value']),'unit':source['unit'],'source_id':alias})
                return dict(model=identity['model'],model_sampling_seed=h.SEED,input_sha256=prepared['input_sha256'],raw_output=raw,usage={'prompt_tokens':80,'completion_tokens':20,'total_tokens':100},finish_reason='stop')
            with patch.object(h.dev,'metadata',return_value=identity),patch.object(h.dev,'runtime_version',return_value='test-runtime'),patch.object(h.dev,'preload',return_value={'wall_seconds':0.}),patch.object(h.dev.transport,'run',side_effect=transport):
                result=h.run(study)
            self.assertEqual(Counter(calls),{'baseline':100,'candidate':60})
            self.assertEqual(result['verdict'],'promote_proposal')
            with patch.object(h.dev.transport,'run',side_effect=AssertionError('no inference')):
                self.assertEqual(h.verify(study),result)
                with self.assertRaises(FileExistsError):h.run(study)
            private=json.loads((study/'private-report.json').read_text())
            self.assertEqual(len(private['rows']),400)
            self.assertNotIn('private_tasks',result)
            for path in (study/'private-report.json',study/'claims.sqlite',study/'aggregate-report.json'):
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            for path in (b/'holdout.json',study/'slice1.json',study/'slice2.json',study/'reserve.json'):
                self.assertEqual(path.stat().st_mode & 0o777,0)


if __name__=='__main__':unittest.main()
