"""Serializable two-sided CUSUM over bounded outcome telemetry (CPU only)."""
from dataclasses import dataclass, field
import math

@dataclass
class DriftMonitor:
    warmup: int = 30
    threshold: float = 8.0
    allowance: float = .05
    count: int = 0
    baseline: list = field(default_factory=lambda: [0., 0., 0.])
    positive: list = field(default_factory=lambda: [0., 0., 0.])
    negative: list = field(default_factory=lambda: [0., 0., 0.])

    def __post_init__(self):
        if self.warmup < 2 or not math.isfinite(self.threshold) or self.threshold <= 0 or not 0 <= self.allowance < 1:
            raise ValueError('invalid registered monitor configuration')

    def update(self, *, correct, discordance, abstention):
        values = [correct, discordance, abstention]
        if any(type(x) not in (int, float, bool) or not math.isfinite(x) or not 0 <= x <= 1 for x in values):
            raise ValueError('bounded outcome telemetry required')
        self.count += 1
        if self.count <= self.warmup:
            self.baseline = [a + (b-a)/self.count for a,b in zip(self.baseline,values)]
            return False
        self.positive = [max(0., a+b-c-self.allowance) for a,b,c in zip(self.positive,values,self.baseline)]
        self.negative = [max(0., a+c-b-self.allowance) for a,b,c in zip(self.negative,values,self.baseline)]
        detected = max(self.positive+self.negative) >= self.threshold
        if detected:
            # Relearn after a detected change; state is checkpointed with its receipt.
            self.count = 0
            self.baseline = [0.,0.,0.]
            self.positive = [0.,0.,0.]
            self.negative = [0.,0.,0.]
        return detected
