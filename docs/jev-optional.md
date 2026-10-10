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

## Single-call batch reviews

For the research coordinator, use `JevBatchReviewer` from
`nerve_awim.jev_batch` instead of `JevResearchReviewer`. It packages up to
six independent candidate questions into a single TypeSafe System One
request, matching the provider's documented batched-question interface.
This *reduces request count*, but latency and speedups must still be measured
on a real account before claiming performance gains.

```python
from nerve_awim.jev_batch import JevBatchReviewer
reviewer = JevBatchReviewer(timeout=8)
```

The parallel coordinator recognises `review_many` automatically. The provider
remains optional, no credentials are committed, and batch advice never
changes the independent WorldCore acceptance rules.

## Preferred one-command live smoke test

When `TYPESAFE_API_KEY` is already exported in your **own terminal**:

```bash
cd NERVE
git pull --ff-only origin main
export PYTHONPATH=src
python3 -m nerve_awim.jev_smoke
```

The command makes exactly **one** TypeSafe HTTPS request containing two typed Noul judgments about fixed synthetic metrics. Its output contains only model identity, risk scores, elapsed time, token counts and a warning. It never prints or stores the key. Our CI cannot run the live service because no private key is configured there; the unit test uses a fake reviewer and checks the single-batch behaviour. Revoke the key after the real smoke test, especially because it was shared in conversation text.

## Optional protected GitHub Actions live test

The workflow `.github/workflows/jev-live.yml` is **manual only**
(`workflow_dispatch`) and restricted to `ALIYILD/NERVE` on `main`.
It has read-only repository permissions, a three-minute timeout, and
references only the `typesafe-live` **environment** secret. Pushes and
pull requests do not trigger this paid external API call.

Before enabling it:

1. Revoke the TypeSafe key that was shared in a conversation, and create
   a fresh limited-purpose credential. Do not reuse the disclosed key.
2. In GitHub, open `ALIYILD/NERVE` > **Settings** > **Environments**.
3. Create an environment named `typesafe-live`; restrict deployment branches
   to `main`, and enable required reviewers if your plan allows it.
4. In that environment (not in the source repository), add an
   **environment secret** named `TYPESAFE_API_KEY` containing only the
   **new** credential.
5. Open **Actions** > **TypeSafe Jev - manually approved live smoke test**
   > **Run workflow**, select `main` and approve the protected environment
   if prompted.
6. Review the minimal output: model ID, two synthetic risk values,
   token usage and elapsed time. Never upload raw responses or API keys.

If the secret is missing, the workflow exits without making a request.
CI cannot verify GitHub environment protection settings or run against an
unconfigured live TypeSafe account. It validates the workflow's source
and runs API contract tests with synthetic, mocked responses instead.

Security note: In public repositories, contributors with sufficient write
access can modify workflow code. Restrict write access and protect
`main`; the protected environment should require independent review.

## Jev agreement benchmark — offline by default

The new `jev_agreement_v12.py` evaluates six synthetic WorldCore
candidate scenarios with a fixed deterministic regression oracle.
It records agreement, false-positive and false-negative counts, the
separate deterministic human-review eligibility decision, request latency,
and reported token usage. No cost estimate is calculated because
pricing and real usage have not been independently established.

Run the safe **fixture-only** example without any API key:

```bash
export PYTHONPATH=src
python -m nerve_awim.jev_agreement_v12
```

**Important:** the synthetic fixture deliberately contains two incorrect
advisory classifications to test that NERVE can detect and report errors.
Fixture agreement is not actual Jev accuracy. This is not a measured model
speedup, and no medical/physical-AI claims follow from the experiment.

To compare real Jev judgments *after provisioning a fresh private key*,
run `python -m nerve_awim.jev_agreement_v12 --live` locally, or select
**comparison** in the manual `TypeSafe Jev` GitHub workflow. The workflow
supports two mutually exclusive choices: **smoke** (2 judgments) or
**comparison** (6 judgments), each performed in one API request.
Ordinary push/PR CI never uses a paid API.

The deterministic reviewer continues to reject candidates that violate
completion, abort or constraint requirements regardless of Jev's advice.
No candidate is promoted or deployed automatically.
