# Retrieval policy

Authenticate at the API, resolve an offline grant, compare clinical fixture IDs, verify the host capability, retrieve from the authoritative ledger, re-read each returned record, reject wrong-context/inactive/expired records and content-hash mismatch, deduplicate, enforce count and character budgets, and return source-linked evidence. The caller cannot supply a cache key or model state.

Optional semantic/adaptive ranking failure falls back to lexical retrieval in the same authorised ledger. Permission errors propagate. Ledger corruption/unavailability propagates to sanitised 503 at the service. No relevant source returns an empty list and no_approved_context; no model answer or diagnosis is fabricated. A provider outage never changes authorisation or verification.

Existing supersession removes predecessor evidence on trusted approval; revocation/delete remove later retrieval eligibility. Conflicting approved facts are returned as separate evidence records: automatic clinical conflict resolution is not implemented. Freshness enforces expiry; freshness weighting remains experimental. Query timeouts require trusted bounded rankers and ingress deadlines; arbitrary external ranking code is not safely cancellable in-process.

Context strings encode JSON evidence. Downstream consumers must preserve instruction/data separation and authorised review. Tests reject pending/rejected/revoked/expired/other-context memories and post-ranking revocation, plus corruption and cross-context supersession. Real KV stale-block/collision/tensor correctness tests remain blocked.
