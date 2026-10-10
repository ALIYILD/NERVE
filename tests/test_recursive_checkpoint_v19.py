"""Persistence, corruption and cross-process exploration regression coverage."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.recursive_research_v19 import run
from nerve_awim.research_checkpoint_v19 import load_checkpoint, MAX_BYTES
from nerve_awim.recursive_evolution_v19 import (
    EvalScore, RecursiveEvolutionLoop, RetrievalGenome,
)


class RecursiveCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'evolution.json'

    def test_separate_processes_resume_until_all_35_recipes_examined(self):
        previous_size = 0
        total = 0
        for index in range(1, 7):
            process = subprocess.run([
                sys.executable, 'scripts/recursive_research_v19.py',
                '--resume', str(self.path), '--checkpoint-out', str(self.path),
                '--seed', str(index), '--generations', '6',
            ], capture_output=True, text=True, check=True,
               env={**os.environ, 'PYTHONPATH': 'src'})
            report = json.loads(process.stdout)
            total += report['candidates_evaluated']
            self.assertEqual(report['completed_runs'], index)
            self.assertEqual(report['cumulative_candidates'], total)
            self.assertEqual(report['resumed_from_checkpoint'], index > 1)
            self.assertGreaterEqual(report['known_population_size'], previous_size)
            self.assertEqual(report['remaining_candidates'], 35 - report['known_population_size'])
            self.assertEqual(report['report_only_holdout']['cross_tenant_leaks'], 0)
            previous_size = report['known_population_size']
            if report['remaining_candidates'] == 0:
                break
        self.assertEqual(previous_size, 35)
        self.assertEqual(total, 34)  # canonical baseline is checked separately
        final = run(checkpoint=self.path, seed=99)
        self.assertEqual(final['candidates_evaluated'], 0)
        self.assertEqual(final['stop_reason'], 'search_space_exhausted')

    def test_checkpoint_excludes_all_fitness_holdout_and_authority(self):
        report = run(checkpoint_out=self.path, generations=1)
        payload = json.loads(self.path.read_text())['checkpoint']
        self.assertEqual(set(payload), {
            'checkpoint_schema', 'study_protocol', 'evaluator_fingerprint',
            'selected', 'population_archive', 'completed_runs', 'cumulative_candidates'})
        self.assertEqual(load_checkpoint(self.path).selected,
                         RetrievalGenome(**report['selected']))

    def test_evaluator_change_resets_even_if_champion_did_not_regress(self):
        run(checkpoint_out=self.path, generations=1)
        with patch('nerve_awim.research_checkpoint_v19.evaluator_fingerprint', return_value='new'):
            result = run(checkpoint=self.path, generations=1)
        self.assertEqual(result['checkpoint_reset_reason'], 'evaluator_changed')
        self.assertFalse(result['resumed_from_checkpoint'])
        self.assertEqual(result['baseline'], {'token_weight': 3, 'trigram_weight': 0})
        self.assertEqual(result['completed_runs'], 1)

    def test_legacy_unversioned_report_migrates_with_explicit_reset(self):
        report = run(generations=1)
        del report['evaluator_fingerprint']
        self.path.write_text(json.dumps(report))
        result = run(checkpoint=self.path, checkpoint_out=self.path, generations=1)
        self.assertEqual(result['checkpoint_reset_reason'], 'legacy_unversioned')
        self.assertFalse(result['resumed_from_checkpoint'])
        self.assertEqual(load_checkpoint(self.path).completed_runs, 1)

    def test_corruption_fails_without_overwriting_history(self):
        run(checkpoint_out=self.path, generations=1)
        data = json.loads(self.path.read_text())
        data['checkpoint']['selected']['token_weight'] = 5
        self.path.write_text(json.dumps(data))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            run(checkpoint=self.path, checkpoint_out=self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_atomic_replace_preserves_prior_checkpoint(self):
        run(checkpoint_out=self.path, generations=1)
        before = self.path.read_bytes()
        with patch('nerve_awim.research_checkpoint_v19.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                run(checkpoint=self.path, checkpoint_out=self.path, generations=1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_failed_evaluation_never_publishes_checkpoint(self):
        run(checkpoint_out=self.path, generations=1)
        before = self.path.read_bytes()
        with patch('scripts.recursive_research_v19.RecursiveEvolutionLoop.run', side_effect=RuntimeError('gate')):
            with self.assertRaises(RuntimeError):
                run(checkpoint=self.path, checkpoint_out=self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_malformed_archives_and_counters_rejected(self):
        report = run(generations=1)
        cases = [dict(report, completed_runs=True),
                 dict(report, cumulative_candidates=-1),
                 dict(report, completed_runs=2**53),
                 dict(report, population_archive=report['population_archive'] * 2),
                 dict(report, selected={'token_weight': True, 'trigram_weight': 1})]
        for bad in cases:
            with self.subTest(bad=bad):
                self.path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    load_checkpoint(self.path)

    def test_oversized_and_truncated_checkpoints_rejected(self):
        for raw in (' ' * (MAX_BYTES + 1), '{"checkpoint":'):
            self.path.write_text(raw)
            with self.assertRaises(ValueError):
                load_checkpoint(self.path)

    def test_global_exploration_finds_unseen_recipe_beyond_local_neighbours(self):
        target = RetrievalGenome(0, 5)
        class Objective:
            def evaluate(self, genome, split):
                hits = 8 if genome == target else 2
                return EvalScore(hits / 10, hits, 10, 0)
        archive = tuple(RetrievalGenome(t, g) for t in range(6) for g in range(6)
                        if t + g and (t, g) != (0, 5))
        report = RecursiveEvolutionLoop(objective=Objective(), generations=1).run(
            previous_population=archive)
        self.assertEqual(report['selected'], {'token_weight': 0, 'trigram_weight': 5})
        self.assertEqual(report['candidates_evaluated'], 1)
        self.assertEqual(report['remaining_candidates'], 0)
        self.assertEqual(report['status'], 'candidate_for_human_review')


if __name__ == '__main__':
    unittest.main()
