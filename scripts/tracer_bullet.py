"""
scripts/tracer_bullet.py — Griha tracer bullet demo

Fires "let the dog walker in" through all four governance layers:
  1. Sthala    — local LLM extracts intent (narrate only)
  2. ContextOps — load home state, compute risk
  3. ContextBoundary — gate on blast radius, fire HITL
  4. Execution — deterministic mock actuation

Run with:
    python scripts/tracer_bullet.py

Requires:
    - Ollama running locally with phi3 pulled
    - config/home_state.yaml present (created by framework/context_ops.py)

This script uses a CLI HITL function (terminal YES/NO).
Telegram HITL is wired in the next phase.
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework.context_ops import get_state_snapshot, HomeState
from framework.context_boundary import evaluate, ACTION_REGISTRY, ApprovalToken
from framework.sthala import extract, narrate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s"
)
logger = logging.getLogger("tracer_bullet")


# ---------------------------------------------------------------------------
# Step 1 — Intent extraction (Sthala: narrate/compute split)
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = """You are a home intent parser. Extract the user's intent as JSON.

Output ONLY valid JSON in this exact format:
{
  "action": "<action_id>",
  "target": "<target_device>",
  "confidence": "<HIGH|MEDIUM|LOW>"
}

Valid action IDs: """ + ", ".join(sorted(ACTION_REGISTRY.keys())) + """

If the intent is unclear or maps to no valid action, output:
{"action": "unknown", "target": "none", "confidence": "LOW"}

Never invent action IDs not in the list above."""


async def extract_intent(user_input: str) -> dict:
    """Step 1: LLM extracts structured intent from natural language."""
    logger.info(f"STEP 1 — Extracting intent from: '{user_input}'")

    raw = await extract(
        prompt=f"User said: \"{user_input}\"\n\nExtract intent as JSON.",
        system_prompt=EXTRACT_SYSTEM,
    )

    # Parse JSON — LLM output is untrusted, validate strictly
    try:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:-1])
        intent = json.loads(cleaned)

        # Validate required fields
        if "action" not in intent or "target" not in intent:
            raise ValueError("Missing required fields")

        # Validate action is in whitelist (LLM cannot invent actions)
        if intent["action"] not in ACTION_REGISTRY and intent["action"] != "unknown":
            logger.warning(f"LLM returned unknown action '{intent['action']}' — treating as unknown")
            intent["action"] = "unknown"
            intent["confidence"] = "LOW"

        logger.info(f"STEP 1 — Extracted: {intent}")
        return intent

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"STEP 1 — Intent parse failed: {e}. Raw: {raw}")
        return {"action": "unknown", "target": "none", "confidence": "LOW"}


# ---------------------------------------------------------------------------
# Step 2 — Home state (ContextOps layer)
# ---------------------------------------------------------------------------

def load_state() -> tuple[HomeState, str]:
    """Step 2: Load home state. State sets risk — not the LLM."""
    logger.info("STEP 2 — Loading home state (ContextOps)")
    try:
        state, state_hash = get_state_snapshot()
        logger.info(
            f"STEP 2 — State: anyone_home={state.anyone_home} "
            f"mode={state.mode} risk={state.risk_level()} hash={state_hash}"
        )
        return state, state_hash
    except FileNotFoundError as e:
        logger.error(f"STEP 2 — {e}")
        raise


# ---------------------------------------------------------------------------
# Step 3 — CLI HITL function (Telegram replaces this in next phase)
# ---------------------------------------------------------------------------

async def cli_hitl(
    action: str,
    target: str,
    requestor: str,
    risk: str,
    state: HomeState,
    state_hash: str,
    raw_input: str,
) -> str | None:
    """
    CLI approval gate. Shows exact capability to human.
    Returns approver ID string on YES, None on NO.

    Telegram HITL replaces this in the next phase.
    """
    print("\n" + "="*60)
    print("GRIHA — APPROVAL REQUIRED")
    print("="*60)
    print(f"  ACTION    : {action}")
    print(f"  TARGET    : {target}")
    print(f"  REQUESTOR : {requestor}")
    print(f"  RISK      : {risk}")
    print(f"  STATE     : anyone_home={state.anyone_home}, mode={state.mode}")
    print(f"  STATE HASH: {state_hash}")
    print(f"  RAW INPUT : \"{raw_input}\"")
    print("="*60)
    print("Type YES to approve, anything else to deny (60s timeout):")

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, input, "> "),
            timeout=60.0
        )
        if response.strip().upper() == "YES":
            print("  ✓ Approved")
            return "cli_user"
        else:
            print("  ✗ Denied")
            return None
    except asyncio.TimeoutError:
        print("  ✗ Timeout — denied")
        return None


# ---------------------------------------------------------------------------
# Step 4 — Deterministic execution (mock)
# ---------------------------------------------------------------------------

async def execute_action(action: str, target: str, token: ApprovalToken, state: HomeState, state_hash: str) -> bool:
    """
    Step 4: Deterministic execution — only reached with a valid approved token.

    TOCTOU check: recompute state hash before executing.
    If state changed since approval — deny.
    """
    logger.info("STEP 4 — Execution layer (deterministic)")

    # TOCTOU check — recompute state hash immediately before execute
    _, current_hash = get_state_snapshot()
    valid, reason = token.is_valid(current_hash)

    if not valid:
        logger.error(f"STEP 4 — Token invalid: {reason}. DENY.")
        return False

    # Deterministic execution (mock — replace with real device call)
    logger.info(f"STEP 4 — EXECUTING: {action} on {target} (token={token.nonce[:8]}...)")
    print(f"\n  ✓ EXECUTED: {action} on {target}")
    print(f"  Token: {token.nonce[:8]}... | Approver: {token.approver}")
    return True


# ---------------------------------------------------------------------------
# Step 5 — Narration (Sthala: narrate layer)
# ---------------------------------------------------------------------------

async def narrate_outcome(action: str, target: str, success: bool, user_input: str) -> str:
    """Step 5: LLM narrates the outcome. Narrate only — no computation here."""
    outcome = "successfully completed" if success else "was denied"
    prompt = f'The request "{user_input}" resulted in: {action} on {target} {outcome}. Summarise in one friendly sentence.'
    return await narrate(prompt)


# ---------------------------------------------------------------------------
# Main tracer bullet
# ---------------------------------------------------------------------------

async def run_tracer_bullet(user_input: str, requestor: str = "telegram:demo_user"):
    print(f"\n{'='*60}")
    print(f"GRIHA TRACER BULLET")
    print(f"Input: \"{user_input}\"")
    print(f"{'='*60}\n")

    # Step 1: Extract intent (Sthala — narrate/compute split)
    intent = await extract_intent(user_input)

    if intent["action"] == "unknown":
        print("\n✗ Could not extract a valid intent. No action taken.")
        return

    # Step 2: Load home state (ContextOps)
    state, state_hash = load_state()

    # Step 3: Gate (ContextBoundary — blast radius, HITL)
    logger.info("STEP 3 — Boundary gate (ContextBoundary)")
    decision = await evaluate(
        action=intent["action"],
        target=intent["target"],
        state=state,
        state_hash=state_hash,
        requestor=requestor,
        raw_input=user_input,
        hitl_fn=cli_hitl,
    )

    if not decision.allowed:
        print(f"\n✗ DENIED: {decision.reason}")
        return

    # Step 4: Execute (deterministic — token validated, TOCTOU checked)
    success = await execute_action(
        action=intent["action"],
        target=intent["target"],
        token=decision.token,
        state=state,
        state_hash=state_hash,
    )

    # Step 5: Narrate outcome (Sthala — narrate only)
    summary = await narrate_outcome(intent["action"], intent["target"], success, user_input)
    print(f"\n  Summary: {summary}")


if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "let the dog walker in"
    asyncio.run(run_tracer_bullet(user_input))
