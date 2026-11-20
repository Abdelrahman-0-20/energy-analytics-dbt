# Energy Analytics dbt Pipeline

[![ELT pipeline](https://github.com/Abdelrahman-0-20/energy-analytics-dbt/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdelrahman-0-20/energy-analytics-dbt/actions/workflows/ci.yml)
[![dbt docs](https://img.shields.io/badge/docs-dbt%20lineage-blue)](https://abdelrahman-0-20.github.io/energy-analytics-dbt/)
[![Live demo](https://img.shields.io/badge/live%20demo-streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://energy-analytics-dbt-pactrkas7ao69jwbh6ykhg.streamlit.app)

Project #3 of a [data engineering portfolio](https://github.com/Abdelrahman-0-20/api-ingestion-pipeline)
(companions: [API ingestion pipeline](https://github.com/Abdelrahman-0-20/api-ingestion-pipeline) ·
[analytics engineering pipeline](https://github.com/Abdelrahman-0-20/analytics-engineering-pipeline)).

**ELT done the modern way:** public [OWID energy data](https://github.com/owid/energy-data)
(314 entities × 130 metrics, 1900–2025) → pinned raw layer in **DuckDB** →
**dbt** models across staging → intermediate → marts → **46 data tests** →
scheduled by **GitHub Actions** → **dbt docs** with lineage published to
**GitHub Pages** → Streamlit dashboard over the gold layer. No API keys, no
cloud accounts, no services to run.

**At a glance:** 23,377 entity-years · 314 entities (220 countries) · 9 dbt
models · 46 data tests + 2 freshness checks green in ~3 s · loader rerun is
byte-identical (ingest log: `unchanged`) · second `dbt build` changes **zero**
rows across all 8 tables (CI enforces this) · 50-column data contract on the
raw layer.

## Architecture

```
data/raw/*.csv                 pinned to upstream commit SHAs, fetched once
        │  src/fetch.py — idempotent download (atomic .part → rename)
        ▼
raw_energy 23,377×130   raw_countries 249×11   ingest_log (insert-once)
        │  src/load.py — CREATE OR REPLACE (byte-identical rerun)
        │  └─ data contract: refuses any file missing one of 50 required columns
        ▼
dbt sources (freshness: warn 7d / error 30d on _ingested_at)
        │
        ├─ staging/     stg_energy · stg_countries              (views)
        ├─ intermediate/ int_energy_long  — 9 sources unpivoted via macro
        └─ marts/       dim_entities · dim_years                (tables)
                        fct_energy_year   ← incremental, merge on surrogate key
                        mart_energy_mix · mart_renewable_transition
                        mart_energy_snapshot
        │
        ├─ 46 data tests + 4 singular tests (reconciliation, referential
        │   integrity, coverage guard, vetted allow-list)
        ├─ dbt docs → GitHub Pages (clickable lineage graph)
        ├─ dashboard/app.py — Streamlit, reads marts.* only
        └─ scripts/prove_idempotency.py — CI reruns dbt build, diffs counts
```

## Run it

All commands run from the repo root — the loader and dbt must share one
warehouse path, so dbt is pointed at `dbt/` explicitly:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.pipeline                  # fetch (pinned, idempotent) → raw tables
python -m pytest -q                     # 10 loader tests: contract, idempotency, drift

dbt deps --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt        # 9 models + 46 tests
python scripts/prove_idempotency.py     # rerun must change nothing (CI enforces)
dbt source freshness --project-dir dbt --profiles-dir dbt

dbt docs generate --project-dir dbt --profiles-dir dbt
dbt docs serve --project-dir dbt --profiles-dir dbt   # lineage at localhost:8080

streamlit run dashboard/app.py          # gold layer only
python -m src.export_marts             # publish gold marts as CSVs (CI does this too)
```

**Live demo:** [energy-analytics-dbt-pactrkas7ao69jwbh6ykhg.streamlit.app](https://energy-analytics-dbt-pactrkas7ao69jwbh6ykhg.streamlit.app)

**Deploying the dashboard?** `warehouse/*.duckdb` is gitignored (it is a build
artifact), so Streamlit Community Cloud would never see it. CI exports the
dashboard's gold marts to `dashboard/data/*.csv` and commits them back with
`[skip ci]`; the app reads CSVs when the warehouse is absent and the live
warehouse when present. Connect the repo on
[share.streamlit.io](https://share.streamlit.io) and it just works.

## dbt project tour

| Layer | Model | What it proves |
|---|---|---|
| staging | `stg_energy` | 130 raw columns → typed, renamed, explicit contract in SQL |
| staging | `stg_countries` | hyphenated ISO columns made SQL-safe |
| intermediate | `int_energy_long` | wide → long unpivot generated from a Jinja column map |
| marts | `dim_entities` | 314 entities classified (country / historical state / aggregate) via **vars** |
| marts | `dim_years` | 1900–2025 spine with a decade axis |
| marts | `fct_energy_year` | **incremental** merge on `entity_year_sk`; `--full-refresh` for history revisions |
| marts | `mart_energy_mix` | long form (93,084 rows) for stacked charts |
| marts | `mart_renewable_transition` | first-observation → latest renewables share, ranked (Iceland +56.7 pp) |
| marts | `mart_energy_snapshot` | latest year per country + per-capita rank |

**Tests are evidence, not decoration** — every threshold was measured on the
pinned release before being asserted:

- `assert_energy_shares_reconcile` — the 9 source consumptions must sum within
  ±5% of reported primary energy (measured: min 95.6%, max 102.9%, **0 outliers
  in 6,379** entity-years)
- `assert_full_country_coverage` — ≥200 distinct countries must survive the load
  (measured: 220) → catches truncated upstream files
- `assert_iso_codes_resolve` — every ISO code must exist in the reference data,
  except vetted withdrawn codes (`ANT`, Netherlands Antilles, dissolved 2010)
- `assert_vetted_unclassified_countries` — rows with no UN M49 region must match
  the allow-list (Antarctica, Taiwan)
- `expect_value_between` — a **custom generic test** that skips NULLs: sparse
  metrics are legitimate, out-of-range values are not

## Design decisions (interview talking points)

| Decision | Why |
|---|---|
| Upstream pinned to commit SHAs | reproducible builds; you bump the pin deliberately, drift can't break CI silently |
| 50-column contract checked in the loader | schema drift must alert at load time, never corrupt gold |
| Raw = `CREATE OR REPLACE` + insert-once ingest log | rerunning is byte-identical: same tables, same `_ingested_at` |
| Explicit Jinja column map for the unpivot | upstream is inconsistent (`other_renewable_consumption` vs `other_renewables_share_energy`) — the trap lives in exactly one place |
| `fct` incremental + `on_schema_change: sync_all_columns` | new release years merge in; new columns follow; revisions need `--full-refresh` |
| Entity classification as dbt **vars** | curated lists are data, not code — tune without touching SQL |
| `generate_schema_name` macro | plain `staging`/`marts` schemas instead of `main_staging` noise |
| Idempotency proof as a CI step | "rerun-safe" is enforced, not claimed |
| Reconciliation test with measured tolerance | a data-quality gate with a number you can defend in an interview |

## Resume line

> Built an ELT pipeline (Python + DuckDB + dbt) transforming the OWID energy
> dataset (23k entity-years × 130 metrics) through typed staging, an
> intermediate unpivot, and 6 gold marts — with 46 dbt tests, a 50-column data
> contract, freshness checks, incremental models, proven rerun idempotency in
> CI, and dbt docs lineage deployed to GitHub Pages.

## Ideas for later

- `snapshots` (SCD 2) for entity metadata across releases
- Alerting when a data test fails (Slack/email webhook)
- dbt `state: modified` + slim CI (`dbt build --select state:modified+`) for PRs
- Replace DuckDB with MotherDuck/Snowflake — the dbt project ports unchanged
