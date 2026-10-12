"""Measured local arithmetic smoke check, never a paper benchmark or release.

Public generated arithmetic tasks and a strict integer grader isolate transport
plumbing. No answers reach the provider; no raw answers are retained in evidence.
"""
import re

from .cue_engine import Cue
from .cue_evaluation import DatasetManifest, promotion_decision
from .cue_experiment import ExperimentTask, JudgeReceipt, ExperimentBlocked, run_experiment


def run_local_smoke(adapter):
    identity = adapter.inspect()
    profile, model = adapter.profile, adapter.model_config
    manifest = DatasetManifest(('local-discovery-unused',), ('local-selection-unused',),
                               ('local-addition', 'local-subtraction'))
    tasks = (ExperimentTask('local-addition', 'Compute 17 + 26. Return only the integer.', '43'),
             ExperimentTask('local-subtraction', 'Compute 81 - 39. Return only the integer.', '42'))
    cue = Cue('local-arithmetic-check', 1, 'Check the arithmetic before answering.',
              'instruction', profile.key, ('research',), 'fixed-local-smoke-not-discovered')

    def grade(*, output, expected):
        # This is only format safety for these fixed arithmetic tasks, not a
        # general safety classifier or clinical evaluation.
        integer = re.fullmatch(r'-?[0-9]{1,12}', output.strip()) is not None
        return JudgeReceipt(integer and output.strip() == expected, integer)

    try:
        report = run_experiment('local-arithmetic-smoke', cue, manifest, tasks, model,
            adapter, grade, max_calls=4, max_cost_usd=.004, per_call_cost_cap_usd=.001,
            permission_granted=True)
    except ExperimentBlocked as exc:
        return {'schema': 'nerve-cce-local-smoke-v1', 'state': 'blocked',
                'scope': 'incomplete local arithmetic smoke; not effectiveness evidence',
                'reason': exc.reason, 'attempted_calls': exc.attempted_calls,
                'failed_calls': exc.failed_calls, 'known_external_provider_fee_usd': exc.known_cost_usd,
                'identity': identity, 'adapter': adapter.summary(), 'report': None,
                'paper_reproduced': False, 'activation_authorized': False}
    decision = promotion_decision(report, (), generator_id='fixed-local-smoke')
    return {'schema': 'nerve-cce-local-smoke-v1', 'state': 'completed',
            'scope': 'two public arithmetic tasks; local instruction transport only',
            'identity': identity, 'report': report.to_dict(), 'metrics': report.metrics,
            'decision': decision.to_dict(), 'adapter': adapter.summary(),
            'paper_reproduced': False, 'activation_authorized': False,
            'safety_scope': 'strict integer output format on fixed arithmetic tasks only',
            'limitations': ['two pairs cannot establish effectiveness',
                'answer calibration unavailable', 'no independent approval receipt',
                'observational local serving identity; not worker deployment attestation',
                'external provider fee only; local compute cost unmeasured']}
