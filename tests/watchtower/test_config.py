import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_guardian.config import validate_config
from nerve_guardian.__main__ import build_guardian, read_config, run_watchtower


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(state_directory=str(self.root/'state'), anchor_directory=str(self.root/'anchor'),
                           enforcement_directory=str(self.root/'enforcement'),
                           tenants={'a': {'units': [{'name': 'nerve-pilot.service'}]}})

    def test_examples_validate_without_reading_files_or_starting_services(self):
        root = Path(__file__).resolve().parents[2]
        examples = [json.loads((root/'deploy/watchtower'/name).read_text()) for name in ('guardian.example.json', 'watchtower.example.json')]
        with patch('builtins.open', side_effect=AssertionError('filesystem access')), patch('os.open', side_effect=AssertionError('filesystem access')):
            for example in examples:
                self.assertTrue(validate_config(example)['valid_schema'])
        self.assertEqual(validate_config(self.config)['production_readiness'], 'unverified')

    def test_invalid_schema_cannot_create_guardian_state(self):
        for field, value in [('interval_seconds', float('nan')), ('interval_seconds', True), ('portal_port', 0),
                             ('armed_typo', False), ('owners', {'human': 'missing'}),
                             ('anchor_directory', str(self.root/'state'/'anchor'))]:
            config = copy.deepcopy(self.config); config[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): build_guardian(config)
            self.assertFalse((self.root/'state').exists())
            self.assertFalse((self.root/'enforcement').exists())

    def test_unsafe_inventory_and_pins_rejected(self):
        for unit in ({'name': 'guardian.service'}, {'name': 'nerve.service', 'clinical': True},
                     {'name': 'nerve.service', 'shared': 'false'}, {'name': '../nerve.service'}):
            config = copy.deepcopy(self.config); config['tenants']['a']['units'] = [unit]
            with self.assertRaises(ValueError): validate_config(config)
        config = copy.deepcopy(self.config); config['tenants']['b'] = copy.deepcopy(config['tenants']['a'])
        with self.assertRaises(ValueError): validate_config(config)
        config = copy.deepcopy(self.config); config['tenants']['a']['protected_files'] = {'/opt/pinned': 'bad'}
        with self.assertRaises(ValueError): validate_config(config)

    def test_identity_and_notification_schema(self):
        config = copy.deepcopy(self.config)
        config['owners'] = {'owner': 'a'}
        config['identity'] = dict(issuer='https://id.example', audience='guardian', public_key_files={'key': '/missing/key.pem'}, mfa_acr=['mfa'])
        config['notifications'] = {'email': dict(endpoint='https://mail.example/send', secret_path='/missing/secret', recipient='owner@example.test', sender='guardian@example.test')}
        self.assertTrue(validate_config(config)['valid_schema'])
        for key, value in [('endpoint', 'http://mail.example'), ('sender', None), ('secret_path', 'relative'), ('unexpected', 'x')]:
            changed = copy.deepcopy(config); changed['notifications']['email'][key] = value
            with self.assertRaises(ValueError): validate_config(changed)
        config['notifications'] = {'telegram': dict(endpoint='https://evil.example', secret_path='/missing/secret', recipient='owner')}
        with self.assertRaises(ValueError): validate_config(config)

    def test_ambiguous_json_and_unsafe_configuration_files_rejected(self):
        path = self.root/'config.json'
        for text in ('{"armed":false,"armed":true}', '{"x":{"a":1,"a":2}}', '{"interval_seconds":NaN}'):
            path.write_text(text)
            with self.assertRaises(ValueError): read_config(path)
        path.write_text('{}'); link = self.root/'link'; link.symlink_to(path)
        with self.assertRaises(OSError): read_config(link)
        with self.assertRaises(ValueError): validate_config({})
        with self.assertRaises(ValueError): validate_config({'sources': [], 'tenants': {}})

    def test_bad_watchtower_config_starts_no_collector(self):
        source = dict(path=str(self.root/'source.db'), tenant='a', source='shared')
        config = dict(sources=[source], report_path=str(self.root/'report.json'))
        for changes in ({'interval_seconds': 0}, {'sources': [source, source]}, {'report_path': source['path']}, {'interval_seconds': float('inf')}):
            changed = copy.deepcopy(config); changed.update(changes)
            with patch('nerve_guardian.telemetry.BoundedCollector.start', side_effect=AssertionError('worker started')):
                with self.assertRaises(ValueError): run_watchtower(changed, once=True)
            self.assertFalse((self.root/'report.json').exists())

    def test_distinct_sources_preserve_both_tenants(self):
        database = self.root/'source.db'
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE gl_events(tenant TEXT)')
            connection.executemany('INSERT INTO gl_events VALUES(?)', [('a',), ('b',), ('b',)])
        report = self.root/'report.json'
        run_watchtower(dict(sources=[dict(path=str(database), tenant=t, source=t) for t in ('a', 'b')],
                            report_path=str(report), interval_seconds=.25), once=True)
        observations = json.loads(report.read_text())['observations']
        self.assertEqual({obs['tenant']: obs['counters']['gl_events'] for obs in observations}, {'a': 1, 'b': 2})

    def test_report_staging_does_not_overwrite_source_database(self):
        database = self.root/'source.pending'
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE gl_events(tenant TEXT)')
            connection.execute("INSERT INTO gl_events VALUES('a')")
        before = database.read_bytes()
        report = self.root/'source.json'
        run_watchtower(dict(sources=[dict(path=str(database), tenant='a', source='source')],
                            report_path=str(report), interval_seconds=.25), once=True)
        self.assertEqual(database.read_bytes(), before)
        self.assertEqual(json.loads(report.read_text())['observations'][0]['counters'], {'gl_events': 1})
        self.assertEqual(list(self.root.glob('.guardian-report-*')), [])
