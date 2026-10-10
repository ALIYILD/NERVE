"""Compare serial and parallel NERVE research subagent execution.

Wall times are informational: threads do not guarantee speedups for Python
CPU-bound code. Research review results should be identical.
"""
import json
import tempfile
from pathlib import Path
from time import perf_counter

from nerve_awim.autoresearch_v04 import Proposal
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.evolution_cycle_v11 import ParallelEvolutionCycle


def benchmark():
    with tempfile.TemporaryDirectory() as folder:
        memory = EvolutionMemory(Path(folder) / "memory.sqlite")
        memory.record("lab", "WorldCore", "long-outage", .9)
        candidates = [
            Proposal("short-outage", 3, .25),
            Proposal("long-outage", 8, .25),
            Proposal("high-risk", 5, .6),
        ]
        observations = {}
        for name, workers in (("serial", 1), ("parallel", 4)):
            started = perf_counter()
            result = ParallelEvolutionCycle(
                memory=memory, agent_id="lab", max_workers=workers
            ).run(candidates, context="WorldCore")
            observations[name] = {
                "wall_seconds": round(perf_counter() - started, 6),
                "status": result["status"],
                "selected": result["selected"],
                "rejected": sum(row["decision"] == "reject"
                                for row in result["trials"]),
            }
        matches = (observations["serial"]["status"] ==
                   observations["parallel"]["status"] and
                   observations["serial"]["selected"] ==
                   observations["parallel"]["selected"] and
                   observations["serial"]["rejected"] ==
                   observations["parallel"]["rejected"])
        return {
            "serial": observations["serial"],
            "parallel": observations["parallel"],
            "decisions_match": matches,
            "note": "No demonstrated acceleration; threads share one Python process.",
        }


if __name__ == "__main__":
    result = benchmark()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["decisions_match"]:
        raise SystemExit(1)
