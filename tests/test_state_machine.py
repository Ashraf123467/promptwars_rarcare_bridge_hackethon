"""Unit tests for JourneyStateMachine."""

import pytest
from core.models import JourneyStatus
from core.state_machine import JourneyStateMachine, StateMachineError


def test_valid_lifecycle_transitions():
    """State machine allows valid linear transitions."""
    sm = JourneyStateMachine(initial_state=JourneyStatus.RAW)
    assert sm.current_state == JourneyStatus.RAW

    sm.transition(JourneyStatus.INGESTED)
    assert sm.current_state == JourneyStatus.INGESTED

    sm.transition(JourneyStatus.VALIDATED)
    assert sm.current_state == JourneyStatus.VALIDATED

    sm.transition(JourneyStatus.RECONCILED)
    assert sm.current_state == JourneyStatus.RECONCILED

    sm.transition(JourneyStatus.PENDING_REVIEW)
    assert sm.current_state == JourneyStatus.PENDING_REVIEW

    sm.transition(JourneyStatus.REVIEWED)
    assert sm.current_state == JourneyStatus.REVIEWED

    sm.transition(JourneyStatus.SIMULATED_RESOLVED)
    assert sm.current_state == JourneyStatus.SIMULATED_RESOLVED


def test_illegal_state_jump_raises_error():
    """Attempting an illegal jump (e.g. RAW -> SIMULATED_RESOLVED) must fail."""
    sm = JourneyStateMachine(initial_state=JourneyStatus.RAW)
    with pytest.raises(StateMachineError):
        sm.transition(JourneyStatus.SIMULATED_RESOLVED)


def test_clean_journey_can_resolve_directly():
    """A clean journey with no findings can transition directly from RECONCILED to SIMULATED_RESOLVED."""
    sm = JourneyStateMachine(initial_state=JourneyStatus.VALIDATED)
    sm.transition(JourneyStatus.RECONCILED)
    assert sm.can_transition(JourneyStatus.SIMULATED_RESOLVED)
    sm.transition(JourneyStatus.SIMULATED_RESOLVED)
    assert sm.current_state == JourneyStatus.SIMULATED_RESOLVED
