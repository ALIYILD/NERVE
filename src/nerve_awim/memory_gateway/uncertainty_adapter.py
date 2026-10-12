"""Authoritative uncertainty metadata for the existing verified memory gateway."""
from dataclasses import dataclass
from .contracts import MemoryRetrievalResult


@dataclass(frozen=True)
class UncertaintyMemoryResult(MemoryRetrievalResult):
    uncertainty: dict
    guidance_authority: bool = False
