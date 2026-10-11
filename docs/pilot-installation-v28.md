# Packaged pilot installation v2.8

This stage checks the distributable service in a clean virtual environment,
separate from the development checkout. It adds deterministic ZIP packaging,
per-file checksums, safe extraction and a hash-locked dependency set for CPython
3.12 on Linux x86_64 with glibc 2.34 or newer. It does not install a system service,
provision an identity provider or connect clinical/model traffic.

## Build and verify

From a reviewed checkout:

```bash
PYTHONPATH=src python scripts/pilot_bundle_v28.py build \
  --source . --destination /tmp/nerve-pilot.zip
PYTHONPATH=src python scripts/pilot_bundle_v28.py verify --source /tmp/nerve-pilot.zip
PYTHONPATH=src python scripts/pilot_bundle_v28.py unpack \
  --source /tmp/nerve-pilot.zip --destination /tmp/nerve-pilot
```

Destination archives/directories must not exist. The archive contains the Python
package source, explicitly selected operational scripts, service template, locked
dependencies and relevant documentation. Identity configuration, runtime
databases, Git history, test signing keys, wheels and virtual environments are
not included. Review source files before packaging; the builder does not scan
Python code for hardcoded secrets.

`PILOT-MANIFEST.json` records the base Git revision, whether the worktree was dirty,
and every packaged file's size and SHA-256. A dirty build is an inspectable local
artifact, not an exact committed release. For a release, require a clean checkout
and match its revision to the reviewed commit. Ignored/untracked Python files
under the source package can be included, so additionally review the manifest.
Checksums detect corruption, not a malicious publisher who replaces the manifest.
Use a trusted delivery channel and review the source revision independently.

Verification rejects traversal/absolute paths, duplicate members, symlinks,
encrypted entries, file/directory conflicts, unexpected manifest structure,
size-budget violations and checksum mismatches before creating the extraction
directory. Extract into a private staging parent controlled by the installer.
Installation is not an atomic replacement of a running application.

## Clean-environment installation drill

```bash
python3.12 -m venv /tmp/nerve-pilot-venv
/tmp/nerve-pilot-venv/bin/python -m pip install --require-hashes --only-binary=:all: \
  -r /tmp/nerve-pilot/deploy/requirements-pilot-linux-x86_64.lock
/tmp/nerve-pilot-venv/bin/python /tmp/nerve-pilot/scripts/verify_pilot_install_v28.py
```

The lock contains exact package versions and the tested Linux wheel hashes;
other Python versions, architectures and older glibc environments require a
separate reviewed lock. Wheels are downloaded from the configured Python package
index. The bundle itself is not a fully offline installer.

The drill creates temporary RSA signing keys and a temporary database. It starts
the extracted service on loopback, checks signed requests and unauthorised denial,
executes a repository task, checks shadow evidence, gracefully stops, runs startup
validation, backs up/restores into a new database and starts again. It verifies
that evidence and the baseline release survived recovery. Temporary state is
removed afterward. It does not contact an actual identity provider or activate a
learned candidate. Existing v2.6/v2.7 tests cover promoted bindings and rollback.

The installation workflow runs this check on GitHub Actions in a fresh venv and
uploads the bundle and smoke report only after success. No JWT/private test key or
runtime database is uploaded. Re-run the drill on the intended host before
installing the reviewed service template and provisioning actual identity
configuration. Systemd runtime isolation, TLS, persistent-volume ownership and
live IdP integration still need target-host verification.
