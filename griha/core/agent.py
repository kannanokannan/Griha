"""
BaseAgent — abstract class every domain agent inherits.

Pipeline enforced per agent:
  Extract → Verify ₒ Execute → Narrate

LLMs handle Extract and Narrate only.
Verify and Execute are code-only — never LLM-triggered directly.
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

import nats
from nats.aio.client import Client as NATS

from .intent import Intent
from .provenance import Provenance
from .llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)


class BaseAgent(ABC):

    role: str = "base"
    version: str = "0.1.0"

    def __init__(self, config: dict):
        self.node_id     = config["node_id"]
        self.nats_url    = config.get("nats_url", "nats://10.99.0.1:4222")
        self.llm         = LLMAdapter.from_profile(config.get("llm", {}))
        self.allowed_actions = config.get("allowed_actions", [])
        self._nc: Optional[NATS] = None

    async def start(self):
        self._nc = await nats.connect(self.nats_url)
        await self._nc.subscribe(f"intent.{self.role}", cb=self._dispatch)
        await self._nc.subscribe("node.health.ping", cb=self._health_pong)
        logger.info(f"[{self.node_id}] Agent '{self.role}' online.")

    async def stop(self):
        if self._nc:
            await self._nc.drain()

    async def _dispatch(self, msg):
        try:
            intent = Intent.model_validate_json(msg.data)
            if not intent.provenance.is_trusted:
                result = await self._handle_untrusted(intent)
            else:
                result = await self._run_pipeline(intent)
            await msg.respond(json.dumps(result).encode())
        except Exception as e:
            logger.error(f"[{self.node_id}] Dispatch error: {e}")
            await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())

    async def _run_pipeline(self, intent: Intent) -> dict:
        extracted = await self.extract(intent)
        verified = await self.verify(extracted, intent)
        if not verified["valid"]:
            return {"status": "rejected", "reason": verified.get("reason", "verification_failed")}
        result = await self.execute(verified["payload"], intent)
        narration = await self.narrate(result, intent)
        return {"status": "ok", "result": result, "narration": narration}

    @abstractmethod
    async def extract(self, intent: Intent) -> dict:
        pass

    @abstractmethod
    async def verify(self, payload: dict, intent: Intent) -> dict:
        pass

    @abstractmethod
    async def execute(self, payload: dict, intent: Intent) -> dict:
        pass

    async def narrate(self, result: dict, intent: Intent) -> str:
        messages = [{"role": "user", "content": (
            f"The user requested: {intent.raw_input}\n"
            f"Result: {json.dumps(result)}\n"
            f"Write a brief, natural confirmation of what was done."
        )}]
        return await self.llm.complete(messages)

    async def _handle_untrusted(self, intent: Intent) -> dict:
        narration = await self.llm.complete([{"role": "user", "content": (
            f"Respond to this query but note you cannot take physical actions "
            f"because the input source is untrusted: {intent.raw_input}"
        )}])
        return {"status": "untrusted_narration_only", "narration": narration, "provenance_chain": intent.provenance.chain}

    async def _health_pong(self, msg):
        await msg.respond(json.dumps({"node_id": self.node_id, "role": self.role, "status": "active", "version": self.version}).encode())
