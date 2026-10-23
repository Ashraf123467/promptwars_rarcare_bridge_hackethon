"""Lightweight SQLite database storage for LabTrace AI.

Provides transparent local storage for events, findings, review decisions,
and an append-only audit trail. Real laboratory systems are never modified.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from core.models import (
    AuditEntry,
    EventLog,
    EventType,
    Finding,
    FindingType,
    JourneyStatus,
    ReviewDecision,
    Severity,
)

DEFAULT_DB_PATH = Path("labtrace_prototype.db")


class Database:
    """Manages SQLite schema and queries for LabTrace AI prototype."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create schema if not existing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    sample_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_system TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_sample ON events (sample_id)")

            # Findings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    sample_id TEXT NOT NULL,
                    finding_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    evidence_event_ids_json TEXT NOT NULL,
                    description TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_sample ON findings (sample_id)")

            # Review decisions table (Human-in-the-loop decisions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_decisions (
                    decision_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    sample_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    justification TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    simulated_change_summary TEXT NOT NULL
                )
            """)

            # Append-only audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    sample_id TEXT,
                    finding_id TEXT,
                    details TEXT NOT NULL
                )
            """)

            # Sample status tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sample_status (
                    sample_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.commit()

    def reset_database(self) -> None:
        """Clear all tables for fresh evaluation or simulation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events")
            cursor.execute("DELETE FROM findings")
            cursor.execute("DELETE FROM review_decisions")
            cursor.execute("DELETE FROM audit_trail")
            cursor.execute("DELETE FROM sample_status")
            conn.commit()

    # --- Event Methods ---

    def insert_events(self, events: List[EventLog]) -> int:
        """Batch insert raw event logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            records = [
                (
                    e.event_id,
                    e.sample_id,
                    e.event_type.value,
                    e.source_system,
                    e.timestamp.isoformat(),
                    e.operator_id,
                    json.dumps(e.metadata),
                )
                for e in events
            ]
            cursor.executemany(
                """
                INSERT OR REPLACE INTO events 
                (event_id, sample_id, event_type, source_system, timestamp, operator_id, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            conn.commit()
            return len(records)

    def get_events_for_sample(self, sample_id: str) -> List[EventLog]:
        """Fetch all events for a specific sample journey sorted chronologically."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE sample_id = ? ORDER BY timestamp ASC",
                (sample_id,),
            )
            rows = cursor.fetchall()
            return [
                EventLog(
                    event_id=r["event_id"],
                    sample_id=r["sample_id"],
                    event_type=EventType(r["event_type"]),
                    source_system=r["source_system"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    operator_id=r["operator_id"],
                    metadata=json.loads(r["metadata_json"]),
                )
                for r in rows
            ]

    def get_all_events(self) -> List[EventLog]:
        """Fetch all events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events ORDER BY sample_id, timestamp ASC")
            rows = cursor.fetchall()
            return [
                EventLog(
                    event_id=r["event_id"],
                    sample_id=r["sample_id"],
                    event_type=EventType(r["event_type"]),
                    source_system=r["source_system"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    operator_id=r["operator_id"],
                    metadata=json.loads(r["metadata_json"]),
                )
                for r in rows
            ]

    # --- Finding Methods ---

    def insert_findings(self, findings: List[Finding]) -> int:
        """Insert or replace reconciliation findings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            records = [
                (
                    f.finding_id,
                    f.sample_id,
                    f.finding_type.value,
                    f.severity.value,
                    json.dumps(f.evidence_event_ids),
                    f.description,
                    f.suggested_action,
                    f.rule_name,
                    "PENDING_REVIEW",
                )
                for f in findings
            ]
            cursor.executemany(
                """
                INSERT OR REPLACE INTO findings 
                (finding_id, sample_id, finding_type, severity, evidence_event_ids_json, description, suggested_action, rule_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            conn.commit()
            return len(records)

    def get_all_findings(self) -> List[Finding]:
        """Fetch all findings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings ORDER BY sample_id ASC")
            rows = cursor.fetchall()
            return [
                Finding(
                    finding_id=r["finding_id"],
                    sample_id=r["sample_id"],
                    finding_type=FindingType(r["finding_type"]),
                    severity=Severity(r["severity"]),
                    evidence_event_ids=json.loads(r["evidence_event_ids_json"]),
                    description=r["description"],
                    suggested_action=r["suggested_action"],
                    rule_name=r["rule_name"],
                )
                for r in rows
            ]

    def get_findings_for_sample(self, sample_id: str) -> List[Finding]:
        """Fetch findings for a single sample."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE sample_id = ?", (sample_id,))
            rows = cursor.fetchall()
            return [
                Finding(
                    finding_id=r["finding_id"],
                    sample_id=r["sample_id"],
                    finding_type=FindingType(r["finding_type"]),
                    severity=Severity(r["severity"]),
                    evidence_event_ids=json.loads(r["evidence_event_ids_json"]),
                    description=r["description"],
                    suggested_action=r["suggested_action"],
                    rule_name=r["rule_name"],
                )
                for r in rows
            ]

    # --- Review Decision & Human Gate Methods ---

    def record_decision(self, decision: ReviewDecision) -> None:
        """Record human review decision and append to audit log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO review_decisions
                (decision_id, finding_id, sample_id, action, reviewer, justification, timestamp, simulated_change_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.finding_id,
                    decision.sample_id,
                    decision.action.value,
                    decision.reviewer,
                    decision.justification,
                    decision.timestamp.isoformat(),
                    decision.simulated_change_summary,
                ),
            )
            # Update finding status
            new_status = "RESOLVED" if "APPROVED" in decision.action.value else "REVIEWED"
            cursor.execute(
                "UPDATE findings SET status = ? WHERE finding_id = ?",
                (new_status, decision.finding_id),
            )
            conn.commit()

        # Append to audit trail
        self.append_audit_log(
            AuditEntry(
                entry_id=f"AUD-{decision.decision_id}",
                timestamp=decision.timestamp,
                actor=decision.reviewer,
                action=f"DECISION_{decision.action.value}",
                sample_id=decision.sample_id,
                finding_id=decision.finding_id,
                details=f"Justification: {decision.justification}. Simulated Delta: {decision.simulated_change_summary}",
            )
        )

    def get_all_decisions(self) -> List[Dict[str, Any]]:
        """Fetch all review decisions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review_decisions ORDER BY timestamp DESC")
            return [dict(r) for r in cursor.fetchall()]

    # --- Audit Trail Methods ---

    def append_audit_log(self, entry: AuditEntry) -> None:
        """Append an immutable audit entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_trail
                (entry_id, timestamp, actor, action, sample_id, finding_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.timestamp.isoformat(),
                    entry.actor,
                    entry.action,
                    entry.sample_id,
                    entry.finding_id,
                    entry.details,
                ),
            )
            conn.commit()

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Fetch complete audit trail sorted chronologically."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_trail ORDER BY timestamp DESC")
            return [dict(r) for r in cursor.fetchall()]

    # --- Sample Status Methods ---

    def update_sample_status(self, sample_id: str, status: JourneyStatus) -> None:
        """Update sample tracking status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sample_status (sample_id, status, updated_at)
                VALUES (?, ?, ?)
                """,
                (sample_id, status.value, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_all_sample_statuses(self) -> Dict[str, str]:
        """Fetch dictionary of sample_id to status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sample_id, status FROM sample_status")
            return {r["sample_id"]: r["status"] for r in cursor.fetchall()}
