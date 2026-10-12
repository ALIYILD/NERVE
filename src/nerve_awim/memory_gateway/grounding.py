"""Opt-in host guard for one synthetic registry grammar, not a semantic verifier.

The model remains untrusted. This validates only the selected approved evidence;
it does not certify that retrieval found every conflicting record in a ledger.
No answer key, training, general scientific reasoning or clinical authority is
provided by this deterministic guard.
"""
from dataclasses import asdict, dataclass
import re

from .contracts import MemoryRequest


_OBJECT = r'[A-Z]{2}[0-9]{2}'
_CODE = r'[A-Z]{4}-[0-9]{4}'
_SOURCE = r'[a-zA-Z0-9_.:-]{1,96}'
_FACT = re.compile(rf'The synthetic registry lists object ({_OBJECT}) with access code ({_CODE})\.')
_SHORT = re.compile(rf'({_CODE})(?:[.]? (?:[Ss]ource_id: )?({_SOURCE}))?\.?')
_SENTENCE = re.compile(rf'The access code for object ({_OBJECT}) is ({_CODE})\.(?: [Ss]ource_id: ({_SOURCE}))?')


@dataclass(frozen=True)
class RegistryGroundingTask:
    """Host construction only. Contains the target entity, never its answer."""

    object_id: str

    def __post_init__(self):
        if type(self.object_id) is not str or not re.fullmatch(_OBJECT, self.object_id):
            raise ValueError('synthetic registry object identifier required')

    @property
    def query(self):
        return (f'In the synthetic registry, what is the access code for object {self.object_id}? '
                'Return only the code and source_id; abstain if unsupported.')


class GroundedRegistryAdapter:
    """Wrap a host-owned inference adapter with exact entity/code validation.

Calls the wrapped adapter once, then rechecks authoritative access and evidence.
Rejected model prose is replaced by a fixed abstention. Accepted output is
canonicalized with a matching approved source identifier, including when the
model omitted that identifier. This is system-level filtering, not model learning.
"""

    def __init__(self, inference):
        self.inference = inference

    def respond(self, gateway, actor, request, *, task):
        if type(task) is not RegistryGroundingTask or type(request) is not MemoryRequest:
            raise ValueError('host-owned registry task and memory request required')
        if request.query != task.query:
            raise ValueError('registry task does not match exact request query')
        selected = gateway.retrieve(actor, request)
        response = self.inference.respond(gateway, actor, request)
        current = gateway.retrieve(actor, request)
        if (current.source_digest != selected.source_digest or current.records != selected.records
                or response.get('source_digest') != selected.source_digest
                or response.get('records') != [asdict(r) for r in selected.records]):
            raise PermissionError('grounding evidence changed')
        gateway._require(actor, request.scope, 'read')
        reason, source, code, citation_added = self._check(task, current.records, response.get('output'))
        result = dict(response)
        accepted = reason == 'supported'
        result.update(output=f'{code} Source_id: {source}' if accepted else 'Unsupported registry answer; abstaining.',
                      status='generated_requires_review' if accepted else 'abstained',
                      review_required=True, synthetic_only=True,
                      grounding={'version': 'synthetic-registry-v1', 'accepted': accepted,
                                 'reason': reason, 'citation_added': citation_added,
                                 'output_canonicalized': accepted,
                                 'scope': 'selected_approved_evidence_only'})
        return result

    @staticmethod
    def _check(task, records, output):
        def reject(reason):
            return reason, None, None, False

        matches = []
        for record in records:
            fact = _FACT.fullmatch(record.content)
            if not fact or record.status != 'approved' or not re.fullmatch(_SOURCE, record.source_id):
                return reject('invalid_evidence')
            if fact[1] == task.object_id:
                matches.append((fact[2], record.source_id))
        if not matches:
            return reject('unsupported_entity')
        if len({code for code, _ in matches}) != 1:
            return reject('conflicting_evidence')
        if type(output) is not str or not 1 <= len(output) <= 512:
            return reject('invalid_answer_format')
        sentence = _SENTENCE.fullmatch(output)
        short = _SHORT.fullmatch(output)
        if sentence:
            if sentence[1] != task.object_id:
                return reject('wrong_entity')
            code, source = sentence[2], sentence[3]
        elif short:
            code, source = short[1], short[2]
        else:
            return reject('invalid_answer_format')
        if code != matches[0][0]:
            return reject('wrong_code')
        sources = {source_id for _, source_id in matches}
        if source is not None and source not in sources:
            return reject('wrong_citation')
        return 'supported', source or sorted(sources)[0], code, source is None
