"""
Coordinator — the sole authority between all agents.
NATS message routing, node registry, egress gate, health monitoring.
No agent talks to another agent directly.
"""
import asyncio, json, logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import nats
from nats.aio.client import Client as NATS
from egress import EgressGate, RiskLevel

logger = logging.getLogger(__name__)

class NodeRegistry:
    def __init__(self, path: str = "/data/registry.json"):
        self.path = Path(path)
        self._nodes: Dict[str, dict] = self._load()

    def _load(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._nodes, indent=2, default=str))

    def register(self, manifest: dict) -> dict:
        node_id = manifest["node_id"]
        manifest["registered_at"] = datetime.utcnow().isoformat()
        manifest["status"] = "active"
        manifest["last_seen"] = datetime.utcnow().isoformat()
        self._nodes[node_id] = manifest
        self._save()
        return manifest

    def find_by_role(self, role: str) -> Optional[dict]:
        for node in self._nodes.values():
            if node.get("role") == role and node.get("status") == "active":
                return node
        return None

    def update_heartbeat(self, node_id: str):
        if node_id in self._nodes:
            self._nodes[node_id]["last_seen"] = datetime.utcnow().isoformat()
            self._save()

    def all_active(self) -> list:
        return [n for n in self._nodes.values() if n.get("status") == "active"]

    def assign_overlay_ip(self) -> str:
        used = {n.get("wireguard_ip") for n in self._nodes.values()}
        for i in range(2, 254):
            candidate = f"10.99.0.{i}"
            if candidate not in used:
                return candidate
        raise RuntimeError("Overlay IP pool exhausted")


class Coordinator:
    def __init__(self, nats_url: str = "nats://0.0.0.0:4222", registry_path: str = "/data/registry.json"):
        self.nats_url = nats_url
        self.registry = NodeRegistry(registry_path)
        self.egress = EgressGate()
        self._nc: Optional[NATS] = None

    async def start(self):
        self._nc = await nats.connect(self.nats_url)
        await self._nc.subscribe("node.register", cb=self._on_register)
        await self._nc.subscribe("node.health", cb=self._on_health)
        await self._nc.subscribe("intent.inbound", cb=self._on_intent)
        asyncio.create_task(self._health_loop())
        logger.info("Coordinator online.")

    async def _on_register(self, msg):
        try:
            manifest = json.loads(msg.data)
            if "wireguard_ip" not in manifest:
                manifest["wireguard_ip"] = self.registry.assign_overlay_ip()
            registered = self.registry.register(manifest)
            await msg.respond(json.dumps({"status": "registered", "wireguard_ip": registered["wireguard_ip"], "node_id": registered["node_id"]}).encode())
        except Exception as e:
            await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())

    async def _on_intent(self, msg):
        from core.intent import Intent
        try:
            intent = Intent.model_validate_json(msg.data)
            domain = intent.normalized_intent.domain
            action = intent.normalized_intent.action
            approved = await self.egress.evaluate(action, domain, {})
            if not approved:
                await msg.respond(json.dumps({"status": "blocked", "reason": "egress_gate_denied"}).encode())
                return
            node = self.registry.find_by_role(domain)
            if not node:
                await msg.respond(json.dumps({"status": "error", "reason": f"no_active_node_for_role:{domain}"}).encode())
                return
            updated_intent = intent.copy(update={"provenance": intent.provenance.propagate("coordinator")})
            response = await self._nc.request(f"intent.{domain}", updated_intent.model_dump_json().encode(), timeout=30)
            await msg.respond(response.data)
        except Exception as e:
            await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())

    async def _on_health(self, msg):
        payload = json.loads(msg.data)
        if node_id := payload.get("node_id"):
            self.registry.update_heartbeat(node_id)

    async def _health_loop(self):
        while True:
            await asyncio.sleep(30)
            for node in self.registry.all_active():
                try:
                    await self._nc.publish("node.health.ping", json.dumps({"from": "coordinator"}).encode())
                except Exception as e:
                    logger.warning(f"Health ping failed for {node['node_id']}: {e}")


async def main():
    import os
    logging.basicConfig(level=logging.INFO)
    coordinator = Coordinator(nats_url=os.getenv("NATS_URL", "nats://0.0.0.0:4222"), registry_path=os.getenv("NODE_REGISTRY_PATH", "/data/registry.json"))
    await coordinator.start()
    await asyncio.sleep(float("inf"))

if __name__ == "__main__":
    asyncio.run(main())
