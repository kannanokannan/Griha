"""
EgressGate — graduated risk enforcement.
LOW=auto, MEDIUM=notify+30s cancel, HIGH=explicit approval.
HARDCODED: Locks/alarms always HIGH RISK. EU AI Act compliance.
"""
import asyncio, logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# HARDCODED — do not make configurable. Code change + review required to modify.
HARDCODED_HIGH_RISK_ACTIONS = frozenset(["lock_control","unlock_control","alarm_arm","alarm_disarm","alarm_trigger","door_control","gate_control","security_camera_control","security_mode_change"])

RISK_MAP: dict[str, RiskLevel] = {
    "light_control": RiskLevel.LOW, "media_control": RiskLevel.LOW, "fan_control": RiskLevel.LOW,
    "thermostat_control": RiskLevel.MEDIUM, "hvac_control": RiskLevel.MEDIUM, "blinds_control": RiskLevel.MEDIUM,
    "schedule_change": RiskLevel.MEDIUM, "reminder_create": RiskLevel.LOW, "grocery_order": RiskLevel.MEDIUM,
    "send_notification": RiskLevel.MEDIUM, "send_email": RiskLevel.HIGH, "security_action": RiskLevel.HIGH,
}

class EgressGate:
    def __init__(self, notify_fn: Optional[Callable] = None, approval_fn: Optional[Callable] = None, cancel_window_seconds: int = 30):
        self.notify_fn = notify_fn
        self.approval_fn = approval_fn
        self.cancel_window_seconds = cancel_window_seconds

    def classify(self, action: str) -> RiskLevel:
        if action in HARDCODED_HIGH_RISK_ACTIONS:
            return RiskLevel.HIGH
        return RISK_MAP.get(action, RiskLevel.MEDIUM)

    async def evaluate(self, action: str, domain: str, payload: dict) -> bool:
        risk = self.classify(action)
        if risk == RiskLevel.LOW: return True
        if risk == RiskLevel.MEDIUM: return await self._medium_gate(action, payload)
        if risk == RiskLevel.HIGH: return await self._high_gate(action, payload)
        return False

    async def _medium_gate(self, action: str, payload: dict) -> bool:
        if self.notify_fn:
            await self.notify_fn(f"⚠️ Pending: *{action}*\nWill execute in {self.cancel_window_seconds}s. Reply CANCEL to abort.")
        try:
            await asyncio.sleep(self.cancel_window_seconds)
            return True
        except asyncio.CancelledError:
            return False

    async def _high_gate(self, action: str, payload: dict) -> bool:
        if self.notify_fn:
            await self.notify_fn(f"🔴 HIGH RISK approval required: *{action}*\nReply APPROVE or DENY.")
        if self.approval_fn:
            return await self.approval_fn(action)
        logger.warning(f"High gate denied (no approval adapter): {action}")
        return False
