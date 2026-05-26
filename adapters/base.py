"""BaseAdapter — contract every interface adapter must implement."""
import logging, uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import nats
from core.intent import Intent, TrustLevel, DataProvenance, NormalizedIntent, Urgency

logger = logging.getLogger(__name__)

class BaseAdapter(ABC):
    TRUST_LEVEL: TrustLevel = TrustLevel.INTERNAL
    SOURCE_NAME: str = "unknown"

    def __init__(self, coordinator_nats_url: str = "nats://10.99.0.1:4222"):
        self.coordinator_url = coordinator_nats_url
        self._nc = None

    async def connect(self):
        self._nc = await nats.connect(self.coordinator_url)
        logger.info(f"Adapter '{self.SOURCE_NAME}' connected.")

    @abstractmethod
    async def start(self): pass

    @abstractmethod
    async def stop(self): pass

    async def submit_intent(self, intent: Intent) -> dict:
        if not self._nc: raise RuntimeError("Not connected.")
        import json
        response = await self._nc.request("intent.inbound", intent.model_dump_json().encode(), timeout=30)
        return json.loads(response.data)

    def build_intent(self, raw_input: str, user_id: str, action: str, domain: Optional[str] = None, context: Optional[dict] = None, urgency: Urgency = Urgency.LOW) -> Intent:
        trust = "trusted" if self.TRUST_LEVEL == TrustLevel.INTERNAL else "untrusted"
        return Intent(intent_id=str(uuid.uuid4()), source=self.SOURCE_NAME, trust_level=self.TRUST_LEVEL, user_id=user_id, raw_input=raw_input,
                      normalized_intent=NormalizedIntent(action=action, domain=domain, context=context or {}, urgency=urgency),
                      provenance=DataProvenance(trust=trust, source=self.SOURCE_NAME, chain=[self.SOURCE_NAME]),
                      timestamp=datetime.utcnow())

    @abstractmethod
    async def send_notification(self, message: str): pass

    async def request_approval(self, action: str) -> bool:
        await self.send_notification(f"🔴 Approval required: {action}\nReply APPROVE to confirm.")
        logger.warning(f"Approval requested for '{action}' — falling back to deny.")
        return False
