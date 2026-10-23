"""Unit tests for deterministic ReconciliationEngine (ECERE)."""

from datetime import datetime, timedelta
import pytest
from core.models import EventLog, EventType, FindingType, Severity
from core.reconciliation_engine import ReconciliationEngine


@pytest.fixture
def engine():
    return ReconciliationEngine(clock_skew_tolerance=timedelta(seconds=60))


def test_clean_journey_has_no_findings(engine):
    """A standard clinical lifecycle journey with complete milestones produces 0 findings."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0, metadata={"barcode_scan": "S1"}),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.TRANSPORT_DISPATCH, source_system="COURIER", timestamp=t0 + timedelta(minutes=20), metadata={"barcode_scan": "S1"}),
        EventLog(event_id="E3", sample_id="S1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0 + timedelta(minutes=40), metadata={"barcode_scan": "S1"}),
        EventLog(event_id="E4", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK", timestamp=t0 + timedelta(minutes=60), metadata={"barcode_scan": "S1"}),
        EventLog(event_id="E5", sample_id="S1", event_type=EventType.ANALYSIS, source_system="ANALYZER", timestamp=t0 + timedelta(minutes=90), metadata={"barcode_scan": "S1"}),
        EventLog(event_id="E6", sample_id="S1", event_type=EventType.REPORTING, source_system="PORTAL", timestamp=t0 + timedelta(minutes=120), metadata={"barcode_scan": "S1"}),
    ]
    findings = engine.reconcile_journey("S1", events)
    assert len(findings) == 0


def test_detects_missing_expected_event(engine):
    """Detects omitted ACCESSIONING stage when sample reaches ANALYSIS."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0 + timedelta(minutes=40)),
        # ACCESSIONING is missing!
        EventLog(event_id="E4", sample_id="S1", event_type=EventType.ANALYSIS, source_system="ANALYZER", timestamp=t0 + timedelta(minutes=90)),
        EventLog(event_id="E5", sample_id="S1", event_type=EventType.REPORTING, source_system="PORTAL", timestamp=t0 + timedelta(minutes=120)),
    ]
    findings = engine.reconcile_journey("S1", events)
    assert any(f.finding_type == FindingType.MISSING_EVENT and "ACCESSIONING" in f.description for f in findings)


def test_detects_duplicate_events(engine):
    """Detects duplicate scans for the same lifecycle stage."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0 + timedelta(minutes=40)),
        EventLog(event_id="E3A", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK_A", timestamp=t0 + timedelta(minutes=60)),
        EventLog(event_id="E3B", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK_B", timestamp=t0 + timedelta(minutes=62)),
        EventLog(event_id="E4", sample_id="S1", event_type=EventType.ANALYSIS, source_system="ANALYZER", timestamp=t0 + timedelta(minutes=90)),
        EventLog(event_id="E5", sample_id="S1", event_type=EventType.REPORTING, source_system="PORTAL", timestamp=t0 + timedelta(minutes=120)),
    ]
    findings = engine.reconcile_journey("S1", events)
    dup_findings = [f for f in findings if f.finding_type == FindingType.DUPLICATE_EVENT]
    assert len(dup_findings) == 1
    assert "E3A" in dup_findings[0].evidence_event_ids
    assert "E3B" in dup_findings[0].evidence_event_ids


def test_detects_timestamp_conflict(engine):
    """Detects timestamp conflict where preceding step occurs after succeeding step."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0 + timedelta(hours=2)),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0 + timedelta(hours=1)),
        EventLog(event_id="E3", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK", timestamp=t0 + timedelta(hours=3)),
    ]
    findings = engine.reconcile_journey("S1", events)
    time_findings = [f for f in findings if f.finding_type == FindingType.TIMESTAMP_CONFLICT]
    assert len(time_findings) >= 1
    assert any("E1" in f.evidence_event_ids and "E2" in f.evidence_event_ids for f in time_findings)


def test_detects_invalid_sequence_order(engine):
    """Detects out-of-order stages such as ANALYSIS executed before ACCESSIONING."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.RECEIVING, source_system="DOCK", timestamp=t0 + timedelta(minutes=20)),
        EventLog(event_id="E3", sample_id="S1", event_type=EventType.ANALYSIS, source_system="ANALYZER", timestamp=t0 + timedelta(minutes=40)),
        EventLog(event_id="E4", sample_id="S1", event_type=EventType.ACCESSIONING, source_system="DESK", timestamp=t0 + timedelta(minutes=60)),
    ]
    findings = engine.reconcile_journey("S1", events)
    seq_findings = [f for f in findings if f.finding_type == FindingType.INVALID_SEQUENCE]
    assert len(seq_findings) >= 1


def test_detects_sample_id_mismatch(engine):
    """Detects corrupted tube barcode or alias scanning mismatch."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    events = [
        EventLog(event_id="E1", sample_id="SMP-100", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0, metadata={"barcode_scan": "SMP-100"}),
        EventLog(event_id="E2", sample_id="SMP-100", event_type=EventType.ACCESSIONING, source_system="DESK", timestamp=t0 + timedelta(minutes=30), metadata={"barcode_scan": "SMP-999"}),
    ]
    findings = engine.reconcile_journey("SMP-100", events)
    id_findings = [f for f in findings if f.finding_type == FindingType.SAMPLE_ID_MISMATCH]
    assert len(id_findings) == 1
    assert "SMP-999" in id_findings[0].description
    assert id_findings[0].severity == Severity.CRITICAL


def test_clock_skew_tolerance(engine):
    """Sub-minute clock skew does not trigger false positive timestamp conflicts."""
    t0 = datetime(2026, 10, 20, 9, 0, 0)
    # E2 is 30 seconds before E1 due to minor network clock drift, within 60s tolerance
    events = [
        EventLog(event_id="E1", sample_id="S1", event_type=EventType.COLLECTION, source_system="CLINIC", timestamp=t0),
        EventLog(event_id="E2", sample_id="S1", event_type=EventType.TRANSPORT_DISPATCH, source_system="COURIER", timestamp=t0 - timedelta(seconds=30)),
    ]
    findings = engine.reconcile_journey("S1", events)
    time_findings = [f for f in findings if f.finding_type == FindingType.TIMESTAMP_CONFLICT]
    assert len(time_findings) == 0
