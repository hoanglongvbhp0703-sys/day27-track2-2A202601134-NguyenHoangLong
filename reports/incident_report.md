# Incident Report — Data Reliability Game Day

## Severity
P1 — High Impact (Critical Data Pipeline & Customer Support Knowledge Base Affected)

## Summary
During the Data Reliability Game Day, three critical data reliability faults occurred across the e-commerce pipeline:
1. Primary key duplication in `orders.csv` causing contract validation failure and downstream metric inflation risk.
2. Sudden volume drop (75% ingestion drop) in `orders.csv` leading to partial data load.
3. Stale Knowledge Base publish timestamps (`kb_documents.jsonl` delayed by >3 hours), leading to RAG Support Agent returning outdated policy refund information.

## Detection
- **Signal**: Data contract validator (`validate_orders`), Z-score & MAD anomaly detectors, and dataset freshness contract checks.
- **First observed time**: 2026-08-29T22:45:00Z
- **SLO Status**: Breached error budget on contract check failures and stale KB freshness window (>60 minutes limit).

## Root Cause Analysis
1. **Duplicate PK (`duplicate_pk`)**: Upstream API/pipeline re-transmitted identical `order_id` batches without deduplication before staging.
2. **Volume Drop (`volume_drop`)**: Ingestion pipeline truncated partial batches, dropping 75% of incoming orders while pipeline status reported `SUCCESS`.
3. **Stale KB (`stale_kb`)**: Knowledge Base sync process failed to publish new refund policies on time, leading to outdated effective documents being consumed by the AI Support Agent.
4. **Revenue Inflation Risk**: Customer dimension (`stg_customers`) contained duplicate active records per customer. SQL join in `fct_daily_revenue` inflated total revenue.

## Evidence
1. `validate_dataframe()` flagged duplicate `order_id` with severity `critical` and action `block`.
2. `detect_anomaly(method="auto")` flagged volume drop from 600 to 150 rows (score = 5.53 > threshold 3.0).
3. `dbt unit_test` exposed revenue doubling (`$100 -> $200`) when duplicate active customer records were joined. Fixed via `select distinct customer_id` in `fct_daily_revenue.sql`.
4. `contracts/kb_contract.yaml` freshness validation flagged delay of 190 minutes (> 60 minutes limit).

## Blast Radius
```text
orders.csv (raw)
└── stg_orders
    └── fct_daily_revenue
        └── CEO Revenue Dashboard

kb_documents.jsonl (raw)
└── KB Validation & Freshness Check
    └── Active KB Index
        └── RAG / Customer Support Agent
```

## Mitigation
1. **Pipeline Blocking & Quarantine**: Automatically block ingestion on `critical` contract failures (`duplicate_pk`).
2. **Deduplication in Transformation**: Added `select distinct customer_id` in `fct_daily_revenue.sql` to protect marts against dimension duplication.
3. **Multi-window Alerting**: Implemented `evaluate_multiwindow_burn` to page SREs on sustained fast burn rates (>14.4 1h burn AND >6.0 6h burn) while suppressing transient spikes.
4. **Knowledge Base Re-sync**: Re-anchored KB document publish timestamps and alerted support team when freshness exceeds 60 minutes.

## Recovery Verification
- [x] Contract healthy: `validate_orders` passes with 0 critical issues on healthy baseline.
- [x] dbt tests healthy: `dbt build` passes all 18 models, generic tests, singular tests, and unit tests.
- [x] Anomaly returned to expected range: MAD and Z-score return `is_anomaly = False` on standard volume.
- [x] SLO healthy / budget understood: Error budget calculation and multiwindow burn policy verified.
- [x] Downstream output verified: CEO dashboard revenue and RAG Support Agent receive verified clean data.

## Prevention / Action Items
| Action | Owner | Deadline | Why |
|---|---|---|---|
| Enforce strict contract validation before staging | Data Infra | 2026-09-05 | Prevent invalid/duplicate data from reaching dbt models |
| Deduplicate active records in all dimensional models | Analytics Eng | 2026-09-05 | Prevent revenue inflation on dimension duplication |
| Implement multiwindow burn rate paging alerts | Reliability Eng | 2026-09-10 | Eliminate alert fatigue from short transient spikes |
| Automated freshness monitoring for KB pipeline | AI Platform | 2026-09-10 | Prevent RAG agent from serving stale refund policies |
