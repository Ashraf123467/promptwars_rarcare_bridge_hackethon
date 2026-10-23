"""Agent 1: Intake and Schema Validation Agent.

Ingests event logs, validates schemas, enforces typing, and transitions
lifecycle states from RAW -> INGESTED -> VALIDATED.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Tuple
from core.models import AuditEntry, EventLog, EventType, JourneyStatus
from core.state_machine import JourneyStateMachine
from storage.db import Database


class IntakeAgent:
    """Logical agent responsible for input validation and state transitions."""

    def __init__(self, db: Database):
        self.db = db

    def process_records(
        self, raw_records: List[Dict[str, Any]], actor: str = "IntakeAgent"
    ) -> Tuple[List[EventLog], List[str]]:
        """Validate raw incoming records and return valid EventLogs along with any error strings."""
        valid_events: List[EventLog] = []
        errors: List[str] = []

        for idx, rec in enumerate(raw_records):
            try:
                # Required fields
                req_fields = ["event_id", "sample_id", "event_type", "source_system", "timestamp"]
                missing = [f for f in req_fields if f not in rec or rec[f] is None or str(rec[f]).strip() == ""]
                if missing:
                    errors.append(f"Row {idx+1}: Missing required fields {missing}")
                    continue

                # Parse event_type
                try:
                    event_type = EventType(str(rec["event_type"]).strip().upper())
                except ValueError:
                    errors.append(f"Row {idx+1}: Invalid event_type '{rec.get('event_type')}'")
                    continue

                # Parse timestamp
                ts = rec["timestamp"]
                if isinstance(ts, str):
                    try:
                        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        errors.append(f"Row {idx+1}: Invalid timestamp format '{ts}'")
                        continue
                elif isinstance(ts, datetime):
                    timestamp = ts
                else:
                    errors.append(f"Row {idx+1}: Unsupported timestamp type {type(ts)}")
                    continue

                # Parse metadata if string
                metadata = rec.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}

                event = EventLog(
                    event_id=str(rec["event_id"]).strip(),
                    sample_id=str(rec["sample_id"]).strip(),
                    event_type=event_type,
                    source_system=str(rec["source_system"]).strip(),
                    timestamp=timestamp,
                    operator_id=str(rec.get("operator_id", "SYSTEM")).strip(),
                    metadata=metadata,
                )
                valid_events.append(event)

            except Exception as e:
                errors.append(f"Row {idx+1}: Parsing error: {str(e)}")

        if valid_events:
            # Store validated events in database
            self.db.insert_events(valid_events)

            # Update sample statuses through FSM
            unique_samples = {e.sample_id for e in valid_events}
            for sid in unique_samples:
                sm = JourneyStateMachine(initial_state=JourneyStatus.RAW)
                sm.transition(JourneyStatus.INGESTED, actor=actor)
                sm.transition(JourneyStatus.VALIDATED, actor=actor)
                self.db.update_sample_status(sid, JourneyStatus.VALIDATED)

            # Record audit entry
            self.db.append_audit_log(
                AuditEntry(
                    entry_id=f"AUD-INTAKE-{int(datetime.utcnow().timestamp())}",
                    actor=actor,
                    action="INTAKE_VALIDATION_COMPLETED",
                    details=f"Successfully validated {len(valid_events)} events across {len(unique_samples)} sample journeys. Errors: {len(errors)}.",
                )
            )

        return valid_events, errors
