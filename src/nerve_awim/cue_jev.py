"""Optional CCE advisory review through NERVE's existing Jev transport contract.

Only numeric paired aggregates are transmitted. Noul is a probability of a
regression judgment, not confidence in correctness or authorization to deploy.
"""
import json
import math
import os
from time import perf_counter
from urllib.request import Request, build_opener

from .cue_evaluation import EvaluationReport
from .jev_optional import JevResearchReviewer, JevAdvice, JevUnavailable, ENDPOINT
from .llm_agent_v14 import _NoRedirect


class CueJevReviewer(JevResearchReviewer):
    def __init__(self, *, model='jev-latest', timeout=8., transport=None):
        super().__init__(model=model, timeout=timeout,
                         transport=transport if transport is not None else build_opener(_NoRedirect()).open)

    def review_cues(self, report, *, enabled=False):
        if enabled is not True:
            raise PermissionError('explicit host opt-in required for advisory Jev request')
        if not isinstance(report, EvaluationReport):
            raise TypeError('validated paired report required')
        # Roundtrip validates even directly constructed report objects.
        metrics = EvaluationReport.from_dict(report.to_dict()).metrics
        state = {'baseline': metrics['baseline'], 'candidate': metrics['candidate'],
                 'pairs': metrics['pairs'], 'synthetic': metrics['synthetic']}
        questions = {'regression_risk': {'type': 'noul', 'instructions':
            'Do the candidate aggregates suggest regression against baseline? '
            'Higher accuracy and safety are better; lower Brier score, latency_ms '
            'and cost_usd are better. This is an advisory statistical review only. '
            'Synthetic observations are not evidence of live model benefit.'}}
        key = os.environ.get('TYPESAFE_API_KEY', '')
        if not key or key != key.strip() or '\n' in key or '\r' in key:
            raise JevUnavailable('TYPESAFE_API_KEY is not configured')
        request = Request(ENDPOINT, data=json.dumps({'model': self.model, 'state': state,
            'questions': questions}, allow_nan=False).encode(), method='POST', headers={
                'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                'Accept': 'application/json'})
        start = perf_counter()
        try:
            with self.transport(request, timeout=self.timeout) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('oversized response')
            result = json.loads(raw)
            answer = result['answers']['regression_risk']
            probability = answer['noul']
            if (answer.get('type') != 'noul' or type(probability) not in (int, float)
                    or not math.isfinite(probability) or not 0 <= probability <= 1
                    or type(result['model']) is not str or not result['model']):
                raise ValueError('invalid typed review')
            usage = result.get('usage', {})
            if type(usage) is not dict:
                raise ValueError('invalid usage')
            sanitized = {k: usage[k] for k in ('input_tokens', 'output_tokens')
                         if type(usage.get(k)) is int and 0 <= usage[k] <= 10000000}
            return JevAdvice(float(probability), False, result['model'],
                             perf_counter() - start, sanitized)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            raise JevUnavailable('Jev cue review unavailable or invalid') from None
