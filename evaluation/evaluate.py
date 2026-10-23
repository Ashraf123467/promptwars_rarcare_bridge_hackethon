"""Evaluation harness for comparing reconciliation performance against ground truth."""

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import EventLog, EventType
from core.reconciliation_engine import ReconciliationEngine
from evaluation.baselines import NaiveRuleBaseline

DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "synthetic_events.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"


def load_dataset() -> Tuple[List[EventLog], Dict[str, Any]]:
    """Load synthetic events and ground truth."""
    if not CSV_PATH.exists() or not GROUND_TRUTH_PATH.exists():
        from data.generator import generate_synthetic_dataset, save_dataset_files
        events_raw, gt_data = generate_synthetic_dataset()
        save_dataset_files(events_raw, gt_data)

    df = pd.read_csv(CSV_PATH)
    events: List[EventLog] = []
    for _, row in df.iterrows():
        meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {}
        events.append(
            EventLog(
                event_id=str(row["event_id"]),
                sample_id=str(row["sample_id"]),
                event_type=EventType(row["event_type"]),
                source_system=str(row["source_system"]),
                timestamp=datetime.fromisoformat(str(row["timestamp"])),
                operator_id=str(row.get("operator_id", "SYSTEM")),
                metadata=meta,
            )
        )

    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    return events, ground_truth


def compute_metrics(predictions: Dict[str, bool], ground_truth: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Calculate Precision, Recall, F1, Accuracy, TP, FP, TN, FN."""
    tp = fp = tn = fn = 0
    
    for sample_id, gt_info in ground_truth.items():
        actual = gt_info["has_anomaly"]
        predicted = predictions.get(sample_id, False)

        if actual and predicted:
            tp += 1
        elif not actual and predicted:
            fp += 1
        elif actual and not predicted:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(ground_truth) if ground_truth else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "total_samples": len(ground_truth),
    }


def run_evaluation() -> Dict[str, Any]:
    """Run comparative benchmark of Reconciliation Engine vs Naive Baseline."""
    events, ground_truth = load_dataset()

    # 1. Evaluate Reconciliation Engine (ECERE)
    engine = ReconciliationEngine()
    ecere_findings = engine.reconcile_all(events)
    ecere_preds = {sid: len(findings) > 0 for sid, findings in ecere_findings.items()}
    # Fill in clean samples with False if not present
    for sid in ground_truth:
        if sid not in ecere_preds:
            ecere_preds[sid] = False
    ecere_metrics = compute_metrics(ecere_preds, ground_truth)

    # 2. Evaluate Naive Baseline
    naive = NaiveRuleBaseline()
    naive_findings = naive.reconcile_all(events)
    naive_preds = {sid: len(findings) > 0 for sid, findings in naive_findings.items()}
    for sid in ground_truth:
        if sid not in naive_preds:
            naive_preds[sid] = False
    naive_metrics = compute_metrics(naive_preds, ground_truth)

    return {
        "dataset_size": len(ground_truth),
        "total_events": len(events),
        "ecere": ecere_metrics,
        "naive": naive_metrics,
    }


if __name__ == "__main__":
    results = run_evaluation()
    print("=" * 60)
    print("LABTRACE AI EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Samples: {results['dataset_size']} | Total Events: {results['total_events']}")
    print("-" * 60)
    print(f"{'Metric':<20} | {'Naive Baseline':<15} | {'ECERE Engine':<15}")
    print("-" * 60)
    for m in ["precision", "recall", "f1", "accuracy", "tp", "fp", "fn", "tn"]:
        print(f"{m.upper():<20} | {str(results['naive'][m]):<15} | {str(results['ecere'][m]):<15}")
    print("=" * 60)
