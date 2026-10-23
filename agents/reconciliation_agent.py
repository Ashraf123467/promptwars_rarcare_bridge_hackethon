"""Agent 2: Reconciliation Agent.

Executes the deterministic ECERE engine on validated event logs, correlates
multi-source events, detects discrepancies, and transitions FSM states.
"""

from datetime import datetime
from typing import Dict, List
from core.models import AuditEntry, EventLog, Finding, JourneyStatus
from core.reconciliation_engine import ReconciliationEngine
from core.state_machine import JourneyStateMachine
from storage.db import Database


class ReconciliationAgent:
    """Logical agent wrapping deterministic event reconciliation."""

    def __init__(self, db: Database, engine: ReconciliationEngine = None):
        self.db = db
        self.engine = engine or ReconciliationEngine()

    def run_reconciliation(
        self, events: List[EventLog] = None, actor: str = "ReconciliationAgent"
    ) -> Dict[str, List[Finding]]:
        """Reconcile events and update persistence and lifecycle states."""
        if events is None:
            events = self.db.get_all_events()

        # Execute reconciliation
        grouped_findings = self.engine.reconcile_all(events)
        
        all_findings: List[Finding] = []
        for sample_id, findings in grouped_findings.items():
            all_findings.extend(findings)

            # Advance state machine
            sm = JourneyStateMachine(initial_state=JourneyStatus.VALIDATED)
            sm.transition(JourneyStatus.RECONCILED, actor=actor)

            if findings:
                sm.transition(JourneyStatus.PENDING_REVIEW, actor=actor)
                self.db.update_sample_status(sample_id, JourneyStatus.PENDING_REVIEW)
            else:
                sm.transition(JourneyStatus.SIMULATED_RESOLVED, actor=actor)
                self.db.update_sample_status(sample_id, JourneyStatus.SIMULATED_RESOLVED)

        # Store findings in database
        if all_findings:
            self.db.insert_findings(all_findings)

        # Record audit entry
        self.db.append_audit_log(
            AuditEntry(
                entry_id=f"AUD-RECON-{int(datetime.utcnow().timestamp())}",
                actor=actor,
                action="RECONCILIATION_COMPLETED",
                details=f"Analyzed {len(events)} events across {len(grouped_findings)} journeys. Identified {len(all_findings)} discrepancy findings.",
            )
        )

        return grouped_findings
