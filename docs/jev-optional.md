# Optional TypeSafe AI / Jev integration

Jev is an **optional** research-review subagent, enabled only when a host explicitly injects a reviewer into ParallelEvolutionCycle.

Official API reference: https://docs.typesafe.ai/api
Endpoint: POST https://api.typesafe.ai/v1/systemone
Model: jev-latest
Request: synthetic aggregate WorldCore metrics and a Noul regression-risk question.
Response: typed answers.regression_risk.noul.

## Local smoke test

Run in the same terminal that has TYPESAFE_API_KEY exported:

```bash
cd NERVE
export PYTHONPATH=src
python -m nerve_awim.jev_optional
```

This sends one synthetic, non-personal evaluation request to TypeSafe. It prints model identity, risk estimate, latency, and token usage, but never the key. There is no additional required SDK dependency.

## Optional integration in a private Python service

```python
from nerve_awim.jev_optional import JevResearchReviewer
from nerve_awim.evolution_cycle_v11 import ParallelEvolutionCycle

loop = ParallelEvolutionCycle(
    memory=my_evolution_memory,
    agent_id='researcher',
    jev_reviewer=JevResearchReviewer(timeout=8),
)
report = loop.run(my_typed_proposals, context='WorldCore')
```

Providing the reviewer enables calls to the external API; omitting it keeps the original provider-independent behaviour. A terminal key is not automatically available to GitHub Actions, remote containers, or ChatGPT.

## Trust boundaries

- Key is read from TYPESAFE_API_KEY only when the adapter makes a request.
- Fixed official HTTPS endpoint; timeout 8 seconds by default; no implicit retries.
- Strict allowlist of five synthetic numeric metrics, no patient data, raw sensor records, text, or identities.
- Jev opinions are advisory only. WorldCore's independent reliability and recovery gates cannot be overridden.
- Missing key, transport errors or malformed typed responses fail closed; an enabled provider failure rejects the research batch.
- NERVE does not currently demonstrate that Jev improves speed, cost, accuracy, clinical safety or physical-AI reliability.
- CI mocks TypeSafe; live connectivity requires a private environment containing a valid key.

Do not send regulated clinical information without an appropriate separate vendor, security and data-protection assessment. Revoke any leaked key.
