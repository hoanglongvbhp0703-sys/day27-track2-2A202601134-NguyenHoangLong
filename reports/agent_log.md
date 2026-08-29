# AI Agent Decision Log

Log of key design decisions, hypotheses, agent proposals, evidence, and verification during Lab 27.

---

## Decision 1: Data Contract Severity & Quarantine Actions
- **Hypothesis**: Simple pass/fail contract validation is insufficient; critical failures (like duplicate order_id) must block ingestion, while minor type/range drift should quarantine or warn.
- **Prompt / Request to Agent**: Extend `contract_validator.py` to support type checking, freshness, severity classification (`critical`, `warning`, `info`), and action mapping (`block`, `quarantine`, `warn`).
- **Agent Proposal**: Added `_issue` action helper mapping `critical -> block`, `warning -> quarantine`, `info -> warn`. Implemented `type`, `min_length`, and `freshness` validation relative to dataset clock or UTC now.
- **Evidence/Test**: `pytest tests_public` passed. Tested `duplicate_pk` fault; correctly produced `critical` severity with `action: block`.
- **Accept / Reject / Revise**: Accepted.
- **Why**: Provides actionable signals to automated data pipelines to block corrupt data before reaching staging.

---

## Decision 2: dbt Transformation Protection & Revenue Inflation Unit Test
- **Hypothesis**: Generic data tests (`unique`, `not_null`) cannot detect revenue inflation when joining a customer table with multiple active records per customer. A dbt unit test is required.
- **Prompt / Request to Agent**: Write a native dbt unit test for `fct_daily_revenue` that exposes revenue inflation when customer dimension contains 2 active rows for the same customer.
- **Agent Proposal**: Created `dbt_project/models/marts/unit_tests.yml` with `detect_revenue_inflation_on_duplicate_active_customer`. Deduplicated `active_customers` in `fct_daily_revenue.sql` using `select distinct customer_id`.
- **Evidence/Test**: `dbt build` ran 18 nodes including 2 unit tests. The unit test caught the inflation bug when unhedged and passed when deduplicated.
- **Accept / Reject / Revise**: Accepted.
- **Why**: Proactively protects executive revenue metrics against dimension fan-out joins.

---

## Decision 3: Robust Anomaly Detection & Context-Aware Seasonality
- **Hypothesis**: Naive Z-score creates false positives on weekend volume drops (seasonality). MAD (Median Absolute Deviation) combined with segment/day-of-week context provides robust anomaly detection.
- **Prompt / Request to Agent**: Improve `observability/anomaly.py` and `detect_anomaly(method="auto")` to be context-aware and fix zero-MAD division by zero.
- **Agent Proposal**: Fixed zero-MAD handling in `mad_detector`. Enhanced `detect_anomaly` in `auto` mode to check `context["same_segment_history"]` and select MAD when sample size >= 5.
- **Evidence/Test**: Tested `volume_drop` fault (150/600 rows); correctly detected as anomaly (score = 5.53). Public test suite passed.
- **Accept / Reject / Revise**: Accepted.
- **Why**: Prevents false positive alert fatigue while accurately capturing true volume drops.

---

## Decision 4: Multi-Window Burn-Rate Alerting Policy
- **Hypothesis**: Single-window burn rate alerts cause page fatigue on short transient spikes. A multi-window policy (1h and 6h windows) should only page SREs when fast burn is sustained.
- **Prompt / Request to Agent**: Implement `evaluate_multiwindow_burn` in `observability/slo.py` using Google SRE Workbook thresholds.
- **Agent Proposal**: Created multi-window logic: pages SRE (`page: True`, `critical`) only if 1h burn > 14.4 AND 6h burn > 6.0; classifies high 1h burn with low 6h burn as transient spike (`page: False`, `warning`).
- **Evidence/Test**: Added unit tests `test_multiwindow_sustained_fast_burn_pages` and `test_multiwindow_transient_spike_warns_no_page`. All tests passed.
- **Accept / Reject / Revise**: Accepted.
- **Why**: Follows industry SRE best practices for error budget alerting.

---

## Decision 5: Transitive Column Lineage Traversal
- **Hypothesis**: Direct child lineage lookup fails to calculate full blast radius across multiple pipeline layers. BFS traversal is needed for column lineage.
- **Prompt / Request to Agent**: Implement BFS graph traversal in `get_column_downstream` in `observability/lineage.py`.
- **Agent Proposal**: Updated `get_column_downstream` to use deque BFS queue with `seen` set to return all transitive downstream columns without loops.
- **Evidence/Test**: Added `test_transitive_column_downstream` in `test_lineage.py`. Test passed.
- **Accept / Reject / Revise**: Accepted.
- **Why**: Enables precise column-level blast radius determination when upstream schema/column changes occur.
