# Proposed public audit cohort v3

This is a preregistered proposal for independent review, not a review attestation
or an admitted study. No model inference or registration was performed.
The 2 train / 4 selection / 4 retention / 6 final partition was authored before
model outcomes. Training is the only partition available to lesson proposals.
All gold decisions and applicable source IDs were chosen explicitly before
checking agreement with the existing deterministic oracle. Citation fields follow
the documented predicate schema.

The substantive additions combine reconvergent provenance DAGs, overlapping
parents, component/identity joins, majority disagreement, and temporal wrappers.
They are new composed tasks under the existing oracle, not new reasoning
primitives. Some pairings deliberately change root applicability as well as graph
structure. Semantic novelty checking ignores source IDs, ordering, assertion
wording, positive-price magnitude and within-window timestamp changes; none of
those incidental edits establish novelty. All 16 canonical identities are unique
and absent from the public development controls, fixed v1 and composition v2.
The independent reviewer must still judge whether the compositions are useful
and sufficiently different; hash inequality alone does not prove that.

No private evidence or credentials are used. These simulated source declarations
are trusted fixture facts, not authenticated provider observations. At most six
sources appear per task, within the existing 64-source validator cap. Some valid
DAGs intentionally have descendants dated before their parent: the schema allows
this, and such descendants remain derived rather than independent roots. No
claim of production realism is made for that case. All tasks share four existing
predicates and a deterministic exact-citation grader. Six final cases cannot
satisfy the separate CCE 30-pair gate or establish broad generalization.

Manifest SHA256: `ef671cbfdda13620f3ea31de9165224e0c28f39e13fa6a018be7243e264cea37`.

Oracle source revision: `83f2c5e092a55c103e2e8fbcd71227c9b029dd3b9e5ca63922918e1ece6d911b`.

| Split | Composition | Hand-authored decision and applicable roots | Rationale |
| --- | --- | --- | --- |
| train | expired-root-diamond-refresh | unknown; no citations | A shared stale root branches and reconverges. No fresh descendant is an independent receipt; graph multiplicity cannot refresh the root. |
| train | independent-root-survives-derived-diamond | supported; free | A current independent free root remains applicable despite two contradictory derived branches and their reconvergence; cite the root once. |
| selection | credential-majority-not-resolution | unknown; yes-a, yes-b, no | Two positive independent roots do not outvote a negative root; a derived majority and reconciliation cannot resolve conflict. |
| selection | fresh-root-stale-derived-wrapper | supported; fresh | A stale child does not make its fresh parent stale; the contradictory projection and future independent root are inapplicable. |
| selection | request-join-time-laundering | contradicted; observed | Combining a stale target and fresh different request cannot produce an independent target success or supersede the boundary failure. |
| selection | pricing-component-splice | contradicted; input-free, output-free | Each independent price record is paid. Splicing zero components across records cannot establish a free complete price. |
| retention | old-parent-does-not-disqualify-new-independent-root | supported; current | A refreshed stale negative is still derived; only the new independent positive root counts, even though a merge mentions both. |
| retention | catalog-provider-model-composite-key | contradicted; negative | Model and provider components cannot be joined across two wrong-identity roots. A genuine target negative prevails over their derived target and stale positive. |
| retention | execution-complete-conflict-citations | unknown; yes-a, yes-b, no | All three applicable roots must be cited, including agreement; exclude future dissent and a multi-root echo. Unknown is not an empty citation set. |
| retention | pricing-future-root-with-past-descendants | unknown; no citations | The valid DAG schema does not require chronological causality; even an in-window child of a future root is derived, not a fresh independent observation. |
| final | credential-disjoint-branches-cross-identity-conflict | unknown; yes, no | Independent matching roots conflict across two derived branches. Another provider and a convergent optimistic probe cannot erase either target root. |
| final | catalog-consensus-identity-bridge-future-dissent | supported; yes-a, yes-b | Both target roots agree; wrong-model dissent cannot acquire identity through derivation, and future dissent cannot be pulled into the present by a merge. |
| final | execution-identity-cartesian-join-plus-root-conflict | unknown; yes, no | A Cartesian identity join is excluded while two genuine target roots conflict. Neither the three distractor votes nor the joined record alters the citation set. |
| final | price-unanimous-paid-opposite-component-echoes | contradicted; paid-a, paid-b, paid-c | Three independently paid full prices all count; overlapping-parent zero projections and their merge do not manufacture a free observation. |
| final | catalog-stale-and-foreign-parent-laundering | unknown; no citations | No target root is applicable. Recursive freshness laundering and adding a fresh foreign provider cannot establish target identity and current observation together. |
| final | pricing-conflict-with-stale-future-tiebreakers | unknown; free, paid | The two current roots conflict. Stale/future tie-breakers and a derived resolution do not supersede either applicable root. |

Validation performed: existing registry strict schema/gold validation, existing
canonical identity collision checks against all above public cohorts, and exact
split sizes. No reviewer identity or gold/novelty/split-separation attestation has
been created. Registration and execution require the independent review stage.
