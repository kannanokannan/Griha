"""
tests/test_boundary.py — Boundary gate unit tests

The canonical test: "absence of permission is denial"
No Ollama required — pure deterministic logic tests.
"""
import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from framework.context_ops import HomeState
from framework.context_boundary import evaluate, ACTION_REGISTRY, issue_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def away_state() -> tuple[HomeState, str]:
    state = HomeState(anyone_home=False, mode="away", time_of_day="day", last_updated="2026-01-01T00:00:00", raw={})
    return state, state.state_hash()

def home_state() -> tuple[HomeState, str]:
    state = HomeState(anyone_home=True, mode="home", time_of_day="day", last_updated="2026-01-01T00:00:00", raw={})
    return state, state.state_hash()

async def deny_hitl(**kwargs):
    return None  # always deny

async def approve_hitl(**kwargs):
    return "test_approver"  # always approve


# ---------------------------------------------------------------------------
# THE canonical test: absence of permission is denial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_absence_of_permission_is_denial():
    """Unknown actions are denied. The whitelist is closed."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="invented_action_not_in_whitelist",
        target="front_door",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="do something",
        hitl_fn=deny_hitl,
    )
    assert not decision.allowed
    assert "unknown action" in decision.reason


# ---------------------------------------------------------------------------
# Critical actions require HITL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critical_action_denied_without_hitl():
    """Critical action with no HITL function = deny."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="unlock_front_door",
        target="front_door",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="let me in",
        hitl_fn=None,  # no HITL
    )
    assert not decision.allowed


@pytest.mark.asyncio
async def test_critical_action_denied_on_hitl_rejection():
    """Critical action denied when human says no."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="unlock_front_door",
        target="front_door",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="let me in",
        hitl_fn=deny_hitl,
    )
    assert not decision.allowed


@pytest.mark.asyncio
async def test_critical_action_allowed_on_hitl_approval():
    """Critical action allowed when human approves — token issued."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="unlock_front_door",
        target="front_door",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="let me in",
        hitl_fn=approve_hitl,
    )
    assert decision.allowed
    assert decision.token is not None
    assert decision.token.action == "unlock_front_door"


# ---------------------------------------------------------------------------
# State escalation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_critical_action_auto_allowed_in_low_risk_state():
    """Lights on with someone home = auto-allowed, no HITL."""
    state, state_hash = home_state()
    decision = await evaluate(
        action="turn_on_lights",
        target="living_room",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="turn on the lights",
        hitl_fn=None,
    )
    assert decision.allowed
    assert not decision.requires_hitl


@pytest.mark.asyncio
async def test_non_critical_action_escalated_in_high_risk_state():
    """Lights on with nobody home = escalated to CRITICAL, requires HITL."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="turn_on_lights",
        target="living_room",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="turn on the lights",
        hitl_fn=deny_hitl,
    )
    assert not decision.allowed
    assert decision.requires_hitl


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_replay_denied():
    """Same token cannot be used twice."""
    state, state_hash = away_state()
    decision = await evaluate(
        action="unlock_front_door",
        target="front_door",
        state=state,
        state_hash=state_hash,
        requestor="test",
        raw_input="let me in",
        hitl_fn=approve_hitl,
    )
    assert decision.allowed
    token = decision.token

    # First use — valid
    valid, reason = token.is_valid(state_hash)
    assert not valid  # nonce already marked used during evaluate()

    # Explicit replay attempt
    valid2, reason2 = token.is_valid(state_hash)
    assert not valid2
    assert "used" in reason2 or "expired" in reason2


@pytest.mark.asyncio
async def test_token_invalid_on_state_change():
    """Token bound to state hash — invalid if state changes (TOCTOU fix)."""
    state, state_hash = away_state()
    token = issue_token("unlock_front_door", "front_door", state_hash, "test_approver")

    # Simulate state change
    new_state = HomeState(anyone_home=True, mode="home", time_of_day="day", last_updated="2026-01-01T01:00:00", raw={})
    new_hash = new_state.state_hash()

    valid, reason = token.is_valid(new_hash)
    assert not valid
    assert "state changed" in reason
