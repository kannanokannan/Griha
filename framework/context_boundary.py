"""
framework/context_boundary.py — Egress gate (ContextBoundary layer mock)

Implements the hardened boundary gate from the Griha tracer bullet spec.
Gates on blast radius (transitive effects + physical topology), not action name.

Three adversarial reviews (ChatGPT, Perplexity, Gemini) converged on this design.
See docs/THREAT-MODEL.md for the full attack surface analysis.

Part of the Griha tracer bullet: context_ops → context_boundary → sthala → coordinator
"""
import hashlib
import hmac
import os
import secrets
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from framework.context_ops import HomeState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical action registry — closed whitelist, classified at definition time.
# LLM selects from these IDs only. It cannot invent names.
# Classification is by BLAST RADIUS (transitive effects + physical topology),
# not by action name. See: docs/THREAT-MODEL.md Class 1 / Class 2.
# ---------------------------------------------------------------------------

CRITICAL = "CRITICAL"
NON_CRITICAL = "NON_CRITICAL"

ACTION_REGISTRY = {
    # Access domain — always critical (irreversible physical side effects)
    "unlock_front_door":    {"risk": CRITICAL,     "affects": ["access_control", "physical_security"]},
    "unlock_back_door":     {"risk": CRITICAL,     "affects": ["access_control", "physical_security"]},
    "unlock_garage":        {"risk": CRITICAL,     "affects": ["access_control", "physical_security"]},
    "open_garage":          {"risk": CRITICAL,     "affects": ["access_control", "physical_security"]},  # capability equivalence
    "disable_alarm":        {"risk": CRITICAL,     "affects": ["physical_security"]},
    "arm_alarm":            {"risk": CRITICAL,     "affects": ["physical_security"]},

    # Mode changes — critical if they transitively affect access or security
    # set_mode("guest") → disable_alarm → unlock. Gate on transitive effect.
    "set_mode":             {"risk": CRITICAL,     "affects": ["access_control", "alarm", "physical_security"]},

    # Device state — critical if device is in physical_security topology
    # smart plug may power lock mechanism (physical topology, Gemini Class 1)
    "toggle_smart_plug":    {"risk": CRITICAL,     "affects": ["physical_topology"]},

    # State-altering commands on critical-domain devices (Gemini Class 5)
    "reboot_device":        {"risk": CRITICAL,     "affects": ["physical_security", "state_transition"]},
    "update_firmware":      {"risk": CRITICAL,     "affects": ["physical_security", "state_transition"]},
    "push_config":          {"risk": CRITICAL,     "affects": ["physical_security", "state_transition"]},

    # Non-critical — no irreversible physical side effects
    "set_temperature":      {"risk": NON_CRITICAL, "affects": ["hvac"]},
    "turn_on_lights":       {"risk": NON_CRITICAL, "affects": ["lighting"]},
    "turn_off_lights":      {"risk": NON_CRITICAL, "affects": ["lighting"]},
    "set_brightness":       {"risk": NON_CRITICAL, "affects": ["lighting"]},
    "play_music":           {"risk": NON_CRITICAL, "affects": ["media"]},
    "stop_music":           {"risk": NON_CRITICAL, "affects": ["media"]},
    "check_status":         {"risk": NON_CRITICAL, "affects": ["query"]},
    "notify_user":          {"risk": NON_CRITICAL, "affects": ["notification"]},
}

# ---------------------------------------------------------------------------
# Nonce store — single-use token enforcement
# ---------------------------------------------------------------------------

_used_nonces: set[str] = set()


def _mark_nonce_used(nonce: str) -> bool:
    """Atomically check and mark nonce used. Returns True if first use."""
    if nonce in _used_nonces:
        return False
    _used_nonces.add(nonce)
    return True


# ---------------------------------------------------------------------------
# Approval token
# ---------------------------------------------------------------------------

TOKEN_SECRET = os.environ.get("GRIHA_TOKEN_SECRET", secrets.token_hex(32))
CRITICAL_TTL_SECONDS = int(os.environ.get("GRIHA_TOKEN_TTL", "60"))


@dataclass
class ApprovalToken:
    action: str
    target: str
    state_hash: str
    nonce: str
    issued_at: float
    expiry: float
    approver: str
    signature: str = field(default="", repr=False)

    def is_valid(self, current_state_hash: str) -> tuple[bool, str]:
        """
        Validate token. Returns (valid, reason).
        All failure modes return False — fail-closed.
        """
        now = time.time()

        # Expired
        if now > self.expiry:
            return False, "token expired"

        # State changed since approval (TOCTOU fix)
        if self.state_hash != current_state_hash:
            return False, f"state changed since approval (was {self.state_hash}, now {current_state_hash})"

        # Single-use nonce
        if not _mark_nonce_used(self.nonce):
            return False, "token already used (replay attempt)"

        # Signature
        expected = _sign_token(self)
        if not hmac.compare_digest(self.signature, expected):
            return False, "invalid signature"

        return True, "ok"


def _sign_token(token: ApprovalToken) -> str:
    payload = f"{token.action}|{token.target}|{token.state_hash}|{token.nonce}|{token.issued_at}|{token.expiry}|{token.approver}"
    return hmac.new(TOKEN_SECRET.encode(), payload.encode(), "sha256").hexdigest()


def issue_token(action: str, target: str, state_hash: str, approver: str) -> ApprovalToken:
    now = time.time()
    nonce = secrets.token_hex(16)
    token = ApprovalToken(
        action=action,
        target=target,
        state_hash=state_hash,
        nonce=nonce,
        issued_at=now,
        expiry=now + CRITICAL_TTL_SECONDS,
        approver=approver,
    )
    token.signature = _sign_token(token)
    return token


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

@dataclass
class GateDecision:
    allowed: bool
    reason: str
    risk: str
    requires_hitl: bool
    token: Optional[ApprovalToken] = None


async def evaluate(
    action: str,
    target: str,
    state: HomeState,
    state_hash: str,
    requestor: str,
    raw_input: str,
    hitl_fn: Optional[Callable[..., Awaitable[Optional[str]]]] = None,
) -> GateDecision:
    """
    Evaluate whether an action is permitted given current state.

    Gate on blast radius, not action name:
    - Unknown actions are denied (closed whitelist)
    - Critical actions require HITL with full context
    - Non-critical actions with HIGH state risk are escalated to CRITICAL
    - All failure modes deny

    Args:
        action: Must be a key in ACTION_REGISTRY. Unknown = deny.
        target: Device or domain target.
        state: Current home state (from context_ops).
        state_hash: Hash of state snapshot — bound to token.
        requestor: Identity of requestor (authenticated before this call).
        raw_input: Original unedited user input shown to human approver.
        hitl_fn: Async callable that sends approval request and returns
                 approver ID string on YES, None on NO/timeout.
    """
    # Unknown action = deny (closed whitelist)
    if action not in ACTION_REGISTRY:
        logger.warning(f"GATE DENY — unknown action '{action}' from {requestor}")
        return GateDecision(
            allowed=False,
            reason=f"unknown action '{action}' — not in whitelist",
            risk="UNKNOWN",
            requires_hitl=False,
        )

    entry = ACTION_REGISTRY[action]
    blast_risk = entry["risk"]

    # State escalation: even NON_CRITICAL actions in HIGH-risk state get escalated
    state_risk = state.risk_level()
    effective_risk = CRITICAL if state_risk == "HIGH" else blast_risk

    logger.info(f"GATE EVAL — action={action} target={target} blast={blast_risk} state={state_risk} effective={effective_risk}")

    if effective_risk == NON_CRITICAL:
        logger.info(f"GATE ALLOW (auto) — {action} on {target}")
        return GateDecision(
            allowed=True,
            reason="non-critical action, state is LOW risk",
            risk=effective_risk,
            requires_hitl=False,
        )

    # CRITICAL — requires HITL
    if hitl_fn is None:
        logger.warning(f"GATE DENY — critical action '{action}' but no HITL function provided")
        return GateDecision(
            allowed=False,
            reason="critical action requires HITL but no approval channel configured",
            risk=effective_risk,
            requires_hitl=True,
        )

    # Send HITL request with full context (Perplexity / ChatGPT Class 6 fix)
    logger.info(f"GATE HITL — firing approval request for {action} on {target}")
    approver = await hitl_fn(
        action=action,
        target=target,
        requestor=requestor,
        risk=effective_risk,
        state=state,
        state_hash=state_hash,
        raw_input=raw_input,
    )

    if approver is None:
        logger.warning(f"GATE DENY — HITL timeout or rejection for {action}")
        return GateDecision(
            allowed=False,
            reason="HITL approval not received — deny",
            risk=effective_risk,
            requires_hitl=True,
        )

    # Issue bound token
    token = issue_token(action, target, state_hash, approver)
    logger.info(f"GATE ALLOW (approved) — {action} on {target} by {approver} token={token.nonce[:8]}...")
    return GateDecision(
        allowed=True,
        reason=f"approved by {approver}",
        risk=effective_risk,
        requires_hitl=True,
        token=token,
    )
