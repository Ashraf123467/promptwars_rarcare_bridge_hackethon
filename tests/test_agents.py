"""Tests for the 3 logical agent roles in LabTrace AI."""

from datetime import datetime
from pathlib import Path
import pytest

from agents.intake_agent import IntakeAgent
from agents.reconciliation_agent import ReconciliationAgent
from agents.review_agent import ReviewAgent
from core.models import DecisionAction, EventLog, EventType, Finding, FindingType, Severity
from storage.db import Database


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_labtrace.db"
    return Database(db_path=db_file)


def test_intake_agent_valid_and_invalid(test_db):
    """IntakeAgent parses valid records and catches invalid records."""
    agent = IntakeAgent(db=test_db)
    raw_data = [
        {
            "event_id": "EVT-1",
            "sample_id": "SMP-1",
            "event_type": "COLLECTION",
            "source_system": "CLINIC",
            "timestamp": "2026-10-20T10:00:00",
            "operator_id": "OP-1",
            "metadata": "{\"barcode_scan\": \"SMP-1\"}",
        },
        {
            # Missing sample_id
            "event_id": "EVT-2",
            "event_type": "RECEIVING",
            "source_system": "DOCK",
            "timestamp": "2026-10-20T10:30:00",
        },
        {
            # Invalid event_type
            "event_id": "EVT-3",
            "sample_id": "SMP-2",
            "event_type": "NON_EXISTENT_STAGE",
            "source_system": "DOCK",
            "timestamp": "2026-10-20T10:30:00",
        },
    ]

    valid, errors = agent.process_records(raw_data)
    assert len(valid) == 1
    assert valid[0].event_id == "EVT-1"
    assert len(errors) == 2

    # Verify database persistence
    stored_events = test_db.get_events_for_sample("SMP-1")
    assert len(stored_events) == 1


def test_reconciliation_agent_workflow(test_db):
    """ReconciliationAgent processes stored events and records findings."""
    t0 = datetime(2026, 10, 20, 10, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S-ANOM", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        # Missing RECEIVING and ACCESSIONING!
        EventLog(event_id="E2", sample_id="S-ANOM", event_type=EventType.ANALYSIS, source_system="ANALYZER", timestamp=t0),
    ]
    test_db.insert_events(events)

    agent = ReconciliationAgent(db=test_db)
    findings_map = agent.run_reconciliation(events)

    assert "S-ANOM" in findings_map
    assert len(findings_map["S-ANOM"]) > 0

    # Verify database has findings
    db_findings = test_db.get_findings_for_sample("S-ANOM")
    assert len(db_findings) > 0


def test_review_agent_explanation_and_gate(test_db):
    """ReviewAgent generates deterministic explanation and enforces approval gate."""
    review_agent = ReviewAgent(db=test_db)

    finding = Finding(
        finding_id="FND-S1-01",
        sample_id="S1",
        finding_type=FindingType.DUPLICATE_EVENT,
        severity=Severity.MEDIUM,
        evidence_event_ids=["EVT-10", "EVT-11"],
        description="Duplicate accession scan detected.",
        suggested_action="Verify physical sample.",
        rule_name="DUPLICATE_STAGE_DETECTION",
    )
    events = [
        EventLog(event_id="EVT-10", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK_A", timestamp=datetime.utcnow()),
        EventLog(event_id="EVT-11", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK_B", timestamp=datetime.utcnow()),
    ]

    # Offline deterministic explanation
    explanation = review_agent.generate_explanation(finding, events)
    assert explanation["mode"] == "Deterministic Offline Template"
    assert explanation["grounding_verified"] is True
    assert len(explanation["verification_steps"]) >= 3

    # Human Gate: Missing reviewer or justification must raise ValueError
    with pytest.raises(ValueError):
        review_agent.submit_review_decision(
            finding_id="FND-S1-01",
            sample_id="S1",
            action=DecisionAction.APPROVED_SIMULATED_CORRECTION,
            reviewer="",  # Empty reviewer
            justification="Valid reason",
            simulated_change_summary="Marked secondary event as redundant scan",
        )

    with pytest.raises(ValueError):
        review_agent.submit_review_decision(
            finding_id="FND-S1-01",
            sample_id="S1",
            action=DecisionAction.APPROVED_SIMULATED_CORRECTION,
            reviewer="Dr. Jones",
            justification="",  # Empty justification
            simulated_change_summary="Marked secondary event as redundant scan",
        )

    # Valid human decision
    decision = review_agent.submit_review_decision(
        finding_id="FND-S1-01",
        sample_id="S1",
        action=DecisionAction.APPROVED_SIMULATED_CORRECTION,
        reviewer="Dr. Jones",
        justification="Confirmed with receiving tech that second scan was barcode printer calibration test.",
        simulated_change_summary="Simulated flag: deduplicated event EVT-11.",
    )
    assert decision.action == DecisionAction.APPROVED_SIMULATED_CORRECTION
    assert decision.reviewer == "Dr. Jones"

    # Verify audit trail has recorded the decision
    audit_trail = test_db.get_audit_trail()
    assert len(audit_trail) >= 1
    assert any("DECISION_APPROVED_SIMULATED_CORRECTION" in a["action"] for a in audit_trail)
