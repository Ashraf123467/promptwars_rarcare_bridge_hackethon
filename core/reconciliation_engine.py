"""Lightweight Deterministic Event Reconciliation Engine (ECERE).

Detects 5 key operational anomalies:
1. MISSING_EVENT: Expected lifecycle milestone missing from the journey.
2. DUPLICATE_EVENT: Multiple log entries for the same lifecycle stage.
3. TIMESTAMP_CONFLICT: Chronological time inversion across sequential steps.
4. INVALID_SEQUENCE: Out-of-order workflow execution (e.g. analysis before accession).
5. SAMPLE_ID_MISMATCH: Mismatched tube barcode / alias across multi-system handoffs.
"""

from datetime import timedelta
from typing import Dict, List, Set
from core.models import (
    EventLog,
    EventType,
    Finding,
    FindingType,
    STAGE_ORDER,
    Severity,
)

# Mandatory stages required for a completed sample analysis journey
MANDATORY_STAGES: List[EventType] = [
    EventType.COLLECTION,
    EventType.RECEIVING,
    EventType.ACCESSIONING,
    EventType.ANALYSIS,
    EventType.REPORTING,
]

# Allowed clock skew tolerance between systems (e.g. 60 seconds)
DEFAULT_CLOCK_SKEW_TOLERANCE = timedelta(seconds=60)


class ReconciliationEngine:
    """Deterministic, rule-based cross-source event reconciliation engine."""

    def __init__(self, clock_skew_tolerance: timedelta = DEFAULT_CLOCK_SKEW_TOLERANCE):
        self.clock_skew_tolerance = clock_skew_tolerance

    def reconcile_journey(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Reconcile a single sample journey's events and produce deterministic findings."""
        findings: List[Finding] = []
        if not events:
            return findings

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        # 1. Check for Sample ID / Barcode mismatches in metadata
        findings.extend(self._check_sample_id_mismatch(sample_id, sorted_events))

        # 2. Check for Duplicate events
        findings.extend(self._check_duplicates(sample_id, sorted_events))

        # 3. Check for Invalid Sequence & Timestamp Conflicts
        findings.extend(self._check_sequence_and_timestamps(sample_id, sorted_events))

        # 4. Check for Missing expected events
        findings.extend(self._check_missing_events(sample_id, sorted_events))

        return findings

    def _check_sample_id_mismatch(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Detect barcode aliases, container IDs, or requisition mismatches."""
        findings: List[Finding] = []
        for evt in events:
            # Check metadata fields like 'barcode_scan', 'tube_alias', 'requisition_id'
            barcode = evt.metadata.get("barcode_scan")
            tube_alias = evt.metadata.get("tube_alias")
            
            mismatch_detected = False
            culprit_value = ""

            if barcode and barcode != sample_id:
                mismatch_detected = True
                culprit_value = f"scanned barcode '{barcode}'"
            elif tube_alias and tube_alias != sample_id:
                mismatch_detected = True
                culprit_value = f"tube alias '{tube_alias}'"

            if mismatch_detected:
                findings.append(
                    Finding(
                        finding_id=f"FND-{sample_id}-ID-{evt.event_id}",
                        sample_id=sample_id,
                        finding_type=FindingType.SAMPLE_ID_MISMATCH,
                        severity=Severity.CRITICAL,
                        evidence_event_ids=[evt.event_id],
                        description=(
                            f"Sample ID mismatch detected at {evt.event_type.value} ({evt.source_system}): "
                            f"Primary ID '{sample_id}' conflicts with {culprit_value}."
                        ),
                        suggested_action="Perform physical inspection of specimen barcode label and cross-reference order requisition.",
                        rule_name="SAMPLE_ID_INTEGRITY_CHECK",
                    )
                )
        return findings

    def _check_duplicates(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Detect repeated occurrences of the same lifecycle stage."""
        findings: List[Finding] = []
        stage_map: Dict[EventType, List[EventLog]] = {}
        for evt in events:
            stage_map.setdefault(evt.event_type, []).append(evt)

        for event_type, evts in stage_map.items():
            if len(evts) > 1:
                evt_ids = [e.event_id for e in evts]
                findings.append(
                    Finding(
                        finding_id=f"FND-{sample_id}-DUP-{event_type.value}",
                        sample_id=sample_id,
                        finding_type=FindingType.DUPLICATE_EVENT,
                        severity=Severity.MEDIUM,
                        evidence_event_ids=evt_ids,
                        description=(
                            f"Duplicate event stage '{event_type.value}' recorded {len(evts)} times "
                            f"across systems {[e.source_system for e in evts]}."
                        ),
                        suggested_action="Verify if duplicate scans represent dual-instrument logging or redundant network retries.",
                        rule_name="DUPLICATE_STAGE_DETECTION",
                    )
                )
        return findings

    def _check_sequence_and_timestamps(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Check for chronological inversions and workflow sequence violations."""
        findings: List[Finding] = []
        n = len(events)
        if n < 2:
            return findings

        # Check adjacent events by timestamp
        for i in range(n - 1):
            curr_evt = events[i]
            next_evt = events[i + 1]

            curr_order = STAGE_ORDER.get(curr_evt.event_type, 99)
            next_order = STAGE_ORDER.get(next_evt.event_type, 99)

            # If the current event represents a later lifecycle stage than next event
            if curr_order > next_order:
                findings.append(
                    Finding(
                        finding_id=f"FND-{sample_id}-SEQ-{curr_evt.event_id}-{next_evt.event_id}",
                        sample_id=sample_id,
                        finding_type=FindingType.INVALID_SEQUENCE,
                        severity=Severity.HIGH,
                        evidence_event_ids=[curr_evt.event_id, next_evt.event_id],
                        description=(
                            f"Invalid sequence order: Stage '{curr_evt.event_type.value}' (stage {curr_order}) "
                            f"occurred before '{next_evt.event_type.value}' (stage {next_order})."
                        ),
                        suggested_action="Review station audit logs for out-of-order manual data entry or unsynchronized batch sync.",
                        rule_name="CANONICAL_SEQUENCE_ORDER",
                    )
                )

        # Check for temporal causality (timestamp conflicts):
        # If stage A canonically precedes stage B, but event A's timestamp is later than event B's
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                ea = events[i]
                eb = events[j]
                order_a = STAGE_ORDER.get(ea.event_type, 99)
                order_b = STAGE_ORDER.get(eb.event_type, 99)

                # ea should happen before eb, but ea occurred after eb + tolerance
                if order_a < order_b and ea.timestamp > (eb.timestamp + self.clock_skew_tolerance):
                    finding_id = f"FND-{sample_id}-TIME-{ea.event_id}-{eb.event_id}"
                    if not any(f.finding_id == finding_id for f in findings):
                        findings.append(
                            Finding(
                                finding_id=finding_id,
                                sample_id=sample_id,
                                finding_type=FindingType.TIMESTAMP_CONFLICT,
                                severity=Severity.CRITICAL,
                                evidence_event_ids=[ea.event_id, eb.event_id],
                                description=(
                                    f"Timestamp conflict: Preceding stage '{ea.event_type.value}' timestamp "
                                    f"({ea.timestamp.isoformat()}) is later than succeeding stage "
                                    f"'{eb.event_type.value}' timestamp ({eb.timestamp.isoformat()})."
                                ),
                                suggested_action="Check source system NTP clock synchronization and time zone configuration.",
                                rule_name="TEMPORAL_CAUSALITY_CHECK",
                            )
                        )
        return findings

    def _check_missing_events(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Detect missing mandatory events when later stages have already been reached."""
        findings: List[Finding] = []
        present_stages: Set[EventType] = {e.event_type for e in events}
        max_order_present = max((STAGE_ORDER.get(s, 0) for s in present_stages), default=0)

        for mandatory_stage in MANDATORY_STAGES:
            stage_order = STAGE_ORDER.get(mandatory_stage, 0)
            # If the journey reached a stage beyond this mandatory stage, but the mandatory stage is missing
            if stage_order < max_order_present and mandatory_stage not in present_stages:
                # Evidence is the latest event that bypassed the mandatory stage
                evidence_ids = [e.event_id for e in events if STAGE_ORDER.get(e.event_type, 0) > stage_order]
                findings.append(
                    Finding(
                        finding_id=f"FND-{sample_id}-MISSING-{mandatory_stage.value}",
                        sample_id=sample_id,
                        finding_type=FindingType.MISSING_EVENT,
                        severity=Severity.HIGH,
                        evidence_event_ids=evidence_ids[:2],  # Provide immediate evidence
                        description=(
                            f"Missing expected milestone: Stage '{mandatory_stage.value}' was never logged, "
                            f"despite sample reaching subsequent stage(s)."
                        ),
                        suggested_action=f"Verify paper requisition or station intake logs for missing '{mandatory_stage.value}' record.",
                        rule_name="MANDATORY_MILESTONE_COMPLETION",
                    )
                )
        return findings

    def reconcile_all(self, events: List[EventLog]) -> Dict[str, List[Finding]]:
        """Reconcile a collection of events grouped by sample ID."""
        by_sample: Dict[str, List[EventLog]] = {}
        for evt in events:
            by_sample.setdefault(evt.sample_id, []).append(evt)

        all_findings: Dict[str, List[Finding]] = {}
        for sample_id, sample_events in by_sample.items():
            all_findings[sample_id] = self.reconcile_journey(sample_id, sample_events)
        return all_findings
