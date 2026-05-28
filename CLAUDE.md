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
