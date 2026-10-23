"""Domain models for LabTrace AI.

Defines Pydantic v2 data models for event logs, findings, review decisions,
and audit trails for clinical diagnostic sample event reconciliation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    COLLECTION = "COLLECTION"
    TRANSPORT_DISPATCH = "TRANSPORT_DISPATCH"
    RECEIVING = "RECEIVING"
    ACCESSIONING = "ACCESSIONING"
    ANALYSIS = "ANALYSIS"
    REPORTING = "REPORTING"


# Canonical lifecycle sequence order
STAGE_ORDER: Dict[EventType, int] = {
    EventType.COLLECTION: 1,
    EventType.TRANSPORT_DISPATCH: 2,
    EventType.RECEIVING: 3,
    EventType.ACCESSIONING: 4,
    EventType.ANALYSIS: 5,
    EventType.REPORTING: 6,
}


class FindingType(str, Enum):
    MISSING_EVENT = "MISSING_EVENT"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    TIMESTAMP_CONFLICT = "TIMESTAMP_CONFLICT"
    INVALID_SEQUENCE = "INVALID_SEQUENCE"
    SAMPLE_ID_MISMATCH = "SAMPLE_ID_MISMATCH"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EventLog(BaseModel):
    event_id: str
    sample_id: str
    event_type: EventType
    source_system: str
    timestamp: datetime
    operator_id: str = "SYSTEM"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    finding_id: str
    sample_id: str
    finding_type: FindingType
    severity: Severity
    evidence_event_ids: List[str]
    description: str
    suggested_action: str
    rule_name: str
    status: str = "PENDING_REVIEW"


class DecisionAction(str, Enum):
    APPROVED_SIMULATED_CORRECTION = "APPROVED_SIMULATED_CORRECTION"
    REJECTED = "REJECTED"
    FLAGGED_PHYSICAL_INSPECTION = "FLAGGED_PHYSICAL_INSPECTION"


class ReviewDecision(BaseModel):
    decision_id: str
    finding_id: str
    sample_id: str
    action: DecisionAction
    reviewer: str
    justification: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    simulated_change_summary: str


class JourneyStatus(str, Enum):
    RAW = "RAW"
    INGESTED = "INGESTED"
    VALIDATED = "VALIDATED"
    RECONCILED = "RECONCILED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEWED = "REVIEWED"
    SIMULATED_RESOLVED = "SIMULATED_RESOLVED"


class AuditEntry(BaseModel):
    entry_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    action: str
    sample_id: Optional[str] = None
    finding_id: Optional[str] = None
    details: str
