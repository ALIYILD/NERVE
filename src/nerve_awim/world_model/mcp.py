"""Optional inspection-only tools, bound to an authenticated host actor.

No tenant arguments, authority issuance, evidence writes or deployment methods.
The existing server registers these only when a trusted host injects a binding.
"""
from .registry import Registry


class InspectionTools:
    def __init__(self, ledger, actor):
        ledger.authority.require(actor,'auditor')
        self.ledger,self.actor=ledger,actor

    def inspect_model(self, model_id):
        model=Registry(self.ledger).get(self.actor,model_id)
        return {key:model[key] for key in ('model_id','state','rulebook_hash','executable_hash','environment_revision')}


def register(server, binding):
    if type(binding) is not InspectionTools:
        raise TypeError('host-authenticated inspection binding required')
    @server.tool()
    def inspect_world_model(model_id:str)->dict:
        """Inspect hashes and status in the host-bound scope. No activation authority."""
        return binding.inspect_model(model_id)
