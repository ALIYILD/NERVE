from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import seal_scientific_holdout_v2 as seal

class SealTests(unittest.TestCase):
    def test_incomplete_robustness_cannot_generate(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);study=p/'robust';study.mkdir();seal.base.write(study/'aggregate.json',{'complete':False,'promotion_authorized':False})
            with self.assertRaisesRegex(ValueError,'completed_exploratory'):seal.seal(p/'bank',study)
            self.assertFalse((p/'bank').exists())
    def test_balanced300_and_real_filesystem_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);study=p/'robust';study.mkdir();seal.base.write(study/'aggregate.json',{'complete':True,'promotion_authorized':False,'identity':{},'version':'scientific-runpod-robustness-36.5-v1','status':'complete_exploratory','holdout_accessed':False})
            with patch.object(seal.base,'identity',return_value={}):receipt=seal.seal(p/'bank',study)
            self.assertTrue(receipt['sealed']);self.assertEqual(sum(receipt['counts'].values()),300);self.assertEqual(sorted(receipt['counts'].values()),[42,43,43,43,43,43,43])
            self.assertEqual(stat.S_IMODE((p/'bank/holdout.json').stat().st_mode),0);self.assertEqual(stat.S_IMODE((p/'bank/private-seed.json').stat().st_mode),0)
            self.assertEqual(receipt['manifest_sha256'],seal.base.digest((p/'bank/manifest.json').read_bytes()));self.assertEqual(receipt['model_calls'],0)
