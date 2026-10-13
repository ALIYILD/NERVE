import copy
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import prequential_gain_demo as demo


class PrequentialGainDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[demo.execute(arm,plant) for plant in demo.PLANTS for arm in demo.ARMS]

    def test_exact_fixed_roster_and_physical_learning_audits(self):
        self.assertEqual(len(self.rows),12)
        for row in self.rows:
            self.assertTrue(demo.validate(row,row['arm'],row['plant']))
            self.assertEqual(row['learning_audit']['repeated_applications'],0)
            self.assertEqual(len(row['trace']),80)
        for arm,plant in (('legacy','drift'),('selector','unknown')):
            with self.assertRaises(ValueError): demo.execute(arm,plant)

    def test_original_frozen_single_use_trajectories_preserved(self):
        path=Path(__file__).resolve().parents[1]/'docs/galahad/evidence/standard-learning-development-v1.json.gz'
        originals=json.loads(gzip.decompress(path.read_bytes()))['rows']
        for row in self.rows:
            if row['plant'] not in ('nominal','drift') or row['arm']=='selector': continue
            old=next(r['episode'] for r in originals if r['arm']==row['arm'] and r['episode']['scenario']==('stationary' if row['plant']=='nominal' else 'drift'))
            for key,value in row['metrics'].items(): self.assertEqual(value,old['metrics'][key])
            for new,prior in zip(row['trace'],old['trace']):
                for key in ('action','true_position','true_velocity','estimated_gain','predicted_velocity','goal_error','prediction_error'):
                    self.assertEqual(new[key],prior[key])

    def test_tampered_shadow_forecast_source_and_recovery_rejected(self):
        original=next(r for r in self.rows if r['arm']=='selector' and r['plant']=='drift')
        for mode in ('shadow','forecast','source','incident','commandbool','resume'):
            row=copy.deepcopy(original)
            if mode=='shadow': row['trace'][20]['estimated_gain']=.999
            elif mode=='forecast':
                item=next(t for t in row['trace'] if t['selector_after']['pending'])
                item['selector_after']['pending'][0]['learned_forecast']=999.
            elif mode=='source': row['source_sha256']['secret']='unexpected'
            elif mode=='incident': row['recovery_events'][0]['incident']=999
            elif mode=='commandbool': row['trace'][0]['command']['action']=True
            else: row['trace'][45]['command']['phase']='active'
            with self.subTest(mode=mode),self.assertRaises(ValueError): demo.validate(row,'selector','drift')

    def test_wrong_plant_and_physical_outcomes_rejected(self):
        row=copy.deepcopy(self.rows[0]); row['trace'][10]['true_gain']=.99
        with self.assertRaises(ValueError): demo.validate(row,row['arm'],row['plant'])
        with self.assertRaises(ValueError): demo.compare(self.rows[:-1])
        with self.assertRaises(ValueError): demo.compare(self.rows+[self.rows[0]])

    def test_selector_snapshots_use_only_prior_sensor_action_information(self):
        row=copy.deepcopy(next(r for r in self.rows if r['arm']=='selector' and r['plant']=='drift'))
        demo._audit_selector(row)
        for item in row['trace']:
            for key in ('true_gain','true_velocity','true_position','goal_error','prediction_error','violation'):
                item[key]='withheld'
        demo._audit_selector(row)
        for item in row['trace']:
            if item['selector_before']['scores']:
                item['selector_before']['scores'][0]['observed_velocity']=999
                break
        with self.assertRaises(ValueError): demo._audit_selector(row)

    def test_mixed_window_rejected_despite_better_summed_loss(self):
        windows=[t['selector_before'] for r in self.rows if r['arm']=='selector' for t in r['trace']
                 if len(t['selector_before']['scores'])==4
                 and sum(s['learned_error'] for s in t['selector_before']['scores']) < sum(s['nominal_error'] for s in t['selector_before']['scores'])
                 and not all(s['learned_error']<s['nominal_error'] for s in t['selector_before']['scores'])]
        self.assertGreater(len(windows),0)
        for snapshot in windows:
            self.assertEqual(snapshot['mode'],'nominal')
            self.assertEqual(snapshot['selected_gain'],.27)

    def test_screen_requires_each_baseline_and_all_regimes(self):
        with patch.object(demo,'validate'):
            rows=copy.deepcopy(self.rows)
            for row in rows:
                row['metrics']={'mean_goal_error':.9 if row['arm']=='selector' else 1.,
                    'mean_prediction_error':.1,'violations':0,'supervisor_steps':0}
            self.assertTrue(demo.compare(rows)['passed'])
            row=next(r for r in rows if r['arm']=='selector' and r['plant']=='lower')
            row['metrics']['mean_prediction_error']=.2
            self.assertFalse(demo.compare(rows)['passed'])

    def test_run_roster_budgets_and_narrow_claims(self):
        indexed={(r['arm'],r['plant']):r for r in self.rows}
        with patch.object(demo,'execute',side_effect=lambda a,p:indexed[a,p]):
            result=demo.run_demo()
        self.assertEqual(result['episodes'],12);self.assertEqual(result['plant_steps'],960)
        for key in ('performance_improvement_claimed','candidate_promoted','model_weights_trained','registered_streams_used','heldout_outcomes_analyzed'):
            self.assertIs(result[key],False)
        with patch.object(demo,'sources',return_value={}),patch.object(demo.time,'monotonic',side_effect=[0,361]),patch.object(demo,'execute') as execute:
            with self.assertRaises(TimeoutError): demo.run_demo()
            execute.assert_not_called()
