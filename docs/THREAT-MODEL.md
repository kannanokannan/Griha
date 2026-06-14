# Griha — Threat Model

Derived from three independent adversarial reviews (ChatGPT, Perplexity, Gemini) of the tracer bullet algorithm. All three converged on the same primary finding.

---

## Core Finding (all three reviewers)

> The original gate checked action names. That fails.

An LLM can pick a benign-sounding action whose *transitive effect* is critical. The fix:

```
Policy(action)
  → Policy(transitive_logical_effects)   e.g. set_mode("guest") → disable_alarm → unlock
  → Policy(physical_topology)            e.g. smart plug powers the lock mechanism
  → Policy(state_transitions)            e.g. firmware reboot drops magnetic strike
```

**Govern the capability graph / blast radius, not the API surface.**

---

## Attack Classes

### Class 1 — Semantic Smuggling (Highest Risk)
User: *"Disable the alarm so I can enter."*
LLM emits: `{action: "set_mode", target: "welcome"}`
`set_mode` is classified non-critical. Internally: `mode=welcome → disable_alarm → unlock`.
Gate never fires. House opens.

**Fix:** `ACTION_REGISTRY` classifies `set_mode` as CRITICAL because its transitive effects touch `access_control` and `physical_security`.

---

### Class 2 — Capability Equivalence
`unlock_front_door` requires approval. `open_garage` does not. Garage → house access is functionally equivalent.

**Fix:** Both classified CRITICAL in `ACTION_REGISTRY`. Classification is by security outcome, not device category.

---

### Class 3 — TOCTOU (Time-of-Check to Time-of-Use)
State at approval time: child not home. State at execution time: child arrives. Approval was for the wrong context.

**Fix:** Approval token binds `state_hash`. `scripts/tracer_bullet.py` Step 4 recomputes state hash immediately before execution. Hash mismatch → token invalid → deny.

---

### Class 4 — Approval Substitution
Token contains only `approved=true`. Attacker replays token for a different action.

**Fix:** Token binds `action + target + state_hash + nonce + expiry + approver`. All fields inside HMAC signature.

---

### Class 5 — Token Replay
Valid token captured and replayed later.

**Fix:** Single-use nonce store (`_used_nonces` set). `_mark_nonce_used()` atomically checks and marks before execution. Second use returns False.

---

### Class 6 — HITL UI Attack
Approval message shows "Approve action?" with a YES button. Human approves without knowing what they approved.

**Fix:** CLI HITL (and future Telegram HITL) shows: ACTION, TARGET, REQUESTOR, RISK, STATE, STATE_HASH, and the raw unedited user input. Human verifies the extraction matched the original request.

---

### Class 7 — Identity Drift
Telegram account compromised. Wrong human initiates the request. LLM extracts correctly. System executes correctly. Wrong person is the approver.

**Fix:** Identity authenticated before LLM sees any input. `requestor` field is set by the adapter layer (authenticated channel), not extracted from user text.

---

### Class 8 — Partition / TTL
Approval issued. Network partition. Token still valid hours later when partition heals.

**Fix:** Critical approval TTL = 60 seconds (`GRIHA_TOKEN_TTL` env var). Expired tokens fail `is_valid()`.

---

### Class 9 — Log Integrity
Execute succeeds. Log write fails. Action is unlogged.

**Fix (design, not yet implemented):** Log before execute. Obtain log receipt. Then actuate. Append-only, hash-chained log. v0.2 item.

---

### Class 10 — Physical Topology (Gemini — unique finding)
Smart plug classified non-critical. Smart plug powers the magnetic lock mechanism. `toggle_smart_plug` skips the gate. Lock disengages.

**Fix:** `toggle_smart_plug` classified CRITICAL in `ACTION_REGISTRY` — physical topology means any device that can affect a critical domain inherits critical classification.

---

### Class 11 — Firmware / State Transitions (Gemini — unique finding)
`update_firmware` on a door lock classified as IT task (non-critical). Lock reboots. Magnetic strike drops during reboot (fire-safety default). Door opens physically.

**Fix:** All state-altering commands (reboot, firmware update, config push) on critical-domain devices classified CRITICAL.

---

## Invariants Implemented

| Invariant | Where enforced |
|-----------|---------------|
| Closed action whitelist | `ACTION_REGISTRY` in `context_boundary.py` |
| Blast-radius classification | `ACTION_REGISTRY` — transitive effects + physical topology |
| State sets risk, not LLM | `HomeState.risk_level()` in `context_ops.py` |
| Non-critical escalates in HIGH-risk state | `evaluate()` in `context_boundary.py` |
| Token binds action+target+state_hash+nonce+expiry | `ApprovalToken` + `_sign_token()` |
| Single-use nonce | `_mark_nonce_used()` — atomic check-and-mark |
| TOCTOU check before execution | `tracer_bullet.py` Step 4 — recompute hash |
| HITL shows raw input + full context | `cli_hitl()` in `tracer_bullet.py` |
| Local inference only | `_assert_local_model()` in `sthala.py` |
| Narrate/compute split | `_assert_allowed_operation()` in `sthala.py` |
| All failure modes deny | Every except/None path in `evaluate()` returns `allowed=False` |

---

## Known Gaps

- `_used_nonces` is in-process memory — does not survive restarts or scale across processes. Redis/DB-backed nonce store needed for production.
- Log-before-execute not yet implemented — execution can succeed before log write.
- Telegram HITL channel authentication not yet implemented — CLI HITL is for demo only.
- NATS registration in node-wizard is a stub.

---

## Test Coverage

`tests/test_boundary.py` — 8 passing deterministic tests covering:
- Absence of permission is denial (canonical test)
- Critical action denied without HITL
- Critical action denied on HITL rejection
- Critical action allowed on HITL approval with token
- Non-critical auto-allowed in LOW-risk state
- Non-critical escalated in HIGH-risk state
- Token replay denied
- Token invalid on state change (TOCTOU)
