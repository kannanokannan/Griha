"""
framework/context_ops.py — Home state loader (ContextOps layer mock)

Loads home state from a local YAML file. State sets risk — not the LLM.
This is the Griha inheritance point for ContextOps context lifecycle concerns.

Part of the Griha tracer bullet: context_ops → context_boundary → sthala → coordinator
"""
import hashlib
import yaml
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


STATE_FILE = os.environ.get("GRIHA_STATE_FILE", "config/home_state.yaml")


@dataclass
class HomeState:
    anyone_home: bool
    mode: str              # "home", "away", "night", "guest"
    time_of_day: str       # "morning", "day", "evening", "night"
    last_updated: str
    raw: dict

    def state_hash(self) -> str:
        """Canonical hash of this state snapshot. Bound to approval tokens."""
        canonical = f"{self.anyone_home}|{self.mode}|{self.time_of_day}|{self.last_updated}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def risk_level(self) -> str:
        """
        State-derived risk level for access-domain actions.
        State sets risk — not the LLM, not the action name.
        """
        if not self.anyone_home:
            return "HIGH"
        if self.mode in ("night", "guest"):
            return "HIGH"
        if self.mode == "away":
            return "HIGH"
        return "LOW"


def load_home_state() -> HomeState:
    """
    Load home state from YAML. Raises FileNotFoundError if state file missing.
    Fail-closed: missing state = unknown state = treat as HIGH risk upstream.
    """
    if not os.path.exists(STATE_FILE):
        raise FileNotFoundError(
            f"Home state file not found: {STATE_FILE}. "
            "Create config/home_state.yaml before running Griha."
        )

    with open(STATE_FILE, "r") as f:
        raw = yaml.safe_load(f)

    return HomeState(
        anyone_home=raw.get("anyone_home", False),
        mode=raw.get("mode", "away"),
        time_of_day=raw.get("time_of_day", "day"),
        last_updated=raw.get("last_updated", datetime.utcnow().isoformat()),
        raw=raw,
    )


def get_state_snapshot() -> tuple[HomeState, str]:
    """
    Returns (state, state_hash). The hash is bound to approval tokens.
    Call immediately before execution to detect TOCTOU violations.
    """
    state = load_home_state()
    return state, state.state_hash()
