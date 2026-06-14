# CLAUDE.md - Griha Agent Briefing

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

- ContextOps - context governance
- ContextBoundary - egress control
- Sthala - narrate/compute split

Status: proof of concept. Apache 2.0.

---

## The Core Constraint

LLMs interpret intent only. Deterministic code owns all device execution. No exceptions.

---

## Key Files

- `core/intent.py` - LLM intent extraction (narrate layer only)
- `coordinator/main.py` - deterministic validation and routing (compute layer)
- `coordinator/egress.py` - egress control (ContextBoundary integration point)
- `core/provenance.py` - audit trail
- `adapters/` - device adapters, deterministic only
- `docs/architecture.md` - full architecture and failure narrative

---

## What Griha Is NOT

- Not a home automation platform
- Not an AI assistant
- Not production-ready - POC only
- Not a sibling of the three governance projects - it is the product layer above them

---

## Commit Style

Single-topic commits. Verify `git remote -v` shows Griha before every session.

---

## Google Drive Mirror

Canonical Drive folder: `1Rb2FzDxUg0N6hnns34R0KFt-Hf-aLYg4`

When files are created or modified, upload the updated file to this folder (mirroring the repo structure). Do NOT upload to any other Drive location.

---

*Griha - Apache 2.0 - Inherits: ContextOps - ContextBoundary - Sthala*

---

## Tracer Bullet Guidance

The dog-walker tracer bullet demonstrates Griha as a product/workflow proof-of-concept. Keep the public framing stable:

- LLMs extract structured intent only.
- Deterministic code validates state, risk, and policy.
- ContextBoundary-style checks gate high-risk actions by blast radius.
- Adapters execute only after deterministic approval conditions pass.
- Provenance records the request, decision, approval token, action, and outcome.

Do not describe Griha as a fourth governance pillar, a peer governance framework, a stack layer that owns execution, or the source of canonical Context Stack doctrine. Griha inherits ContextOps, ContextBoundary, and Sthala principles and demonstrates them in a concrete workflow.
