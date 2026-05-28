# Griha

**The only local AI for Home Assistant that won't accidentally unlock your front door.**

Most "local AI" smart home setups hand an LLM direct access to your devices and hope for the best. Griha doesn't. The LLM extracts intent. Python verifies it. Code executes it. Always.

No hallucination reaches a physical actuator. Ever.

---

## Why This Exists

Every current local AI + Home Assistant setup has the same flaw: the LLM calls the API directly. That means a misread prompt, a bad day for your model, or a crafted sensor payload can turn on your heater, unlock your door, or trigger your alarm.

Griha separates the two jobs that should never be merged:

- **LLM** — understands what you want
- **Python** — decides if it's safe to do it

---

## How It Works

```
You say something
      ↓
LLM extracts structured intent (what, where, trust level)
      ↓
Python verifies against real device state (not what the LLM thinks the state is)
      ↓
Egress gate checks risk level
      ↓
      ├── Low risk   → executes automatically
      ├── Medium risk → notifies you, 30s to cancel
      └── High risk  → waits for explicit approval
      ↓
Home Assistant executes
```

Locks and alarms are hardcoded as human-approval only. No prompt can override that.

---

## Architecture

Griha runs as a swarm of specialised Raspberry Pi nodes — each Pi owns one domain.

```
[ Telegram / REST ]        Interface adapters
        ↓
[ Coordinator (NATS) ]     Routing · Egress gate · Node registry
        ↓
[ Agent Nodes ]            One Pi per domain (home, planner, security...)
        ↓
[ Home Assistant ]         Sole IoT bridge — single integration surface
        ↓
[ Your Devices ]           WiFi / Zigbee / Z-Wave / Matter
```

**Network:** WireGuard overlay on wired Ethernet. Wireless reserved for IoT devices only. Nodes authenticate with mTLS.

---

## What's Built (v0.1.0)

- Intent schema with data provenance — every object in the pipeline is tagged with its origin and trust level
- Base agent pipeline — Extract → Verify → Execute → Narrate
- NATS coordinator with graduated egress gate
- Node onboarding wizard — scans hardware, assigns roles, provisions WireGuard
- Home Manager agent — Home Assistant bridge with illusion-proof entity verification
- Pluggable adapter contract — add Alexa, voice, or any interface without touching core

---

## Hardware

Designed for **Raspberry Pi 5 (8GB)**. Each node runs one agent recipe.

Recommended inference: BitNet B1.58 2B or Qwen 2.5 3B via Ollama.

Single-node mode (coordinator + agent on one Pi) works for getting started.

---

## Status

| Version | Focus | Status |
|---|---|---|
| v0.1.0 | Foundation — pipeline, egress gate, node wizard | ✅ Done |
| v0.2 | Security — WireGuard provisioning, mTLS CA, Telegram adapter | 🔨 Next |
| v0.3 | Planner agent, Google Calendar, cross-agent data passing | Planned |
| v0.4 | Web UI for wizard, one-shot install scripts, health dashboard | Planned |
| v0.5 | Grocery agent, security agent, voice adapter stub | Planned |

---

## Stack

Python · NATS · LiteLLM · Pydantic · FastAPI · Home Assistant · WireGuard · Docker

---

> **Note:** Griha is the first working prototype of a broader set of ideas — a pipeline discipline where LLMs narrate and code executes, an egress contract that governs what leaves a trust boundary, and a governance layer that sits above it all. These concepts are being formalised into a wider ecosystem (ContextBoundary, ContextOps) for enterprise and SMB contexts. Griha is where they were proven to work on $80 hardware.
