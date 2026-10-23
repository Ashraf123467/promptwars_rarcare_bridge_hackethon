"""Baseline implementations for empirical comparison against LabTrace AI reconciliation engine."""

from typing import Dict, List
from core.models import EventLog, Finding, FindingType, Severity


class NaiveRuleBaseline:
    """A naive, single-pass rule baseline.
    
    Lacks multi-event correlation, clock skew tolerance, and cross-source
    barcode integrity verification. Uses brittle static thresholds.
    """

    def __init__(self, expected_event_count: int = 6):
        self.expected_event_count = expected_event_count

    def reconcile_journey(self, sample_id: str, events: List[EventLog]) -> List[Finding]:
        """Run simplistic checks on a single journey."""
        findings: List[Finding] = []
        if not events:
            return findings

        # Naive Check 1: Count check only
        if len(events) < self.expected_event_count:
            findings.append(
                Finding(
                    finding_id=f"NAIVE-{sample_id}-COUNT",
                    sample_id=sample_id,
                    finding_type=FindingType.MISSING_EVENT,
                    severity=Severity.HIGH,
                    evidence_event_ids=[e.event_id for e in events[:1]],
                    description=f"Naive check: Found {len(events)} events, expected {self.expected_event_count}.",
                    suggested_action="Review log count.",
                    rule_name="NAIVE_COUNT_CHECK",
                )
            )

        # Naive Check 2: Strict adjacent timestamp monotonicity (fails under clock jitter)
        for i in range(len(events) - 1):
            if events[i].timestamp > events[i + 1].timestamp:
                findings.append(
                    Finding(
                        finding_id=f"NAIVE-{sample_id}-TIME-{i}",
                        sample_id=sample_id,
                        finding_type=FindingType.TIMESTAMP_CONFLICT,
                        severity=Severity.HIGH,
                        evidence_event_ids=[events[i].event_id, events[i + 1].event_id],
                        description="Naive check: Strict adjacent timestamp inversion.",
                        suggested_action="Check timestamps.",
                        rule_name="NAIVE_TIME_MONOTONICITY",
                    )
                )

        return findings

    def reconcile_all(self, events: List[EventLog]) -> Dict[str, List[Finding]]:
        """Reconcile all samples using naive rules."""
        by_sample: Dict[str, List[EventLog]] = {}
        for evt in events:
            by_sample.setdefault(evt.sample_id, []).append(evt)

        results: Dict[str, List[Finding]] = {}
        for sid, sample_events in by_sample.items():
            results[sid] = self.reconcile_journey(sid, sample_events)
        return results
