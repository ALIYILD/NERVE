"""Explicit punctuation repair for the opt-in synthetic registry guard.

Only an anchored comma followed by a source_id label is normalized. The v1
entity, code, citation, evidence and authorization checks remain authoritative.
This is a host parser revision, not model training or a semantic verifier.
"""
import re

from .grounding import GroundedRegistryAdapter


_COMMA_CITATION = re.compile(r'([A-Z]{4}-[0-9]{4}), ([Ss]ource_id: [a-zA-Z0-9_.:-]{1,96})')


class GroundedRegistryAdapterV2(GroundedRegistryAdapter):
    """Same host task contract and exact output semantics as v1, plus one form."""

    def respond(self, gateway, actor, request, *, task):
        normalization = 'none'
        delegate = self.inference

        class NormalizedInference:
            def respond(self, gateway, actor, request):
                nonlocal normalization
                response = delegate.respond(gateway, actor, request)
                output = response.get('output')
                match = _COMMA_CITATION.fullmatch(output) if type(output) is str else None
                if not match:
                    return response
                normalization = 'comma_before_source_label'
                # Copy: raw response capture by the calling benchmark stays intact.
                return {**response, 'output': f'{match[1]} {match[2]}'}

        result = GroundedRegistryAdapter(NormalizedInference()).respond(
            gateway, actor, request, task=task)
        result['grounding'].update(version='synthetic-registry-v2', input_normalization=normalization)
        return result
