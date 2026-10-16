# Attended relaunch — 16 October 2026

The user explicitly authorized a new attended execution window after the overnight run closed. Prior evidence and the closed handoff remain intact. The new prospective protocol is `evidence/family-b-attended-protocol-v2.json`. Inference must stop by 10:15 UTC (11:15 London), leaving fifteen minutes for backup, pod stop/readback and handoff before 11:30 London.

The same cumulative six GPU hours include the prior 1,160.783 running seconds. The shared physical-attempt limit remains 6,000; prior attempts are zero. One A40 pod at a time, exact model digest, one conditional holdout slice, no signing. No actual bank or candidate exists at relaunch.

CPU preflight already passed 2,226 tests with two dependency skips, and 18 focused bank/adapter tests passed. The only study logic change is the prospective execution window/version/source-pin path. A focused registration test checks the new bound and retained cumulative budget before pod startup.

Required operations: structured Runpod get/start/stop; port-specific SSH and SCP after fresh connection discovery; restore the pinned cached runtime; transfer the frozen source archive; run the versioned bank builder and study harness; archive and copy private evidence; feature-branch commits/push. No persistent UI permission is assumed. Any execution approval request will identify its actual command.

The port-specific commands below use the provider's fresh direct SSH address after start; `<port>` is not an assumed persistent port. Key and host verification stay enabled.

```sh
scp -P <port> -i /Users/aliyildirim/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes /Users/aliyildirim/nerve-research-runs/overnight-resume-20261016/bootstrap-pinned-runtime.sh root@<host>:/workspace/nerve-overnight-runtime/bootstrap-pinned-runtime.sh
ssh -p <port> -i /Users/aliyildirim/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes root@<host> bash /workspace/nerve-overnight-runtime/bootstrap-pinned-runtime.sh
```

The bootstrap uses `apt-get` only if `zstd` is absent, extracts the existing `/workspace/nerve-overnight-runtime/ollama-0.40.5.tar.zst` to `/usr`, and starts Ollama bound to loopback with the existing `/workspace/nerve-smoke/models` cache. It does not download another model or invoke inference. The study commands run inside the transferred frozen checkout with `PYTHONPATH=src`:

```sh
python3 scripts/build_scientific_task_bank_v3.py --directory /root/nerve-attended-bank-v3 --protocol docs/galahad/evidence/family-b-attended-protocol-v2.json
python3 scripts/run_scientific_family_b_study.py register --directory <private-study-directory> --kind <calibration|dev|holdout> --protocol docs/galahad/evidence/family-b-attended-protocol-v2.json --budget /root/nerve-attended-budget --running-start-utc <provider-start> --prior-running-seconds 1160.783
python3 scripts/run_scientific_family_b_study.py run --directory <private-study-directory>
python3 scripts/run_scientific_family_b_study.py verify --directory <private-study-directory>
```

Registration supplies `--bank`, `--calibration`, `--prior` and the exact frozen candidate module only where required. Holdout is never called unless verified candidate development is eligible. Transfer uses `git archive`, `scp` and `tar`; private archives stay outside Git in a mode-0700 local directory. Commands with an actual execution approval requirement will be surfaced before waiting.

## Authorized replacement

Original pod start returned capacity error400 twice and fresh reads confirmed EXITED. The one permitted replacement is `97vr620wnmtuga`, A40 at $0.59/hour, started2026-10-16T06:27:28.749Z. Catalog stock was MEDIUM in EU-SE-1. Its account-injected SSH key did not match this laptop; only replacement pod configuration was amended with the local public key, preserving existing environment and keys. The automatic container restart changed directSSH to194.68.245.46:22159; cumulative time still starts at the original provider timestamp.

Protocol `evidence/family-b-attended-protocol-v3.json` pins this replacement. New `scientific_attended_replacement_transport.py` preserves the historical transport file and the exact Linux/loopback/model/runtime/decoder guards. Two focused tests passed for replacement isolation and the attended deadline. The previous window/source receipts remain unchanged historical records.

Actual bootstrap command, running without inference:

```sh
ssh -p 22159 -i /Users/aliyildirim/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes root@194.68.245.46 timeout 1800 bash /root/nerve-attended-bootstrap.sh
```

Its exact source is `scripts/bootstrap_attended_runpod.sh`; it pulls only the requested named model and rejects any digest mismatch. Runtime readiness is pending until its identity receipt is verified.
