# LabTrace AI 🧬
### Lightweight Diagnostic Sample Event Reconciliation Prototype

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed%20(100%25)-brightgreen.svg)](tests/)
[![Distributable Size](https://img.shields.io/badge/ZIP%20Size-<1%20MB-success.svg)](package_project.py)

---

## 1. Project Overview & Operational Context

In clinical diagnostic laboratories, biological specimens (blood, swabs, tissue biopsies) traverse multiple independent stations: collection clinic, courier transport, central receiving dock, accession desk, robotic analyzer, and physician reporting portal. 

Discrepancies frequently occur across disparate IT systems: missing handoff scans, duplicate barcode records, clock drift between instruments, out-of-order data entry, and barcode alias mismatches.

**LabTrace AI** is a simple, lightweight, prototype-level Streamlit application that detects operational discrepancies across sample event logs, links findings to exact supporting evidence event IDs, and enforces a strict human-in-the-loop approval gate before recording any simulated corrections.

> **CRITICAL SAFETY NOTICE:** LabTrace AI is an operational workflow integrity prototype. It is **NOT** a medical diagnostic or clinical decision support system. It operates purely on synthetic data and **NEVER modifies real laboratory LIS/HIS databases**.

---

## 2. Architecture & 3 Logical Agent Roles

The application is structured into three explicit, lightweight logical agent modules governed by a deterministic Finite State Machine (FSM):

```
[RAW Logs] 
    │
    ▼ (Agent 1: Intake & Validation)
[INGESTED] ──► [VALIDATED]
                   │
                   ▼ (Agent 2: Reconciliation ECERE)
               [RECONCILED] 
                   │
         ┌─────────┴─────────┐
    (No Findings)       (Has Findings)
         │                   │
         ▼                   ▼
[SIMULATED_RESOLVED]   [PENDING_REVIEW]
                             │
                             ▼ (Agent 3: Explanation & Review Gate)
                         [REVIEWED] ──► [SIMULATED_RESOLVED]
```

1. **Agent 1: Intake & Validation Agent (`agents/intake_agent.py`)**
   - Validates CSV/JSON input schemas, mandatory fields (`event_id`, `sample_id`, `event_type`, `source_system`, `timestamp`), and timestamp formats.
   - Transitions state: `RAW` → `INGESTED` → `VALIDATED`.
2. **Agent 2: Reconciliation Agent (`agents/reconciliation_agent.py`)**
   - Executes the deterministic Reconciliation Engine (ECERE).
   - Identifies discrepancies across 5 key anomaly categories, attaching exact `evidence_event_ids`.
   - Transitions state: `VALIDATED` → `RECONCILED` → `PENDING_REVIEW` (or `SIMULATED_RESOLVED` if clean).
3. **Agent 3: Explanation & Review Agent (`agents/review_agent.py`)**
   - Generates structured operational summaries and recommended verification steps.
   - **Offline Mode (Default):** Uses deterministic templates with 100% citation grounding and zero external dependencies.
   - **Gemini Online Mode (Optional):** Supports Google Gemini when an API key is provided, with programmatic citation verification.
   - **Human Approval Gate:** Enforces explicit reviewer identity and written justification before any simulated correction is committed. Never modifies production systems.

---

## 3. Deterministic Reconciliation Engine

The reconciliation engine (`core/reconciliation_engine.py`) performs rule-based temporal and sequence verification across five anomaly types:

| Anomaly Type | Detection Logic | Evidence Linked |
| :--- | :--- | :--- |
| **`MISSING_EVENT`** | Detects omitted mandatory milestones (e.g. testing completed without prior accessioning). | Preceding and succeeding event IDs |
| **`DUPLICATE_EVENT`** | Identifies redundant scans of the same lifecycle stage. | All duplicate event IDs |
| **`TIMESTAMP_CONFLICT`** | Flags preceding stages recorded with timestamps later than succeeding stages (with 60-second clock skew tolerance). | Conflicting event ID pairs |
| **`INVALID_SEQUENCE`** | Identifies out-of-order workflow execution according to clinical lifecycle rules (`COLLECTION` → `TRANSPORT` → `RECEIVING` → `ACCESSIONING` → `ANALYSIS` → `REPORTING`). | Out-of-order event IDs |
| **`SAMPLE_ID_MISMATCH`** | Flags cross-referencing barcode scan mismatches or tube alias inconsistencies. | Culprit event ID with scanned value |

---

## 4. Setup & Running the Application

### Prerequisites
- Python 3.11+
- Standard virtual environment (`venv`)

### Installation (Windows / Linux / macOS)
```bash
# 1. Clone or navigate to the repository directory
cd d:/PROMPTWARS

# 2. Create and activate a clean virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# 3. Install minimal dependencies
pip install -r requirements.txt
```

### Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 5. Actual Test & Empirical Benchmark Results

### Automated Test Suite (Pytest)
Run the automated test suite:
```bash
pytest
```
**Actual Test Results:**
- **Total Tests:** 18 automated tests across `test_reconciliation.py`, `test_agents.py`, `test_state_machine.py`, `test_storage.py`, and `test_evaluation.py`.
- **Pass Rate:** **100% Passed (18/18)** in 7.85s.

### Empirical Benchmark vs Naive Baseline
Evaluated on **150 reproducible synthetic sample journeys** (900 total event logs) generated with seed 42 against independent ground truth (`data/ground_truth.json`):

```bash
python evaluation/evaluate.py
```

| Metric | Naive Rule Baseline | LabTrace AI (ECERE) |
| :--- | :---: | :---: |
| **Precision** | 1.0000 | **1.0000** |
| **Recall** | 0.4082 | **1.0000** |
| **F1-Score** | 0.5797 | **1.0000** |
| **Accuracy** | 80.67% | **100.00%** |
| **True Positives (TP)** | 20 | **49** |
| **False Positives (FP)** | **0** | **0** |
| **False Negatives (FN)** | 29 | **0** |
| **True Negatives (TN)** | 101 | **101** |

*Note: The naive baseline misses 29 out of 49 anomalies because it relies only on crude log counts and adjacent monotonicity, whereas ECERE tracks multi-station lifecycle ordering, cross-referencing barcode IDs, and clock skew tolerance.*

---

## 6. Distributable Package & Size Verification

To verify that the project meets the strict distributable size requirements (< 10 MB, target < 3 MB):

```bash
python package_project.py
```

The packager excludes virtual environments (`.venv`), byte caches (`__pycache__`), pytest caches (`.pytest_cache`), Git repositories (`.git`), and temporary database files.

**Actual ZIP Archive Verification:**
- Archive Name: `labtrace_ai_prototype.zip`
- Archive Size: **~35 KB (0.034 MB)**
- Size Compliance: **PASSED (< 10 MB and well below the 3 MB target)**

---

## 7. Limitations & Honest Engineering Scope

1. **Synthetic Data Sandbox:** The prototype is evaluated on 150–300 synthetic sample journeys modeled after clinical lab workflows. It has not been validated on live hospital electronic medical records.
2. **Simplified Station Topologies:** The lifecycle sequence assumes a linear progression (`COLLECTION` → `TRANSPORT` → `RECEIVING` → `ACCESSIONING` → `ANALYSIS` → `REPORTING`). Complex branches (e.g. reflex testing, aliquoting into multiple sub-tubes, or specimen send-outs to reference labs) require expanding the stage graph.
3. **Simulated State Only:** Approving a correction in the UI updates the local SQLite simulation state and writes an immutable audit record; it deliberately does not transmit modifications to real clinical laboratory analyzers or EHR systems.
