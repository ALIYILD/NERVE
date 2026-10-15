"""NERVE Evolution v1.3: framework-neutral, allowlisted executable agent demo.

Only two inert string transformations are exposed. Stored experience
never executes arbitrary code or changes permissions. Caller-supplied
agent_id is a local namespace, NOT authenticated identity.
"""
from dataclasses import asdict
import json

from .agent_learning_v12 import (
    AgentTask, FeedbackAgentCoordinator, RegisteredStrategy
)
from .evolution_v01 import EvolutionMemory
from .parallel_agents_v11 import AgentJob, BoundedParallelAgents


def _validate_email(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 180:
        raise ValueError("demo email must be nonempty and <=180 characters")
    return value


def _extract_raw(value):
    return value  # Deliberately ineffective candidate for measured evaluation.


def _extract_json(value):
    document = json.loads(value)
    if not isinstance(document, dict) or set(document) != {"email"}:
        raise ValueError("expected exactly one email field")
    return _validate_email(document["email"])


def _normalise_basic(value):
    return _validate_email(value).lower()


def _normalise_trim(value):
    return _validate_email(value).strip().lower()


def _unique_hint_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate strategy hint field')
        result[key] = value
    return result


def approved_memory_hint(content, registry):
    """Decode only the fixed data-only strategy schema against a host registry."""
    try:
        hint = json.loads(content, object_pairs_hook=_unique_hint_fields)
    except (ValueError, TypeError, RecursionError):
        return None
    if (type(hint) is not dict
            or set(hint) != {'schema', 'task', 'extract', 'normalise'}
            or hint['schema'] != 'nerve-demo-strategy-v1'
            or hint['task'] != 'email-normalization'
            or type(hint['extract']) is not str or type(hint['normalise']) is not str
            or ('extract', hint['extract']) not in registry
            or ('normalise', hint['normalise']) not in registry):
        return None
    return hint['extract'], hint['normalise']


STRATEGIES = (
    RegisteredStrategy("raw", "extract", _extract_raw),
    RegisteredStrategy("json-field", "extract", _extract_json),
    RegisteredStrategy("lower-only", "normalise", _normalise_basic),
    RegisteredStrategy("trim-lower", "normalise", _normalise_trim),
)

# Fixed training-only examples, not arbitrary caller-supplied reward labels.
FIXTURES = (
    ("  TRAIN.ONE@EXAMPLE.COM  ", "train.one@example.com"),
    ("  TWO@EXAMPLE.ORG  ", "two@example.org"),
)


class DemoAgentBridge:
    def __init__(self, path, *, agent_id="external-demo", max_workers=4, memory_session=None,
                 require_verified_memory=False):
        if type(require_verified_memory) is not bool or (require_verified_memory and memory_session is None):
            raise ValueError("strict execution requires a bound memory session")
        self.require_verified_memory = require_verified_memory
        if memory_session is not None:
            from .memory_gateway.session import BoundMemorySession
            if type(memory_session) is not BoundMemorySession:
                raise TypeError('host-bound memory session required')
        self.memory_session = memory_session
        self.agent = FeedbackAgentCoordinator(
            memory=EvolutionMemory(path), agent_id=agent_id,
            strategies=STRATEGIES, max_workers=max_workers
        )
        self.pool = BoundedParallelAgents(
            {"pipeline": self._run_one}, max_workers=max_workers,
            max_jobs=16
        )

    @staticmethod
    def capabilities():
        return (
            {"context": "extract", "strategies": ["raw", "json-field"]},
            {"context": "normalise", "strategies": ["lower-only", "trim-lower"]},
        )

    def train_fixed_fixtures(self):
        """Trusted program scores known tools on fixed examples.

        No feedback, scores or expected labels are accepted from MCP callers.
        Deliberately record the poor strategy last so recency is a meaningful
        baseline in paired tests, using exactly the same prior experiences.
        """
        count = 0
        for raw_email, canonical in FIXTURES:
            source = json.dumps({"email": raw_email}, sort_keys=True)
            for context, candidates, payload, expected in (
                ("extract", ("json-field", "raw"), source, raw_email),
                ("normalise", ("trim-lower", "lower-only"), raw_email, canonical),
            ):
                for strategy_id in candidates:
                    handler = self.agent.registry[(context, strategy_id)]
                    try:
                        outcome = handler(payload)
                    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                        outcome = None
                    self.agent.feedback(
                        context=context, strategy_id=strategy_id,
                        reward=float(outcome == expected)
                    )
                    count += 1
        return {"verified_training_observations": count,
                "source": "fixed synthetic fixtures; no user labels"}

    def choose(self, context, *, policy="utility"):
        if context not in ("extract", "normalise"):
            raise ValueError("only built-in safe contexts are supported")
        strategy_id, used_feedback = self.agent.select(context, policy=policy)
        return {"context": context, "strategy_id": strategy_id,
                "used_feedback": used_feedback,
                "warning": "Selection is research guidance, not authorisation"}

    def _run_one(self, payload):
        task_id, email_document, policy = payload
        if not isinstance(email_document, str) or not 1 <= len(email_document) <= 512:
            raise ValueError("demo JSON input must be <=512 characters")
        if policy not in ("utility", "recency"):
            raise ValueError("only utility and recency research policies supported")
        if self.memory_session is not None:
            return self._run_with_verified_memory(task_id, email_document, policy)
        return self._run_default(task_id, email_document, policy)

    def _run_default(self, task_id, email_document, policy):
        first = self.agent.run([
            AgentTask(task_id + ":extract", "extract", email_document)
        ], policy=policy)[0]
        if not isinstance(first.value, str):
            raise ValueError("string extraction result required")
        second = self.agent.run([
            AgentTask(task_id + ":normalise", "normalise", first.value)
        ], policy=policy)[0]
        return {
            "task_id": task_id,
            "result": second.value,
            "strategies": {
                "extract": first.strategy_id,
                "normalise": second.strategy_id,
            },
            "used_feedback": first.used_feedback or second.used_feedback,
            "policy": policy,
        }

    def _run_with_verified_memory(self, task_id, email_document, policy):
        """Approved data selects fixed registered tools, never executable code.

        This is the existing synthetic email demo. Clinical reasoning and free
        form agent instructions are deliberately outside this adapter.
        """
        evidence = self.memory_session.query('email normalization', limit=20)
        hints, provenance = set(), []
        for record in evidence['records']:
            hint = approved_memory_hint(record['content'], self.agent.registry)
            if hint is None:
                continue
            hints.add(hint)
            provenance.append({key: record[key] for key in ('memory_id', 'source_id', 'source_sha256')})
        if self.require_verified_memory and (len(hints) != 1 or len(provenance) != 1
                or evidence['fallback_reason'] == 'retrieval_backend_unavailable'):
            raise ValueError('strict execution requires one approved ranked strategy')
        if len(hints) == 1:
            extract, normalise = next(iter(hints))
            result = self.execute_plan(task_id=task_id, email_document=email_document,
                                       extract_strategy=extract, normalise_strategy=normalise)
            result.update(policy=policy, used_feedback=False)
            status = 'used'
        else:
            result = self._run_default(task_id, email_document, policy)
            status = 'conflicting_hints' if hints else 'no_valid_hint'
        result['verified_memory'] = {'status': status, 'provenance': provenance,
                                      'kv_status': evidence['kv_status'],
                                      'fallback_reason': evidence['fallback_reason']}
        result['outcome_memory'] = {'status': 'not_requested'}
        if self.memory_session.can_propose:
            # Completion is not correctness. No raw task/email/output or reward
            # is retained; independent host approval remains mandatory.
            observation = json.dumps({'schema': 'nerve-demo-outcome-v1',
                'task': 'email-normalization', 'strategies': result['strategies'],
                'execution_completed': True, 'correctness_verified': False}, sort_keys=True)
            try:
                result['outcome_memory'] = self.memory_session.propose(observation, 'demo-pipeline-outcome')
            except PermissionError:
                raise
            except Exception:
                result['outcome_memory'] = {'status': 'not_recorded', 'reason': 'memory_write_unavailable'}
        return result

    def run_pipeline(self, *, task_id, email_document, policy="utility"):
        if not isinstance(task_id, str) or not 0 < len(task_id) <= 48:
            raise ValueError("bounded task ID required")
        return self._run_one((task_id, email_document, policy))

    def run_pipelines(self, tasks, *, policy="utility"):
        """Concurrent independent two-stage tasks, all-or-nothing results."""
        tasks = tuple(tasks)
        if not 1 <= len(tasks) <= 16:
            raise ValueError("between 1 and 16 pipeline tasks required")
        validated = []
        for task in tasks:
            if not isinstance(task, dict) or set(task) != {"task_id", "email_document"}:
                raise ValueError("expected task_id and email_document")
            task_id = task["task_id"]
            if not isinstance(task_id, str) or not 0 < len(task_id) <= 48:
                raise ValueError("invalid pipeline task ID")
            validated.append(task)
        if len({task["task_id"] for task in validated}) != len(validated):
            raise ValueError("duplicate pipeline task IDs")
        outcomes = self.pool.run([
            AgentJob(task["task_id"], "pipeline",
                     (task["task_id"], task["email_document"], policy))
            for task in validated
        ])
        return [item.output for item in outcomes]

    def execute_plan(self, *, task_id, email_document, extract_strategy,
                     normalise_strategy):
        """Execute an explicitly chosen *allowlisted* two-stage plan.

        Plan inputs are untrusted strategy identifiers, never Python source.
        The plan is not allowed to modify feedback memory or permissions.
        """
        if not isinstance(task_id, str) or not 0 < len(task_id) <= 48:
            raise ValueError("bounded task ID required")
        if not isinstance(email_document, str) or not 1 <= len(email_document) <= 512:
            raise ValueError("bounded synthetic JSON document required")
        if (type(extract_strategy) is not str
                or ("extract", extract_strategy) not in self.agent.registry):
            raise ValueError("unregistered extract strategy")
        if (type(normalise_strategy) is not str
                or ("normalise", normalise_strategy) not in self.agent.registry):
            raise ValueError("unregistered normalise strategy")
        # Registered pure transformations only; no eval/exec/commands/network.
        extracted = self.agent.registry[("extract", extract_strategy)](
            email_document)
        if not isinstance(extracted, str):
            raise ValueError("registered extract must produce text")
        if len(extracted) > 512:
            raise ValueError("extract output too large")
        normalized = self.agent.registry[("normalise", normalise_strategy)](
            extracted)
        if not isinstance(normalized, str) or len(normalized) > 512:
            raise ValueError("invalid normalise output")
        return {
            "task_id": task_id, "result": normalized,
            "strategies": {"extract": extract_strategy,
                           "normalise": normalise_strategy},
            "feedback_written": False,
        }
