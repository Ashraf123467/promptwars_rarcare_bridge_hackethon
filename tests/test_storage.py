"""Unit tests for SQLite storage layer and audit log immutability."""

from datetime import datetime
import pytest
from core.models import AuditEntry, EventLog, EventType, Finding, FindingType, JourneyStatus, Severity
from storage.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(db_path=tmp_path / "test_store.db")


def test_db_event_lifecycle(db):
    """Test inserting, querying, and sample status tracking in SQLite."""
    t0 = datetime(2026, 10, 20, 10, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S-1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        EventLog(event_id="E2", sample_id="S-1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0),
    ]
    inserted = db.insert_events(events)
    assert inserted == 2

    stored = db.get_events_for_sample("S-1")
    assert len(stored) == 2
    assert stored[0].event_id == "E1"

    # Status tracking
    db.update_sample_status("S-1", JourneyStatus.VALIDATED)
    statuses = db.get_all_sample_statuses()
    assert statuses.get("S-1") == JourneyStatus.VALIDATED.value


def test_db_finding_and_audit_trail(db):
    """Test finding insertion and audit trail append-only behavior."""
    finding = Finding(
        finding_id="F-1",
        sample_id="S-1",
        finding_type=FindingType.MISSING_EVENT,
        severity=Severity.HIGH,
        evidence_event_ids=["E1"],
        description="Missing accession",
        suggested_action="Verify physical specimen",
        rule_name="MANDATORY_MILESTONE",
    )
    db.insert_findings([finding])
    findings = db.get_all_findings()
    assert len(findings) == 1
    assert findings[0].finding_id == "F-1"
    assert findings[0].status == "PENDING_REVIEW"

    # Append audit entry
    entry = AuditEntry(
        entry_id="AUD-001",
        actor="TechA",
        action="TEST_ACTION",
        sample_id="S-1",
        finding_id="F-1",
        details="Sample verified manually.",
    )
    db.append_audit_log(entry)
    trail = db.get_audit_trail()
    assert len(trail) == 1
    assert trail[0]["entry_id"] == "AUD-001"
    assert trail[0]["actor"] == "TechA"
