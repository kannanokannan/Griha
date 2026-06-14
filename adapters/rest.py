"""REST Adapter — HTTP interface. Foundation adapter. POST /intent, GET /health, GET /status."""
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn
from adapters.base import BaseAdapter
from core.intent import TrustLevel, Urgency

logger = logging.getLogger(__name__)

class RESTAdapter(BaseAdapter):
    TRUST_LEVEL = TrustLevel.INTERNAL
    SOURCE_NAME = "rest_local"

    def __init__(self, coordinator_nats_url: str = "nats://10.99.0.1:4222", host: str = "0.0.0.0", port: int = 8080, api_key: Optional[str] = None):
        super().__init__(coordinator_nats_url)
        self.host = host
        self.port = port
        self.api_key = api_key
        self.app = FastAPI(title="Home Framework REST Adapter", version="0.1.0")
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.middleware("http")
        async def auth(request: Request, call_next):
            if self.api_key and request.headers.get("X-API-Key") != self.api_key:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

        @app.get("/health")
        async def health(): return {"status": "ok", "adapter": self.SOURCE_NAME}

        @app.post("/intent")
        async def submit(request: Request):
            body = await request.json()
            intent = self.build_intent(raw_input=body.get("input",""), user_id=body.get("user_id","rest_user"),
                                       action=body.get("action","query"), domain=body.get("domain"),
                                       context=body.get("context",{}), urgency=Urgency(body.get("urgency","low")))
            try: return JSONResponse(await self.submit_intent(intent))
            except Exception as e: raise HTTPException(status_code=500, detail=str(e))

        @app.get("/status")
        async def status(): return {"status": "ok", "nodes": []}  # Coordinator registry integration is deferred.

    async def start(self):
        await self.connect()
        server = uvicorn.Server(uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info"))
        await server.serve()

    async def stop(self):
        if self._nc: await self._nc.drain()

    async def send_notification(self, message: str):
        logger.info(f"[REST — fallback log]: {message}")


app = RESTAdapter().app
