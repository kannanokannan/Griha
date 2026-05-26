# Griha — Home Framework v0.1.0

A privacy-first, multi-node smart home orchestration framework built on Raspberry Pis.

## Architecture

```
Adapter → Coordinator → Agent(s)
          (NATS bus)
```

- **Core** — Intent schema, DataProvenance trust tagging, BaseAgent pipeline (Extract → Verify → Execute → Narrate)
- **Coordinator** — NATS message router, NodeRegistry, EgressGate (graduated risk: LOW/MEDIUM/HIGH)
- **Node Wizard** — Hardware scanner, USB detection, role eligibility matrix; provisions WireGuard + mTLS
- **Adapters** — BaseAdapter contract + REST adapter (FastAPI)
- **Agents** — `home_manager`: sole HA bridge; entity verify prevents LLM hallucination acting on real devices

## Security

- Provenance tagging: untrusted data (camera, mic, sensors, Alexa) cannot trigger physical actions
- Locks and alarms are **hardcoded HIGH RISK** — always require explicit human approval (EU AI Act)
- NATS overlay on WireGuard; no agent talks to another agent directly

## Quick Start

```bash
pip install -r requirements.txt
docker-compose up -d nats coordinator
```

## Sibling Projects

Part of the **ContextOps** ecosystem. Sibling to [Sthala](https://github.com/kannanokannan/Sthala).
