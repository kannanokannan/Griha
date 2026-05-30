# CLAUDE.md — Griha Agent Briefing

This file briefs any Claude agent working on the Griha project.
Read this before touching any file in this repo.

---

## Canonical Reference

Before introducing any new term: check https://github.com/kannanokannan/context-stack/blob/main/GLOSSARY.md

Before making any cross-project decision: check https://github.com/kannanokannan/context-stack/blob/main/DECISIONS.md

Terminology defined in GLOSSARY.md overrides any local usage in this repo.

---

## What Griha Is

Griha is the product layer above three sibling governance projects. It inherits:
- ContextOps — context governance
- ContextBoundary — egress control
- Sthala — narrate/compute split

Status: proof of concept. Apache 2.0.

---

## The Core Constraint

LLMs interpret intent only. Deterministic code owns all device execution. No exceptions.

---

## Key Files

- `core/intent.py` — LLM intent extraction (narrate layer only)
- `coordinator/main.py` — deterministic validation and routing (compute layer)
- `coordinator/egress.py` — egress control (ContextBoundary integration point)
- `core/provenance.py` — audit trail
- `adapters/` — device adapters, deterministic only
- `docs/architecture.md` — full architecture and failure narrative

---

## What Griha Is NOT

- Not a home automation platform
- Not an AI assistant
- Not production-ready — POC only
- Not a sibling of the three governance projects — it is the product layer above them

---

## Commit Style

Single-topic commits. Verify `git remote -v` shows Griha before every session.

---

*Griha · Apache 2.0 · Inherits: ContextOps · ContextBoundary · Sthala*

---

## Tracer Bullet — Hardened Build TODO

Derived from three independent adversarial reviews (ChatGPT, Perplexity, Gemini) that all converged on the same core finding: **gate on blast radius, not action name.**

Demo goal: "let the dog walker in" via Telegram → fires through all four layers → HITL approval → local execution.

### Core design change (the finding all three caught)

The original gate looked up `{action}` by name. That fails — an LLM can pick a benign-sounding action whose effect is critical (authority laundering / semantic smuggling). Classification must span three layers:

```
Policy(action)
  → Policy(transitive_logical_effects)      e.g. set_mode("guest") → disable_alarm → unlock
  → Policy(physical_topology)               e.g. smart plug powers the lock mechanism
  → Policy(state_transitions)               e.g. firmware reboot drops magnetic strike
```

Govern the capability graph / blast radius, not the API surface.

### Open design question — answer this first

Gemini's closing question: are action contracts a flat list of commands, or do they map the blast radius? **Answer this before writing the gate.** The whole hardened model depends on it being blast-radius-aware.

### Build checklist

**Layer mocks (`framework/` folder — NOT named after real projects)**
- [ ] `framework/context_ops.py` — load home state from local YAML (who's home, time, mode). State sets risk, not the LLM.
- [ ] `framework/context_boundary.py` — the gate. Resolves action → blast radius → most-critical reachable effect. Fires HITL.
- [ ] `framework/sthala.py` — enforce local-only LiteLLM, no cloud fallback.
- [ ] Wire through `coordinator/main.py`.

**Classification (the hardened core)**
- [ ] Closed whitelist of primitives, classified critical/non-critical at build time.
- [ ] LLM selects only from pre-verified safe IDs — cannot invent action names or pick between implementations.
- [ ] Action→effect map is canonical and NOT derived from LLM output.
- [ ] Map transitive effects: any action that reaches a critical primitive inherits critical.
- [ ] Map physical topology: device on same circuit / proximity as a critical device inherits critical.
- [ ] Classify state-altering commands (reboot, firmware update, config push) on a critical-domain device as critical.

**Approval token (bind everything)**
- [ ] Token binds: action + target + state_hash + nonce + expiry + approver.
- [ ] Cryptographically signed (key held only by approval service).
- [ ] Single-use: nonce store, atomically mark `used` before action.
- [ ] Short TTL for critical actions (30–60s).

**TOCTOU / state staleness**
- [ ] Recompute state_hash immediately before execution.
- [ ] If hash != token's hash → invalidate, require re-approval.

**HITL channel**
- [ ] Approval message shows exact capability: ACTION, TARGET, REQUESTOR, RISK, STATE, TIME.
- [ ] Include raw unedited user input alongside extracted intent (human verifies the extraction).
- [ ] Identity authenticated BEFORE intent extraction — never anonymous text → LLM.

**Fail-closed (explicit)**
- [ ] Every failure mode coded as explicit deny: network partition → deny, missing token → deny, stale state → deny, verification failure → deny.
- [ ] No "best effort" / "last known good" / "optimize for uptime" paths in critical domains.

**Provenance**
- [ ] Append-only, signed, hash-chained log.
- [ ] Log BEFORE execute (obtain log receipt, then actuate).
- [ ] Log: raw input, extracted intent, state snapshot+hash, risk+reason, gate decision+reason, token hash, actual executed action, outcome.

**After the build**
- [ ] `THREAT-MODEL.md` — assemble from the three review replies. This is the proof artifact.
- [ ] Boundary test: "absence of permission is denial" as an actual passing test (highest-signal cheap item per hiring-manager review).
- [ ] `CASE-STUDY.md` — dog-walker worked example: problem → why naive agents fail → how four layers handle it → tradeoffs.
- [ ] Then (only then): invite one external user.
