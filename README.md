# GB Road Safety Dashboard (STATS19)

A reproducible data engineering pipeline + interactive dashboard for Great Britain road safety data (DfT STATS19).  
This project focuses on **analytic schema design**, **data quality enforcement**, and **interactive query / visualization performance** using a Python-first stack.

---

## What’s in this repo

### End-to-end workflow
1. Download raw DfT STATS19 CSVs (Collision / Vehicle / Casualty)
2. Clean + standardize + feature engineer (time fields, age groups, coordinate checks, etc.)
3. Enforce referential integrity (drop orphan records)
4. Export analysis-ready outputs:
   - cleaned fact tables (Collision / Vehicle / Casualty)
   - optional merged `master_dataset.csv` for offline analysis
   - (optional) DuckDB database + materialized aggregates for fast dashboard queries

### Dashboard highlights (new)
- **Hotspots (Map-based exploration)**  
  Explore collision hotspots on an interactive map with filters (e.g., year/severity and other fields).  
  Optional “click-to-select / recenter” interaction is supported when `folium` + `streamlit-folium` are installed.

- **Condition-aware Hotspots (Map + context filters)**  
  A more advanced hotspot view that lets you analyze hotspots **under specific conditions** (e.g., weather/road/lighting-like attributes if present in your cleaned tables), enabling “apples-to-apples” comparisons.

> Note: some interactions are intentionally two-step (select / filter first, then render charts/tables below) to avoid expensive re-renders over millions of rows.

---

## Data model (Analytic schema)

We model STATS19 as a normalized analytic schema with three core fact tables:

- `collision` (accident-level / collision-level facts, time fields, coordinates)
- `vehicle` (vehicle records associated with a collision)
- `casualty` (casualty records associated with a collision)

### Keys / relationships
The three fact tables are linked by the official STATS19 collision identifier
(commonly named `accident_index` in raw DfT files; some pipelines rename it to `collision_index`).

This pipeline enforces:
- `vehicle.[key]` → `collision.[key]`
- `casualty.[key]` → `collision.[key]`

Any orphaned `vehicle` / `casualty` rows without a valid collision key are dropped during ETL.

---

## Temporal filtering (2000–2024)

By default, we target `2000–2024`:

- If a table has a reliable date/year field (typically `collision`), we filter directly by year.
- If a table does **not** have a reliable date/year field (often `vehicle` / `casualty`), we enforce the same year range by **key cascading**:
  keep only records whose collision key exists in the filtered `collision` table.

This keeps the three tables consistent without relying on missing/unstable year columns.

---

## Data quality checks

During ETL (and in tests), we enforce:

- **Referential integrity**: drop orphan `vehicle` / `casualty` rows without a valid collision key
- **Coordinate validity**: validate lat/long ranges (GB bounds) for map-ready outputs
- **Schema consistency**: categorical codes can be validated/decoded via a materialized `code_map` dimension

---

## Outputs

After running ETL, you should expect artifacts under `data/cleaned/` (paths may vary):

- Cleaned fact tables (CSV):
  - `...collision...csv`
  - `...vehicle...csv`
  - `...casualty...csv`
- Optional denormalized export:
  - `master_dataset.csv` (collision joined with vehicle/casualty fields as configured)

If your configuration enables DuckDB loading, you may also get:
- `road_safety.duckdb` containing normalized facts + (optional) aggregates

---


## Setup and Usage

1. **Environment Setup**
   Ensure Python 3.11+ is installed. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Download Data**  
   Download the raw STATS19 datasets (Collision, Vehicle, Casualty) from the DfT website:
   ```bash
   python src/etl/download.py
   ```
4. **Run ETL Pipeline**
   Process raw data, run quality checks, and generate the DuckDB database:
   ```bash
   python clean_stats19.py
   ```
5. **Run Tests**
   Verify data quality and schema integrity:
   ```bash
   pytest tests/test_etl.py
   ```
6. **Launch Dashboard**
   Start the Streamlit application:
   ```bash
   streamlit run app.py
   ```

## Repo structure

- `src/etl/` — ingestion, cleaning, transformation, loading
- `src/dashboard/` — Streamlit UI + tabs
  - `src/dashboard/tabs/hotspots.py` — hotspot map exploration
  - `src/dashboard/tabs/conditionawarehotspots.py` — condition-aware hotspot analysis
- `src/shared/` — shared utilities / config
- `clean_stats19.py` — ETL entry point
- `app.py` — Streamlit entry point
- `tests/` — ETL / data quality tests
- `ref/` — reference schema / metadata (DfT spec, code maps, etc.)

## Notes on large data

STATS19 can be large (tens of millions of rows across decades). Recommended practices:

- Prefer filtering by year range early (collision) and cascade by key for consistency
- Use pre-aggregations (monthly/daily/hourly/dow) or DuckDB queries for interactive speed
- Avoid rendering full-resolution maps without sampling or filtering

## License / attribution

- Data source: UK Department for Transport (DfT) STATS19
- Schema reference: DfT specifications and `stats19` R package conventions (used as reference standard)

