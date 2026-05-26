"""
Intent — the normalized object every adapter produces and every agent consumes.
Nothing enters the framework without being cast into this schema first.
"""
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid


class TrustLevel(str, Enum):
    INTERNAL = "internal"   # Local Pi adapter — full action set
    EXTERNAL = "external"   # Alexa, cloud adapter — restricted action set


class Urgency(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class DataProvenance(BaseModel):
    """
    Tracks the trust lineage of data through the pipeline.
    Once untrusted, always untrusted — cannot be upgraded mid-chain.
    Defends against prompt injection via sensor/external data.
    """
    trust: str                          # "trusted" | "untrusted"
    source: str                         # Origin (telegram, sensor, camera, etc.)
    chain: List[str] = Field(default_factory=list)  # Audit trail of agent hops

    @property
    def is_trusted(self) -> bool:
        return self.trust == "trusted"

    def propagate(self, next_agent: str) -> "DataProvenance":
        """Provenance is inherited and cannot be upgraded downstream."""
        return DataProvenance(
            trust=self.trust,
            source=self.source,
            chain=self.chain + [next_agent]
        )


class NormalizedIntent(BaseModel):
    action: str
    domain: Optional[str] = None        # Target agent role e.g. "home_manager"
    context: Dict[str, Any] = Field(default_factory=dict)
    urgency: Urgency = Urgency.LOW


class Intent(BaseModel):
    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    trust_level: TrustLevel
    user_id: str
    raw_input: str
    normalized_intent: NormalizedIntent
    provenance: DataProvenance
    timestamp: datetime = Field(default_factory=datetime.utcnow)
