"""Reproducible Synthetic Clinical Diagnostic Event Generator.

Generates 100-300 synthetic sample journeys with known ground truth anomalies:
- MISSING_EVENT
- DUPLICATE_EVENT
- TIMESTAMP_CONFLICT
- INVALID_SEQUENCE
- SAMPLE_ID_MISMATCH
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Tuple
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import EventLog, EventType, FindingType

DATA_DIR = Path(__file__).resolve().parent
CSV_PATH = DATA_DIR / "synthetic_events.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

SOURCE_SYSTEMS = {
    EventType.COLLECTION: "EHR_CLINIC",
    EventType.TRANSPORT_DISPATCH: "LOGISTICS_COURIER",
    EventType.RECEIVING: "LAB_RECEIVING_DOCK",
    EventType.ACCESSIONING: "LIS_ACCESSION_DESK",
    EventType.ANALYSIS: "ANALYZER_ROBOTICS",
    EventType.REPORTING: "PHYSICIAN_PORTAL",
}

OPERATORS = ["OP-701", "OP-702", "OP-703", "OP-704", "OP-705"]


def generate_synthetic_dataset(
    total_samples: int = 150,
    anomaly_ratio: float = 0.33,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Generate reproducible synthetic event logs and matching ground truth labels."""
    random.seed(seed)
    
    num_anomalies = int(total_samples * anomaly_ratio)
    num_clean = total_samples - num_anomalies

    # Determine anomaly types for the anomaly journeys (approx 10 each for 5 types)
    anomaly_categories = [
        FindingType.MISSING_EVENT,
        FindingType.DUPLICATE_EVENT,
        FindingType.TIMESTAMP_CONFLICT,
        FindingType.INVALID_SEQUENCE,
        FindingType.SAMPLE_ID_MISMATCH,
    ]
    
    assigned_anomalies = []
    for i in range(num_anomalies):
        assigned_anomalies.append(anomaly_categories[i % len(anomaly_categories)])
    random.shuffle(assigned_anomalies)

    all_events: List[Dict[str, Any]] = []
    ground_truth: Dict[str, Dict[str, Any]] = {}

    base_time = datetime(2026, 10, 20, 8, 0, 0)
    event_counter = 1000

    # 1. Generate Clean Journeys
    for i in range(1, num_clean + 1):
        sample_id = f"SMP-{i:04d}"
        journey_start = base_time + timedelta(minutes=random.randint(0, 1440))
        curr_time = journey_start

        ground_truth[sample_id] = {
            "sample_id": sample_id,
            "has_anomaly": False,
            "anomaly_types": [],
            "expected_findings": 0,
            "description": "Standard nominal diagnostic workflow.",
        }

        # Lifecycle sequence
        lifecycle = [
            EventType.COLLECTION,
            EventType.TRANSPORT_DISPATCH,
            EventType.RECEIVING,
            EventType.ACCESSIONING,
            EventType.ANALYSIS,
            EventType.REPORTING,
        ]

        for stage in lifecycle:
            event_counter += 1
            curr_time += timedelta(minutes=random.randint(15, 60))
            all_events.append({
                "event_id": f"EVT-{event_counter}",
                "sample_id": sample_id,
                "event_type": stage.value,
                "source_system": SOURCE_SYSTEMS[stage],
                "timestamp": curr_time.isoformat(),
                "operator_id": random.choice(OPERATORS),
                "metadata": json.dumps({"barcode_scan": sample_id, "temperature_c": 4.1}),
            })

    # 2. Generate Anomaly Journeys
    for idx, anomaly_type in enumerate(assigned_anomalies, start=num_clean + 1):
        sample_id = f"SMP-{idx:04d}"
        journey_start = base_time + timedelta(minutes=random.randint(0, 1440))
        curr_time = journey_start

        ground_truth[sample_id] = {
            "sample_id": sample_id,
            "has_anomaly": True,
            "anomaly_types": [anomaly_type.value],
            "expected_findings": 1,
            "description": f"Engineered anomaly: {anomaly_type.value}",
        }

        lifecycle = [
            EventType.COLLECTION,
            EventType.TRANSPORT_DISPATCH,
            EventType.RECEIVING,
            EventType.ACCESSIONING,
            EventType.ANALYSIS,
            EventType.REPORTING,
        ]

        sample_events: List[Dict[str, Any]] = []

        if anomaly_type == FindingType.MISSING_EVENT:
            # Omit ACCESSIONING or RECEIVING stage
            omitted = EventType.ACCESSIONING
            for stage in lifecycle:
                if stage == omitted:
                    continue
                event_counter += 1
                curr_time += timedelta(minutes=random.randint(15, 60))
                sample_events.append({
                    "event_id": f"EVT-{event_counter}",
                    "sample_id": sample_id,
                    "event_type": stage.value,
                    "source_system": SOURCE_SYSTEMS[stage],
                    "timestamp": curr_time.isoformat(),
                    "operator_id": random.choice(OPERATORS),
                    "metadata": json.dumps({"barcode_scan": sample_id}),
                })

        elif anomaly_type == FindingType.DUPLICATE_EVENT:
            # Duplicate the ACCESSIONING event
            for stage in lifecycle:
                event_counter += 1
                curr_time += timedelta(minutes=random.randint(15, 60))
                sample_events.append({
                    "event_id": f"EVT-{event_counter}",
                    "sample_id": sample_id,
                    "event_type": stage.value,
                    "source_system": SOURCE_SYSTEMS[stage],
                    "timestamp": curr_time.isoformat(),
                    "operator_id": random.choice(OPERATORS),
                    "metadata": json.dumps({"barcode_scan": sample_id}),
                })
                if stage == EventType.ACCESSIONING:
                    event_counter += 1
                    # Immediate duplicate scan 2 mins later
                    sample_events.append({
                        "event_id": f"EVT-{event_counter}",
                        "sample_id": sample_id,
                        "event_type": stage.value,
                        "source_system": SOURCE_SYSTEMS[stage],
                        "timestamp": (curr_time + timedelta(minutes=2)).isoformat(),
                        "operator_id": random.choice(OPERATORS),
                        "metadata": json.dumps({"barcode_scan": sample_id, "retry_flag": True}),
                    })

        elif anomaly_type == FindingType.TIMESTAMP_CONFLICT:
            # Invert timestamp: ANALYSIS timestamp earlier than COLLECTION
            col_time = curr_time + timedelta(hours=2)
            for stage in lifecycle:
                event_counter += 1
                if stage == EventType.COLLECTION:
                    ts = col_time
                elif stage == EventType.ANALYSIS:
                    # Occurred 1 hour before collection!
                    ts = col_time - timedelta(hours=1)
                else:
                    curr_time += timedelta(minutes=30)
                    ts = curr_time

                sample_events.append({
                    "event_id": f"EVT-{event_counter}",
                    "sample_id": sample_id,
                    "event_type": stage.value,
                    "source_system": SOURCE_SYSTEMS[stage],
                    "timestamp": ts.isoformat(),
                    "operator_id": random.choice(OPERATORS),
                    "metadata": json.dumps({"barcode_scan": sample_id}),
                })

        elif anomaly_type == FindingType.INVALID_SEQUENCE:
            # Swap ANALYSIS and ACCESSIONING order
            reordered = [
                EventType.COLLECTION,
                EventType.TRANSPORT_DISPATCH,
                EventType.RECEIVING,
                EventType.ANALYSIS,  # Run testing BEFORE accessioning
                EventType.ACCESSIONING,
                EventType.REPORTING,
            ]
            for stage in reordered:
                event_counter += 1
                curr_time += timedelta(minutes=random.randint(15, 45))
                sample_events.append({
                    "event_id": f"EVT-{event_counter}",
                    "sample_id": sample_id,
                    "event_type": stage.value,
                    "source_system": SOURCE_SYSTEMS[stage],
                    "timestamp": curr_time.isoformat(),
                    "operator_id": random.choice(OPERATORS),
                    "metadata": json.dumps({"barcode_scan": sample_id}),
                })

        elif anomaly_type == FindingType.SAMPLE_ID_MISMATCH:
            # Barcode scan has wrong identifier at ACCESSIONING stage
            for stage in lifecycle:
                event_counter += 1
                curr_time += timedelta(minutes=random.randint(15, 60))
                mismatch_barcode = f"SMP-{random.randint(9000, 9999)}" if stage == EventType.ACCESSIONING else sample_id
                sample_events.append({
                    "event_id": f"EVT-{event_counter}",
                    "sample_id": sample_id,
                    "event_type": stage.value,
                    "source_system": SOURCE_SYSTEMS[stage],
                    "timestamp": curr_time.isoformat(),
                    "operator_id": random.choice(OPERATORS),
                    "metadata": json.dumps({"barcode_scan": mismatch_barcode}),
                })

        all_events.extend(sample_events)

    return all_events, ground_truth


def save_dataset_files(
    events: List[Dict[str, Any]], ground_truth: Dict[str, Dict[str, Any]]
) -> None:
    """Save synthetic CSV and ground truth JSON files."""
    df = pd.DataFrame(events)
    df.to_csv(CSV_PATH, index=False)

    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated {len(df)} events across {len(ground_truth)} samples.")
    print(f"Saved CSV to: {CSV_PATH}")
    print(f"Saved Ground Truth to: {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    events, gt = generate_synthetic_dataset(total_samples=150, seed=42)
    save_dataset_files(events, gt)
