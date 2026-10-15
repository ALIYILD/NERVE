"""Synthetic contract fixtures only. Intentionally not executed during slice 2."""
from copy import deepcopy
from hashlib import sha256
import hmac
import tempfile
import unittest

from nerve_awim.goal_orchestrator import GoalOrchestrator
from nerve_awim.retained_skill_contract import select_retained_skill, signing_payload


class RetainedSkillContractTests(unittest.TestCase):
    def setUp(self):
        self.config = b'fixture configuration v3'
        self.artifacts = {name: ('synthetic ' + name).encode() for name in
                          ('dev_study', 'holdout_study', 'task_bank_manifest')}
        self.incumbent = dict(skill_id='fixture/skill', version='v2', config_hash='2' * 64)
        self.record = dict(skill_id='fixture/skill', version='v3',
                           config_hash=sha256(self.config).hexdigest(),
                           evidence_bundle={name: dict(uri=name, sha256=sha256(data).hexdigest())
                                            for name, data in self.artifacts.items()},
                           supersedes=self.incumbent.copy())
        self.record['evidence_bundle']['model_digest'] = '3' * 64
        self.manifest = sha256(self.artifacts['task_bank_manifest']).hexdigest()
        self.sign(self.record)

    def sign(self, record):
        # Deliberately public fixture key, NEVER a real promotion credential.
        signature = hmac.new(b'fixture-only', signing_payload(record), 'sha256').hexdigest()
        record['signed_by'] = dict(key_id='fixture-authority', signature=signature)

    def select(self, record, gate=True):
        def verify(key, payload, signature):
            return key == 'fixture-authority' and hmac.compare_digest(
                hmac.new(b'fixture-only', payload, 'sha256').hexdigest(), signature)
        return select_retained_skill(record, incumbent=self.incumbent,
            config_bytes=self.config, artifact_bytes=self.artifacts,
            manifest_hash=self.manifest, model_digest='3' * 64,
            verify_gate=lambda record, artifacts: gate, verify_signature=verify)

    def orchestrate(self, record, expected):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = GoalOrchestrator(directory,
                handlers={'select': lambda context: self.select(record)},
                validators={'select': lambda receipt: receipt['retained_skill_selected'] is True})
            orchestrator.create(goal_id='fixture-retention', target='verified signed retained skill',
                                tasks=[{'id': 'select', 'handler': 'select'}])
            state = orchestrator.run()
            self.assertEqual(state['status'], 'complete' if expected else 'blocked')
            receipt = state['tasks'][0]['receipt']
            self.assertEqual(receipt['selected']['version'], 'v3' if expected else 'v2')
            self.assertFalse(receipt['production_authorized'])

    def test_orchestrator_selects_verified_signed_fixture(self):
        self.orchestrate(self.record, True)

    def test_each_tampered_artifact_retains_incumbent(self):
        for uri in tuple(self.artifacts):
            with self.subTest(uri=uri):
                original = self.artifacts[uri]
                self.artifacts[uri] = b'tampered'
                self.orchestrate(self.record, False)
                self.artifacts[uri] = original

    def test_unsigned_invalid_and_unauthorized_promotions_block(self):
        for signer in (None, {}, {'key_id': 'fixture-authority', 'signature': 'bad'},
                       dict(self.record['signed_by'], key_id='untrusted')):
            record = deepcopy(self.record)
            record['signed_by'] = signer
            self.orchestrate(record, False)

    def test_signed_bindings_must_match_host(self):
        for field in ('config', 'model', 'manifest', 'supersedes'):
            record = deepcopy(self.record)
            if field == 'config':
                record['config_hash'] = '0' * 64
            elif field == 'model':
                record['evidence_bundle']['model_digest'] = '0' * 64
            elif field == 'manifest':
                record['evidence_bundle']['task_bank_manifest']['sha256'] = '0' * 64
            else:
                record['supersedes']['version'] = 'wrong'
            self.sign(record)
            self.orchestrate(record, False)

    def test_changed_version_invalidates_signature(self):
        record = deepcopy(self.record)
        record['version'] = 'v4'
        self.orchestrate(record, False)

    def test_dev_review_only_is_not_promotion(self):
        receipt = self.select(self.record, gate=False)
        self.assertFalse(receipt['retained_skill_selected'])
        self.assertEqual(receipt['selected'], self.incumbent)
