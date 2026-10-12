"""Maintenance admission/model contracts; fake board, no inference or network."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPT=Path(__file__).resolve().parents[1]/'integrations/agentos/agent-os-maintenance-mission.py'
SPEC=importlib.util.spec_from_file_location('maintenance_producer',SCRIPT)
producer=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)


class FakeBoard:
    def __init__(self,path):
        self.path=path
        self.cards=[]
        with self.connect() as db:
            db.executescript('CREATE TABLE tasks(id TEXT,assignee TEXT,status TEXT); '
                             'CREATE TABLE task_runs(id INTEGER,task_id TEXT,status TEXT,outcome TEXT,error TEXT);')
    def connect(self):
        return sqlite3.connect(self.path)
    def create_task(self,conn,**card):
        self.cards.append(card)
        return 'card-'+str(len(self.cards))


class MaintenanceProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.board=FakeBoard(self.home/'board.sqlite3')
        self.catalog=self.home/'.agentic-os/nerve/free-models.json'
        self.catalog.parent.mkdir(parents=True)
        self.catalog.write_text('["valid/model:free"]')
        self.config=patch.object(producer,'configured_models',return_value=['removed/model:free','valid/model:free'])
        self.config.start()
        self.addCleanup(self.config.stop)
        self.evidence=self.home/'evidence.json'
        self.evidence.write_text(json.dumps(dict(schema_version=1,collected_at_epoch=int(time.time()),status='ok')))
        self.dest=self.home/'AgentOS-Vault/Journal/maintenance-missions/test'
    def run_mission(self,*extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return producer.main(['--run-key','test',*extra],home=self.home,kanban=self.board)
    def test_blocked_work_has_durable_safe_metadata_without_empty_mission_directory(self):
        with self.board.connect() as db:
            db.execute('INSERT INTO tasks VALUES(?,?,?)',('t1','workflow-integrity-auditor','blocked'))
            db.execute('INSERT INTO task_runs VALUES(?,?,?,?,?)',(1,'t1','failed','spawn_failed','SECRET ERROR'))
            db.execute('INSERT INTO task_runs VALUES(?,?,?,?,?)',(2,'t1','timed_out','timed_out','SECRET ERROR'))
        receipt=self.run_mission()
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.board.cards,[])
        saved=(self.dest.parent/'admission-status.json').read_text()
        self.assertNotIn('SECRET',saved)
        self.assertEqual(json.loads(saved),receipt)
        self.assertEqual(receipt['tasks'],[dict(id='t1',profile='workflow-integrity-auditor',status='blocked',latest_outcome='timed_out')])
    def test_available_configured_fallback_and_snapshot_only_scheduler(self):
        self.dest.parent.mkdir(parents=True)
        (self.dest.parent/'admission-status.json').write_text('{"status":"blocked_existing_work"}')
        self.run_mission('--evidence',str(self.evidence))
        self.assertEqual(len(self.board.cards),4)
        for card in self.board.cards:
            self.assertEqual(card['model_override'],'valid/model:free')
            self.assertEqual(card['provider_override'],'openrouter')
            self.assertEqual(card['max_runtime_seconds'],240)
        scheduling=self.board.cards[1]['body']
        self.assertIn('maintenance-evidence.json',scheduling)
        self.assertIn('Do not enumerate boards, unblock tasks, or run old prompts.',scheduling)
        self.assertNotIn('cron/jobs.json',scheduling)
        self.assertEqual(json.loads((self.dest/'maintenance-evidence.json').read_text()),json.loads(self.evidence.read_text()))
        self.assertEqual(self.board.cards[2]['parents'],['card-1','card-2'])
        self.assertEqual(self.board.cards[3]['parents'],['card-3'])
        self.assertEqual(json.loads((self.dest.parent/'admission-status.json').read_text())['status'],'created')
    def test_worker_and_qa_require_underlying_evidence_for_paid_route_claims(self):
        self.run_mission('--evidence',str(self.evidence))
        routing,scheduling,qa,_=self.board.cards
        self.assertIn('configured :free suffix shows configuration only',routing['body'])
        self.assertIn('Do not claim no_paid_model_routes',scheduling['body'])
        self.assertIn('record that claim as unknown or not assessed',scheduling['body'])
        self.assertIn('A worker assertion is not independent evidence',qa['body'])
        self.assertIn('never infer no_paid_model_routes from a snapshot without model/provider fields',qa['body'])
        self.assertIn('Use false when a required check fails, is unsupported, or is unknown.',qa['body'])
    def test_routing_and_qa_distinguish_key_presence_catalog_and_inference(self):
        self.run_mission('--evidence',str(self.evidence))
        for card in (self.board.cards[0],self.board.cards[2]):
            self.assertIn('/api/openrouter/status ok means only local API-key presence (Boolean(key))',card['body'])
            self.assertIn('it makes no provider request',card['body'])
            self.assertIn('catalog listing still does not prove successful inference',card['body'])
            self.assertIn('Actual execution remains unknown without an existing inference receipt',card['body'])
            self.assertIn('Do not run inference to test this.',card['body'])
    def test_coordinator_keeps_qa_and_host_verdicts_separate_and_honors_veto(self):
        self.run_mission('--evidence',str(self.evidence))
        coordinator=self.board.cards[3]
        direct_prompt=coordinator['body'].split('\n\n',1)[0]
        self.assertEqual(coordinator['parents'],['card-3'])
        self.assertIn('Read host-review.json in the output directory if present',direct_prompt)
        self.assertIn('Report the model QA verdict and host-review verdict separately',direct_prompt)
        self.assertIn('A host veto overrides QA accepted=true',direct_prompt)
        self.assertIn('malformed or incomplete host review blocks verification',direct_prompt)
        self.assertIn('If absent, report host review as not reviewed, not approved',direct_prompt)
        self.assertIn('Preserve the original QA and host-review files unchanged',direct_prompt)
        manifest=json.loads((self.dest/'mission.json').read_text())
        self.assertIn(producer.HOST_REVIEW_CONTRACT,manifest['goal'])
    def test_every_nonterminal_state_blocks_admission_including_triage(self):
        for status in ('triage','scheduled','claimed','needs_human'):
            with self.subTest(status=status):
                with self.board.connect() as db:
                    db.execute('DELETE FROM tasks')
                    db.execute('INSERT INTO tasks VALUES(?,?,?)',('t1','qa',status))
                result=self.run_mission()
                self.assertEqual(result['status'],'blocked_existing_work')
                self.assertFalse(self.dest.exists())
                self.assertEqual(self.board.cards,[])
    def test_explicit_model_must_be_configured_available_and_free(self):
        for candidate in ('unknown/model:free','removed/model:free','paid/model'):
            with self.subTest(candidate=candidate),self.assertRaisesRegex(ValueError,'Configure an available'):
                self.run_mission('--model',candidate,'--evidence',str(self.evidence))
        self.assertEqual(self.board.cards,[])
        self.assertFalse(self.dest.exists())
        self.run_mission('--model','valid/model:free','--evidence',str(self.evidence))
        self.assertEqual(len(self.board.cards),4)
    def test_stale_catalog_fails_closed_before_directory_or_cards(self):
        os.utime(self.catalog,(1,1))
        with patch.object(producer.subprocess,'check_output',side_effect=subprocess.TimeoutExpired('curl',25)), \
             self.assertRaisesRegex(ValueError,'Refresh the NERVE'):
            self.run_mission('--evidence',str(self.evidence))
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.board.cards,[])
        self.assertEqual(json.loads((self.dest.parent/'admission-status.json').read_text())['status'],'blocked_configuration')
    def test_stale_catalog_refresh_accepts_only_zero_price_free_models(self):
        os.utime(self.catalog,(1,1))
        payload={'data':[
            {'id':'valid/model:free','pricing':{'prompt':'0','completion':'0'}},
            {'id':'paid/model:free','pricing':{'prompt':'0.001','completion':'0'}},
            {'id':'paid/model','pricing':{'prompt':'0','completion':'0'}},
            {'id':'invalid/model:free','pricing':{'prompt':False,'completion':'0'}},
            {'id':'missing/model:free'},
            {'id':'nan/model:free','pricing':{'prompt':'NaN','completion':'0'}}]}
        with patch.object(producer.subprocess,'check_output',return_value=json.dumps(payload).encode()) as fetch:
            self.assertEqual(producer.resolve_model(self.home),'valid/model:free')
        command=fetch.call_args.args[0]
        self.assertEqual(command[:2],['/usr/bin/curl','--disable'])
        self.assertEqual(command[-1],'https://openrouter.ai/api/v1/models')
        self.assertEqual(fetch.call_args.kwargs['timeout'],25)
        self.assertEqual(json.loads(self.catalog.read_text()),['valid/model:free'])
        self.assertEqual(list(self.catalog.parent.glob('*.tmp')),[])
    def test_bad_refresh_preserves_stale_catalog_without_using_it(self):
        old=self.catalog.read_bytes()
        os.utime(self.catalog,(1,1))
        for payload in (b'not json',b'{"data":[]}',b'{"data":[{"id":"paid:free","pricing":{"prompt":"1","completion":"1"}}]}'):
            with patch.object(producer.subprocess,'check_output',return_value=payload),self.assertRaises(ValueError):
                producer.resolve_model(self.home)
            self.assertEqual(self.catalog.read_bytes(),old)
        self.assertEqual(self.board.cards,[])
    def test_fresh_catalog_skips_metadata_network_request(self):
        with patch.object(producer.subprocess,'check_output') as fetch:
            self.assertEqual(producer.resolve_model(self.home),'valid/model:free')
        fetch.assert_not_called()
    def test_no_flags_collects_snapshot_before_creating_cards(self):
        def collect(command,**kwargs):
            self.assertEqual(command[1],str(self.home/'nerve-review/scripts/agentos_maintenance.py'))
            self.assertEqual(self.board.cards,[])
            path=Path(command[-1])
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(schema_version=1,collected_at_epoch=int(time.time()),status='ok')))
        with patch.object(producer.subprocess,'run',side_effect=collect) as mocked:
            self.run_mission()
        mocked.assert_called_once()
        self.assertEqual(len(self.board.cards),4)
    def test_failed_collector_creates_no_cards(self):
        with patch.object(producer.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['collector'])):
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_mission()
        self.assertEqual(self.board.cards,[])
    def test_existing_manifest_is_idempotent(self):
        self.run_mission('--evidence',str(self.evidence))
        self.run_mission('--model','invalid')
        self.assertEqual(len(self.board.cards),4)
    def test_invalid_evidence_creates_no_cards_or_directory(self):
        self.evidence.write_text('[]')
        with self.assertRaisesRegex(ValueError,'JSON object'):
            self.run_mission('--evidence',str(self.evidence))
        self.assertEqual(self.board.cards,[])
        self.assertFalse(self.dest.exists())
    def test_stale_or_wrong_schema_evidence_fails_before_cards(self):
        for evidence in ({'schema_version':1,'collected_at_epoch':1},
                         {'schema_version':True,'collected_at_epoch':int(time.time())},
                         {'schema_version':1,'collected_at_epoch':int(time.time())+120}):
            self.evidence.write_text(json.dumps(evidence))
            with self.subTest(evidence=evidence),self.assertRaisesRegex(ValueError,'Collect fresh'):
                self.run_mission('--evidence',str(self.evidence))
        self.assertEqual(self.board.cards,[])
        self.assertFalse(self.dest.exists())
    def test_provisioned_runtime_handoff_preserves_arguments_without_installing(self):
        python=self.home/'provisioned-python'
        python.touch()
        args=['--run-key','test','--model','valid/model:free']
        with patch.dict(producer.os.environ,{},clear=True), \
             patch.object(producer.subprocess,'check_output',side_effect=['["/launcher/python"]',str(python)+'\n']) as resolve, \
             patch.object(producer.os,'execve',side_effect=SystemExit) as execute:
            with self.assertRaises(SystemExit):
                producer.ensure_runtime(self.home,self.home/'.hermes/hermes-agent',args)
        self.assertEqual(resolve.call_count,2)
        self.assertEqual(resolve.call_args_list[0].args[0],[str(self.home/'.local/bin/hermes'),'--print-runtime-command'])
        executable,command,env=execute.call_args.args
        self.assertEqual(executable,str(python))
        self.assertEqual(command,[str(python),str(SCRIPT),*args])
        self.assertEqual(env['NERVE_MAINTENANCE_RUNTIME'],'1')
        self.assertEqual(env['HERMES_DISABLE_LAZY_INSTALLS'],'1')
    def test_runtime_marker_prevents_reexec_loop(self):
        with patch.dict(producer.os.environ,{'NERVE_MAINTENANCE_RUNTIME':'1'}), \
             patch.object(producer.subprocess,'check_output') as resolve, \
             patch.object(producer.os,'execve') as execute:
            producer.ensure_runtime(self.home,self.home/'.hermes/hermes-agent',[])
        resolve.assert_not_called()
        execute.assert_not_called()
    def test_installed_split_connector_selects_explicit_maintenance_board(self):
        mutations=Mock()
        connector=Mock()
        self.assertIs(producer.connect_board(mutations,connector),connector.connect.return_value)
        connector.connect.assert_called_once_with(board='agentos-maintenance')
        mutations.connect.assert_not_called()
    def test_configured_models_uses_hermes_yaml_and_returns_only_model_ids(self):
        self.config.stop()
        config=self.home/'.agentic-os/free-model-config.json'
        config.write_text(json.dumps({'openrouter':{'enabled':True,'model':'primary/model:free'},'private':'SECRET'}))
        profile=self.home/'.hermes/profiles/coordinator/config.yaml'
        profile.parent.mkdir(parents=True)
        profile.write_text('local config')
        yaml=SimpleNamespace(safe_load=Mock(return_value={
            'model':{'default':'hermes/model:free','provider':'openrouter'},
            'fallback_providers':[{'provider':'openrouter','model':'fallback/model:free'},
                                  {'provider':'paid','model':'excluded/model'},'string/model:free'],
            'credentials':'SECRET'}),YAMLError=ValueError)
        with patch.dict(producer.sys.modules,{'hermes_yaml':yaml,'yaml':None}):
            models=producer.configured_models(self.home)
        self.assertEqual(models,['primary/model:free','hermes/model:free','fallback/model:free','string/model:free'])
        self.assertNotIn('SECRET',json.dumps(models))
        yaml.safe_load.assert_called_once_with('local config')

if __name__=='__main__':
    unittest.main()
