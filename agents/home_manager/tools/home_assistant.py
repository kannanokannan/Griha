"""Home Assistant Client — the only tool that touches HA's API."""
import logging, httpx
logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_states(self) -> list:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/api/states", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()

    async def get_entity_state(self, entity_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/api/states/{entity_id}", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()

    async def call_service(self, domain: str, service: str, data: dict) -> dict:
        logger.info(f"HA service call: {domain}.{service} | data={data}")
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/api/services/{domain}/{service}", headers=self.headers, json=data, timeout=15)
            r.raise_for_status()
            return r.json() if r.content else {"status": "ok"}

    async def get_config(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/api/config", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
