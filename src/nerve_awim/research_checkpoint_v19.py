"""Bounded, versioned research data. Checksums detect damage, not forgery.

Fitness, holdout results and permissions are never checkpoint inputs. The
host must trust the checkpoint source; recipes are re-evaluated each run.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from .recursive_evolution_v19 import RetrievalGenome

PROTOCOL = "nerve-recursive-data-only-v19"
MAX_BYTES = 250_000
MAX_COUNTER = 2**53 - 1


def evaluator_fingerprint():
    """Invalidate archive exclusions when evaluator/search/ledger code changes."""
    root = Path(__file__).parent
    digest = sha256(b"nerve-retrieval-checkpoint-v1\0")
    for name in ("recursive_evolution_v19.py", "memory_v18.py"):
        digest.update(name.encode() + b"\0" + (root / name).read_bytes())
    return digest.hexdigest()


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _genome(value):
    if type(value) is not dict or set(value) != {"token_weight", "trigram_weight"}:
        raise ValueError("unexpected checkpoint genome fields")
    return RetrievalGenome(**value)


def _counter(value):
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise ValueError("invalid checkpoint counter")
    return value


@dataclass(frozen=True)
class ResearchCheckpoint:
    selected: RetrievalGenome = RetrievalGenome()
    population: tuple = ()
    completed_runs: int = 0
    cumulative_candidates: int = 0
    reset_reason: str | None = None


def load_checkpoint(path):
    if path is None or not Path(path).exists():
        return ResearchCheckpoint()
    # Bound the actual read as well as the stat (including concurrent growth).
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("untrusted research checkpoint oversized")
    data = json.loads(raw)
    if type(data) is not dict:
        raise ValueError("invalid checkpoint")
    if "checkpoint" in data:
        if set(data) != {"checkpoint", "sha256"}:
            raise ValueError("unexpected checkpoint envelope fields")
        payload = data["checkpoint"]
        if sha256(_json_bytes(payload)).hexdigest() != data["sha256"]:
            raise ValueError("checkpoint checksum mismatch")
        data = payload
        fields = {"checkpoint_schema", "study_protocol", "evaluator_fingerprint",
                  "selected", "population_archive", "completed_runs",
                  "cumulative_candidates"}
        if (type(data) is not dict or set(data) != fields
                or type(data["checkpoint_schema"]) is not int
                or data["checkpoint_schema"] != 1):
            raise ValueError("unsupported checkpoint schema")
    # Legacy reports can migrate, but unversioned exclusion archives cannot.
    if data.get("study_protocol") != PROTOCOL:
        raise ValueError("invalid checkpoint protocol")
    selected = _genome(data.get("selected"))
    archive = data.get("population_archive")
    if type(archive) is not list or not 1 <= len(archive) <= 35:
        raise ValueError("invalid checkpoint archive")
    population = tuple(_genome(item) for item in archive)
    if len(set(population)) != len(population) or selected not in population:
        raise ValueError("invalid checkpoint population membership")
    runs = _counter(data.get("completed_runs", 0))
    candidates = _counter(data.get("cumulative_candidates", 0))
    fingerprint = data.get("evaluator_fingerprint")
    if fingerprint != evaluator_fingerprint():
        return ResearchCheckpoint(reset_reason=(
            "legacy_unversioned" if fingerprint is None else "evaluator_changed"))
    return ResearchCheckpoint(selected, population, runs, candidates)


def write_checkpoint(path, report):
    """Publish only typed recipe state after the entire experiment succeeds."""
    fields = ("study_protocol", "evaluator_fingerprint", "selected",
              "population_archive", "completed_runs", "cumulative_candidates")
    payload = {key: report[key] for key in fields}
    payload["checkpoint_schema"] = 1
    encoded = _json_bytes({"checkpoint": payload,
                           "sha256": sha256(_json_bytes(payload)).hexdigest()})
    if len(encoded) > MAX_BYTES:
        raise ValueError("checkpoint oversized")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(encoded + b"\n")
            f.flush()
            os.fsync(f.fileno())
        # Validate our own output before replacing the last good state.
        load_checkpoint(temporary)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
