# GB Road Safety Dashboard

This project implements a reproducible data engineering pipeline and interactive dashboard for Great Britain's Road Safety Data (STATS19). It provides a Python + DuckDB-based alternative to existing R tooling, emphasizing analytic schema design, data quality enforcement, and interactive query performance.

## Data Pipeline & Design Decisions

### 1. ETL Architecture
We treat the official DfT specifications and the `stats19` R package schema as reference standards, while implementing an independent Python pipeline:

- **Ingestion**: Raw DfT CSVs are processed with Pandas (we filter to `2000–2024` by default).
- **Cleaning + Feature Engineering**: Dataset-specific cleaning is applied, and derived time features are added (e.g., `year`, `month_num`, `day_of_week`, `hour`).
- **Schema Reference / Code Mapping**: We materialize a `code_map` dimension table from the DfT schema (CSV preferred; RDA fallback supported) and use it to validate/interpret categorical codes.
- **Storage**: Cleaned outputs are written to DuckDB (`road_safety.duckdb`) for fast OLAP-style analytics. Geometry fields (if present) are stored as WKT strings for portability.

### 2. Analytic Schema Design
To support interactive dashboard queries, we transform raw transactional tables into an analytic schema:

- **Fact Tables**: `collision`, `vehicle`, and `casualty` are linked via `collision_index`.
- **Optional Master Join**: The pipeline can also export a merged `master_dataset.csv` for offline analysis; the dashboard primarily relies on the normalized fact tables plus precomputed aggregates.
- **Indexes for Common Access Paths**: We create DuckDB indexes on key columns (e.g., `collision_index`, `year`) to accelerate joins and filters.

### 3. Performance: Materialized Aggregates (Pre-aggregation)
To reduce repeated scans over large fact tables, we materialize several small aggregate tables during ETL:

- **`kpi_monthly`**: monthly totals by severity (collisions, casualties, vehicles) plus adjusted-severity columns.
- **`kpi_daily`**: daily totals by severity, with an index on `date` when supported.
- **`by_hour` / `by_dow`**: distributions by hour-of-day and day-of-week (by severity).
- **`collision_geopoints`**: a “map-ready” projection table containing lat/long + selected fields for fast plotting and filtering.

These tables trade a small amount of additional storage for substantial speedups in interactive KPI queries (reading hundreds/thousands of rows instead of scanning millions).

**Updates / refresh policy**: When new data is added or corrected, rerunning the ETL pipeline rebuilds the DuckDB tables and all materialized aggregates via `CREATE OR REPLACE`, ensuring consistency. (The design can be extended to incremental refresh by year/month partitions.)

#### Why not pre-join everything?
We avoid materializing a single denormalized “wide” table for all dashboard queries because it can significantly increase storage (duplicated decoded attributes across many rows). Instead, we keep normalized fact tables plus small materialized aggregates for the most common KPIs.

### 4. Data Quality Assurance
Quality checks are enforced during ETL and validated via `pytest`:

- **Referential Integrity**: Orphaned `vehicle` / `casualty` rows without a valid `collision_index` are dropped to enforce FK consistency.
- **Coordinate Validity**: Latitude/longitude are validated to fall within Great Britain bounds; only valid coordinates are included in `collision_geopoints`.
- **Schema Consistency**: Categorical codes are validated against `code_map` to prevent undefined codes from entering the analysis.

## Setup and Usage

1. **Environment Setup**
   Ensure Python 3.11+ is installed. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. **Download Data**  
   Download the raw STATS19 datasets (Collision, Vehicle, Casualty) from the DfT website:
   ```bash
   python src/etl/download.py
   ```
3. **Run ETL Pipeline**
   Process raw data, run quality checks, and generate the DuckDB database:
   ```bash
   python clean_stats19.py
   ```
4. **Run Tests**
   Verify data quality and schema integrity:
   ```bash
   pytest tests/test_etl.py
   ```
5. **Launch Dashboard**
   Start the Streamlit application:
   ```bash
   streamlit run app.py
   ```

## Project Structure
   The project is organized into a modular structure under the src/ directory:
   - **src/etl/**: ETL pipeline logic (cleaning, transformation, loading).
   - **src/dashboard/**: Streamlit dashboard (tabs/components/data access).
   - **src/shared/**: Shared utilities and configuration.
   - **clean_stats19.py**: ETL entry point.
   - **app.py**: Dashboard entry point.
