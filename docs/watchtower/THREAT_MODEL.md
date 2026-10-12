# Threat model

NERVE application code, task text, reasoning outputs, telemetry, memory, learned routes and application credentials may be compromised. None may grant restart authority or establish a verified critical finding alone. Application anomalies cannot cause automatic universal shutdown. Unavailable or stale evidence is UNKNOWN, never NORMAL.

Trusted boundary: separately administered Guardian host, immutable deployment manifest, OS supervisor, pinned independent owner identity issuer, isolated notification secrets and externally protected audit anchor. Compromise of root/host/IdP exceeds this implementation's guarantees. Root-equivalent agents cannot be contained by same-host software.

Threats tested include forged telemetry, source disappearance, audit truncation/tampering, missing heartbeats, stale observations, notification failure, partial stop, process recreation, replayed restart, invalid/agent identities and expired authentication. Denial of observability alone alerts; it does not imply malicious execution. A failed required recovery check denies restart.

Clinical and shared services are excluded pending a reviewed dependency inventory. No real patient content enters collection or alerts. Store only allowlisted identifiers, aggregate counters, hashes and categorical evidence; no raw reasoning, prompts, credentials or clinical records. Local SQLite is not WORM: protected anchors detect accidental/tampered state under the stated administrator boundary; production off-host archival remains required.
