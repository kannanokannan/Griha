# Griha — Architecture

## What Griha Is

Griha is a policy-bounded AI execution system for home and edge environments. It is the product layer that inherits three open-source governance principles:

| Principle | Source | What it gives Griha |
|-----------|--------|-------------------|
| Context governance | [ContextOps](https://github.com/kannanokannan/ContextOps) | How intent is captured, validated, and supplied to the execution pipeline |
| Egress control | [ContextBoundary](https://github.com/kannanokannan/ContextBoundary) | Where data from home devices is permitted to flow and under what conditions |
| Narrate/compute split | [Sthala](https://github.com/kannanokannan/Sthala) | LLMs interpret intent only — deterministic code owns all device execution |

---

## The Core Constraint

> Probabilistic intelligence must operate inside deterministic governance boundaries.

In Griha this means: the LLM never directly actuates a device. Ever.

---

## Failure Mode Griha Prevents

**Without Griha (typical home AI stack):**
1. User says something ambiguous
2. LLM interprets and executes directly
3. Device actuates — door unlocks, HVAC changes, security system responds
4. No validation, no audit, no reversibility
5. Physical side effect occurs from probabilistic interpretation

**With Griha:**
1. User intent captured and extracted by LLM (narrate only)
2. Intent passed to deterministic validation layer
3. Risk engine classifies action against policy
4. Critical domains (locks, security, access) require explicit approval gate
5. Only after policy clears: deterministic code actuates the device
6. Every action logged with provenance

---

## Architecture

```
User Input
    ↓
[LLM — Intent Extraction]        ← narrate only, no execution
    ↓
[Coordinator — Validation]       ← deterministic, policy-checked
    ↓
[Risk Classification]            ← low / medium / high / blocked
    ↓
[Approval Gate]                  ← human-in-loop for critical domains
    ↓
[Adapter — Device Execution]     ← deterministic code only
    ↓
[Egress — ContextBoundary]       ← data flow governed by tier
```

**Key files:**
- `core/intent.py` — LLM intent extraction (narrate layer)
- `coordinator/main.py` — deterministic validation and routing (compute layer)
- `coordinator/egress.py` — egress control (ContextBoundary integration point)
- `core/provenance.py` — audit trail for every action
- `adapters/` — device adapters, deterministic only

---

## What Griha Is Not

- Not a home automation platform
- Not an AI assistant
- Not a cloud product — designed for local deployment
- Not production-ready — proof of concept

---

## Status

Proof of concept. Core pipeline functional. Docs in progress.

Governance principles inherited from the [kannanokannan](https://github.com/kannanokannan) open-source stack. Apache 2.0.
