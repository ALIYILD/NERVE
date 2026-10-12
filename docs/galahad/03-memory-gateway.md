# Gateway contract

Implemented in src/nerve_awim/memory_gateway/{contracts,gateway}.py. Typed request, scope, provenance, cache identity, policy decision, invalidation, metrics and retrieval contracts reuse the existing MemoryRecord.

Operations: propose pending semantic/episodic/procedural text; trusted decide; retrieve authorised approved evidence; revoke; delete; host capability revoke; scoped aggregate metrics; database/provider health. Deletion returns cache_purge_confirmed and backup_erasure_verified separately. Null-provider purge means there are no provider objects, not that backups are erased. Galahad purge remains unconfirmed.

All operations check the original host capability and exact tenant/agent/context. Administrative operations recheck record context. Approval also checks a legacy candidate's superseded predecessor context. Reads re-read status after advisory retrieval and validate SHA256 of content. Records may be revoked immediately after a completed read; no cross-process snapshot or retroactive erasure of delivered responses is promised.

Limits: 1–20 results; at most 20 advisory candidates inspected; query 1–256 characters; evidence budget 256–32768 characters; existing per-record content limit 2048 characters. Default 1000 records per scope includes pending/rejected records, configurable 1–10000. Quota enforcement requires all writers to use one gateway instance. External ledger writes and multiple processes need a future transactional quota migration. Metrics retain at most 1024 scopes, dropping new metric buckets beyond that cap.

KV save_kv/restore_kv explicitly raise NotImplementedError: inference/runtime integration is not implemented. Retrieval always reports prefill. Identity hashing alone is not evidence of compatibility. Health probes SQLite without creating a missing store and degrades when the provider throws; corrupted/missing authority storage cannot silently become an empty successful response.

Existing ledger SQLite is plaintext research storage. Neither this wrapper nor hashes encrypt it. Synthetic/public data only.
