"""
Home Manager Agent — HA bridge. Extract→Verify→Execute→Narrate pipeline.
Sole bridge between framework and Home Assistant. No other agent touches HA.
"""
import json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.agent import BaseAgent
from core.intent import Intent
from tools.home_assistant import HomeAssistantClient

logger = logging.getLogger(__name__)

EXTRACT_SYSTEM = """
You are a smart home controller. Given a user's natural language request, output JSON:
{"ha_domain": "<light|switch|climate|media_player|cover>", "ha_service": "<turn_on|turn_off|set_temperature|etc>", "entity_id": "<exact HA entity ID>", "service_data": {}}
Rules: entity_id must be exact HA entity ID. Output JSON only.
"""

class HomeManagerAgent(BaseAgent):
    role = "home_manager"

    def __init__(self, config: dict):
        super().__init__(config)
        self.ha = HomeAssistantClient(base_url=config["ha_base_url"], token=config["ha_token"])
        self._entity_registry: dict = {}

    async def start(self):
        await super().start()
        await self._refresh_entity_registry()
        logger.info(f"[{self.node_id}] Entity registry loaded: {len(self._entity_registry)} entities")

    async def _refresh_entity_registry(self):
        states = await self.ha.get_states()
        self._entity_registry = {s["entity_id"]: s for s in states}

    async def extract(self, intent: Intent) -> dict:
        return await self.llm.extract_json([{"role": "user", "content": intent.raw_input}], system=EXTRACT_SYSTEM)

    async def verify(self, payload: dict, intent: Intent) -> dict:
        entity_id = payload.get("entity_id")
        if not entity_id: return {"valid": False, "reason": "no_entity_id_in_payload"}
        if entity_id not in self._entity_registry:
            await self._refresh_entity_registry()
        if entity_id not in self._entity_registry:
            return {"valid": False, "reason": f"entity_not_found:{entity_id}", "hint": "LLM may have hallucinated this entity ID"}
        real_state = self._entity_registry[entity_id]
        payload["_verified_state"] = real_state.get("state")
        payload["_verified_attributes"] = real_state.get("attributes", {})
        return {"valid": True, "payload": payload}

    async def execute(self, payload: dict, intent: Intent) -> dict:
        intent.provenance.assert_trusted_for(f"ha.{payload['ha_domain']}.{payload['ha_service']}")
        result = await self.ha.call_service(domain=payload["ha_domain"], service=payload["ha_service"],
                                            data={"entity_id": payload["entity_id"], **payload.get("service_data", {})})
        return {"entity_id": payload["entity_id"], "action": f"{payload['ha_domain']}.{payload['ha_service']}", "ha_response": result, "prior_state": payload.get("_verified_state")}
