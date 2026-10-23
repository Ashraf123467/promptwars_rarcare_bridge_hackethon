"""Lightweight Bounded Finite State Machine (FSM) for sample journey reconciliation."""

from typing import Dict, Set
from core.models import JourneyStatus


class StateMachineError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class JourneyStateMachine:
    """Explicit deterministic state machine enforcing bounded agent workflows."""

    ALLOWED_TRANSITIONS: Dict[JourneyStatus, Set[JourneyStatus]] = {
        JourneyStatus.RAW: {JourneyStatus.INGESTED},
        JourneyStatus.INGESTED: {JourneyStatus.VALIDATED},
        JourneyStatus.VALIDATED: {JourneyStatus.RECONCILED},
        JourneyStatus.RECONCILED: {JourneyStatus.PENDING_REVIEW, JourneyStatus.SIMULATED_RESOLVED},
        JourneyStatus.PENDING_REVIEW: {JourneyStatus.REVIEWED},
        JourneyStatus.REVIEWED: {JourneyStatus.SIMULATED_RESOLVED, JourneyStatus.PENDING_REVIEW},
        JourneyStatus.SIMULATED_RESOLVED: set(),  # Terminal state
    }

    def __init__(self, initial_state: JourneyStatus = JourneyStatus.RAW):
        self.current_state = initial_state
        self.history = [initial_state]

    def transition(self, new_state: JourneyStatus, actor: str = "SYSTEM") -> JourneyStatus:
        """Execute a state transition with validation."""
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise StateMachineError(
                f"Illegal transition by {actor}: cannot transition from "
                f"'{self.current_state.value}' to '{new_state.value}'. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )
        self.current_state = new_state
        self.history.append(new_state)
        return self.current_state

    def can_transition(self, new_state: JourneyStatus) -> bool:
        return new_state in self.ALLOWED_TRANSITIONS.get(self.current_state, set())
