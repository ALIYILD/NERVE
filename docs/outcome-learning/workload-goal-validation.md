# Workload-linked goal validation — 2026-10-15

- NERVE: 1,469 tests run, 1,468 passed, one skipped; full suite completed in 202.358 seconds with the existing socket/nested-sandbox permissions.
- PerfFlux: 71 relevant tests passed; modified test lint/format checks passed.
- Clinical OS: three offline process tests passed.
- Both host source manifests verified against the pinned NERVE source.
- NERVE CLI and Agent OS bridge completed an externally supplied synthetic workload manifest, with status inspection using the same dataset binding.
- Negative tests cover changed targets/provenance, cross-partition duplicate tasks, unsupported domain, incorrect CPU labels, excessive file size, duplicate JSON keys, invalid targets, unsupported data kind, and budget exhaustion before candidate calls.
- A deliberately unachievable goal remains blocked; successful commands do not override the measurable target.

The intake implementation is complete for the bounded local contract. Representative real-world task data, independent label/provenance attestation, remote authentication, production scheduling, and live clinical/GPU activation are not demonstrated. The example exporter is explicitly synthetic.
