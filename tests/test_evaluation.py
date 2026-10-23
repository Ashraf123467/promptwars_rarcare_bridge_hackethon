"""Unit tests for evaluation metrics and baselines."""

import pytest
from evaluation.evaluate import compute_metrics, run_evaluation


def test_compute_metrics_perfect():
    """Test perfect precision and recall calculation."""
    ground_truth = {
        "S1": {"has_anomaly": True},
        "S2": {"has_anomaly": False},
        "S3": {"has_anomaly": True},
    }
    predictions = {
        "S1": True,
        "S2": False,
        "S3": True,
    }
    metrics = compute_metrics(predictions, ground_truth)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["accuracy"] == 1.0
    assert metrics["tp"] == 2
    assert metrics["tn"] == 1
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


def test_compute_metrics_with_errors():
    """Test metrics with false positives and false negatives."""
    ground_truth = {
        "S1": {"has_anomaly": True},
        "S2": {"has_anomaly": False},
        "S3": {"has_anomaly": True},
        "S4": {"has_anomaly": False},
    }
    predictions = {
        "S1": True,   # TP
        "S2": True,   # FP
        "S3": False,  # FN
        "S4": False,  # TN
    }
    metrics = compute_metrics(predictions, ground_truth)
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["tn"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["accuracy"] == 0.5


def test_full_evaluation_runs():
    """Ensure the full evaluation run completes and produces valid metrics."""
    results = run_evaluation()
    assert results["dataset_size"] > 0
    assert "ecere" in results
    assert "naive" in results
    assert results["ecere"]["f1"] >= results["naive"]["f1"]
