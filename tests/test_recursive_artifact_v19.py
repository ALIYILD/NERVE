"""Check the hosted artifact harness through actual subprocess restarts."""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.verify_research_persistence_v19 import seed, verify


class ArtifactHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed_dir = self.root / 'producer'
        self.result = seed(self.seed_dir)
        self.download = self.root / 'download'
        shutil.copytree(self.seed_dir, self.download)
        self.output = self.root / 'resumed'

    def test_downloaded_checkpoint_resumes_and_adds_only_unseen_recipes(self):
        evidence = verify(self.download, self.output, self.result['checkpoint_sha256'])
        self.assertEqual(evidence['status'], 'artifact_resume_verified')
        self.assertEqual(evidence['completed_runs'], 2)
        self.assertGreater(evidence['new_candidates_evaluated'], 0)
        self.assertEqual(evidence['population_before'], self.result['known_population_size'])
        self.assertEqual(evidence['cross_tenant_leaks'], 0)
        self.assertTrue((self.output / 'verification.json').is_file())

    def test_missing_download_does_not_silently_restart(self):
        (self.download / 'evolution.json').unlink()
        with self.assertRaises(FileNotFoundError):
            verify(self.download, self.output, self.result['checkpoint_sha256'])
        self.assertFalse(self.output.exists())

    def test_transport_digest_mismatch_stops_before_experiment(self):
        with self.assertRaisesRegex(ValueError, 'differs from producer'):
            verify(self.download, self.output, '0' * 64)
        self.assertFalse(self.output.exists())

    def test_producer_evidence_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'preserve'):
            verify(self.download, self.download, self.result['checkpoint_sha256'])


if __name__ == '__main__':
    unittest.main()
