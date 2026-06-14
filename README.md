# Griha

**A governed Home Assistant proof-of-concept that won't accidentally unlock your front door.**

Most AI-assisted smart home setups hand an LLM direct access to your devices and hope for the best. Griha doesn't. The LLM extracts intent. Deterministic Python verifies policy and state. Adapters execute approved actions. Always.

No hallucination reaches a physical actuator. Ever.

## The Problem

Modern AI systems let interpretation, decision-making, and execution share one trust boundary. That lets probabilistic systems directly own deterministic consequences — the root cause of prompt injection, unsafe automation, context contamination, and authority confusion.

This project is part of the context-stack, which separates interpretation from authority: intelligence proposes, governance validates, execution authorizes. Intelligence can suggest anything. Authority stays deterministic.

Full doctrine: https://github.com/kannanokannan/context-stack

---

## Why This Exists

Every AI-assisted Home Assistant setup has the same core failure mode when left ungoverned: the LLM can call the API directly. That means a misread prompt, a bad day for your model, or a crafted sensor payload can turn on your heater, unlock your door, or trigger your alarm.

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

Proof of concept. The current repo demonstrates the foundation: pipeline, egress gate, node wizard, Home Assistant bridge, and blast-radius-aware approval flow.

---

## Stack

Python · NATS · LiteLLM · Pydantic · FastAPI · Home Assistant · WireGuard · Docker

---

> **Note:** Griha is a product/workflow proof-of-concept for Context Stack principles: ContextOps context lifecycle, ContextBoundary egress control, and Sthala's narrate/compute split. It demonstrates deterministic boundaries in a concrete home workflow; canonical stack doctrine lives in the Context Stack repos.
