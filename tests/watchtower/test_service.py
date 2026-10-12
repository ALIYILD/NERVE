import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_guardian.__main__ import build_guardian,run_watchtower,telemetry_report,read_config

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_service_cannot_implicitly_arm(self):
        with self.assertRaises(PermissionError):build_guardian({'armed':True})
    def test_root_cannot_arm_unsupported_host_or_missing_systemctl(self):
        for system,available in [('Darwin',True),('Linux',False)]:
            with self.subTest(system=system), patch('os.geteuid',return_value=0), patch('platform.system',return_value=system), patch('os.access',return_value=available), patch('nerve_guardian.__main__.Store',side_effect=AssertionError('state created')):
                with self.assertRaisesRegex(PermissionError,'supported Linux'):
                    build_guardian({'armed':True},allow_live=True)
    def test_arming_requires_owner_recovery_and_both_alert_channels(self):
        config={'armed':True,'state_directory':str(self.root/'state'),'anchor_directory':str(self.root/'anchor'),
                'enforcement_directory':str(self.root/'enforcement'),'tenants':{'a':{'units':[{'name':'nerve.service'}]}}}
        with patch('os.geteuid',return_value=0), patch('platform.system',return_value='Linux'), patch('os.access',return_value=True), patch('nerve_guardian.__main__.Store',side_effect=AssertionError('state created')):
            with self.assertRaisesRegex(PermissionError,'owner MFA'):
                build_guardian(config,allow_live=True)
            config['owners']={'human':'a'}
            config['identity']={'issuer':'https://id.example','audience':'guardian','public_key_files':{'key':'/private/key.pem'}}
            with self.assertRaisesRegex(PermissionError,'both notification'):
                build_guardian(config,allow_live=True)
            config['notifications']={'email':{'endpoint':'https://mail.example','secret_path':'/private/mail','sender':'guardian@example.test','recipient':'owner@example.test'},
                                     'telegram':{'endpoint':'https://api.telegram.org','secret_path':'/private/bot','recipient':'owner'}}
            config['tenants']['b']={'units':[{'name':'nerve-other.service'}]}
            with self.assertRaisesRegex(PermissionError,'every managed tenant'):
                build_guardian(config,allow_live=True)
    def test_passive_collector_real_sqlite_cli_contract(self):
        db=self.root/'app.db'
        with sqlite3.connect(db) as con:
            con.execute('CREATE TABLE gl_events(tenant TEXT,details TEXT)')
            con.execute('INSERT INTO gl_events VALUES(?,?)',('demo','secret-never-export'))
        before=db.read_bytes();report=self.root/'report.json'
        run_watchtower({'sources':[{'path':str(db),'tenant':'demo','source':'app'}],'report_path':str(report),'interval_seconds':.25},once=True)
        self.assertEqual(before,db.read_bytes());self.assertNotIn('secret-never-export',report.read_text())
        self.assertEqual(telemetry_report(report,'demo',['app'])[0]['counters'],{'gl_events':1})
        self.assertEqual(telemetry_report(report,'other',['app']),[])
    def test_poisoned_report_has_no_arbitrary_payload(self):
        path=self.root/'poison.json'
        path.write_text(json.dumps({'observations':[{'tenant':'demo','source':'secret','counters':{'secret':4},'status':'OK','observed_at':100}]}))
        self.assertEqual(telemetry_report(path,'demo',['app']),[])
    def test_config_rejects_world_writable(self):
        path=self.root/'config.json';path.write_text('{}');path.chmod(0o666)
        with self.assertRaises(PermissionError):read_config(path)
