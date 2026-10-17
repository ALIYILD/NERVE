"""Fail-closed checks for the distinct historical A routing replay study."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('a_replay',ROOT/'scripts/replay_overnight_family_a.py')
replay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

class ReplayAuthorizationTests(unittest.TestCase):
    def test_rejects_unbound_or_wrong_scope_authorization_before_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'registration.json').write_text('{}')
            for auth in ({'authorized':False}, {'authorized':True,'registration_sha256':'wrong','scope':'CPU historical replay only'},
                         {'authorized':True,'registration_sha256':replay.records.filehash(directory/'registration.json'),'scope':'inference'}):
                path=directory/'authorization.json';path.write_text(json.dumps(auth))
                with patch.object(replay,'bindings') as bindings:
                    with self.assertRaisesRegex(ValueError,'W0_replay_authorization_required'):
                        replay.evaluate(directory,path)
                    bindings.assert_not_called()
            self.assertFalse((directory/'result.json').exists())

    def test_rejects_changed_receipt_manifest_before_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            reg={'planned':'planned','source':'source','files':{'receipt':'old'},'sources':{},'rule':{}}
            (directory/'registration.json').write_text(json.dumps(reg))
            auth={'authorized':True,'registration_sha256':replay.records.filehash(directory/'registration.json'),'scope':'CPU historical replay only'}
            path=directory/'authorization.json';path.write_text(json.dumps(auth))
            with patch.object(replay,'bindings',return_value=({'receipt':'changed'},{},[],{'rule':{}})), patch.object(replay.old,'score') as score:
                with self.assertRaisesRegex(ValueError,'replay_bindings_changed'):
                    replay.evaluate(directory,path)
                score.assert_not_called()
            self.assertFalse((directory/'result.json').exists())

    def test_seed_mismatch_rejected_before_receipt_access(self):
        with patch.object(replay.records,'read',side_effect=[{'model_digest':replay.records.DIGEST},[],
                   {'kind':'dev','candidate_module':replay.MODULE,'identity':{'model_digest':replay.records.DIGEST},'seed':20261015}]):
            with self.assertRaisesRegex(ValueError,'replay_seed_changed'):
                replay.bindings(Path('planned'),Path('source'))

if __name__=='__main__':unittest.main()
