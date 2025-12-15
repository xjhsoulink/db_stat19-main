# GB Road Safety Dashboard

This project implements a reproducible data engineering pipeline and interactive dashboard for Great Britain's Road Safety Data (STATS19). It provides a Python and DuckDB-based alternative to existing R tools, focusing on analytic schema design and interactive performance.

## Data Pipeline & Design Decisions

### 1. ETL Architecture
We treat the official DfT specifications and the `stats19` R package as reference standards but implement an independent pipeline:
- **Ingestion**: Raw CSVs (2000-2024) are processed using Pandas.
- **Standardization**: Column names are normalized to snake_case; categorical integers are decoded using a materialized `code_map` dimension table.
- **Storage**: Cleaned data is stored in DuckDB, a high-performance in-process SQL OLAP database.

### 2. Analytic Schema Design
To support interactive queries, we transformed the raw transactional data into an analytic schema:
- **Fact Tables**: `collision`, `vehicle`, and `casualty` tables are linked via `collision_index`.
- **Pre-aggregation**: A `kpi_monthly` table is generated during ETL. This table pre-calculates collision, casualty, and vehicle counts by severity, reducing dashboard KPI query times from scanning millions of rows to reading a few hundred.

### 3. Data Quality Assurance
Automated quality checks are enforced during the ETL process and verified via `pytest`:
- **Referential Integrity**: Orphaned vehicle and casualty records (those missing a valid `collision_index`) are automatically identified and dropped during the ETL process.
- **Coordinate Validity**: Geospatial checks ensure latitude/longitude coordinates fall within valid Great Britain bounds.
- **Schema Consistency**: Categorical values are validated against the defined `code_map` to ensure no undefined codes enter the analysis.

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

The project is organized into a modular structure under the `src/` directory:

- `src/etl/`: Contains the ETL pipeline logic (cleaning, transformation, loading).
- `src/dashboard/`: Contains the Streamlit dashboard application (components, tabs, data fetching).
- `src/shared/`: Shared utilities and configuration.
- `clean_stats19.py`: Entry point for the ETL pipeline.
- `app.py`: Entry point for the Dashboard.
