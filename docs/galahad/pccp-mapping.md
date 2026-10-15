# PCCP design alignment — internal draft

This is an engineering mapping, not a regulatory submission, authorization or
claim of compliance. Regulatory-advisor review is required before external use.
Reference: FDA's [August 2025 final guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence),
which is newer than the December 2024 version named in the adoption plan.

| PCCP component | NERVE design | Outstanding evidence |
|---|---|---|
| Description of modifications | Closed rule/schema/prompt/retrieval/routing seams; A/B/C risk tiers; manual human-keyed promotion; global default | Product-specific intended use, bounded modification ranges and reviewer approval |
| Local modifications | Site policies must carry separate justification, bank identity, acceptance criteria and monitoring | Site-specific validation and operational monitoring |
| Modification protocol | Registration v2 fixes inputs, pilot disclosure, outcomes, exclusions, capacity prices, alpha and stop rules before calls | Signed production gate, real prospective studies and independent isolation |
| Impact assessment | Wrong promotions can alter answers, sources, abstention or resource use; verifier vetoes, controls, regression, rollback and tier-specific evidence bound those risks | Clinical risk assessment, human factors and safety validation |
| Monitoring and updates | Shadow/canary, named rollback and drift-triggered review required for appropriate change tiers | Live canary and drift evidence; these are not established by the retrospective audit |

Proposed internal labeling: “Research system evaluated under a controlled change
plan; no automatic clinical deployment.” Tier A still needs a human signature;
Tier B adds cost/latency/permission evidence; Tier C adds isolated safety studies,
shadow/canary and a named owner. Research probe changes also require Tier C review.
