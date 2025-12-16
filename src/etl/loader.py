# src/etl/loader.py

import duckdb
import pandas as pd

gpd = None
GEO_DATAFRAME_TYPE = None
try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
    GEO_DATAFRAME_TYPE = gpd.GeoDataFrame
except ImportError:
    HAS_GEOPANDAS = False


def save_to_duckdb(cleaned_dfs: dict[str, pd.DataFrame], db_path: str) -> None:
    """
    Saves cleaned dataframes to a DuckDB database file.

    cleaned_dfs: dict, e.g. {"collision": df_collision, "vehicle": df_vehicle, ...}
    db_path: path to road_safety.duckdb
    """
    print(f"Creating DuckDB database at {db_path}...")
    con = duckdb.connect(str(db_path))

    try:
        # -----------------------------
        # 1) Load cleaned tables
        # -----------------------------
        for name, df in cleaned_dfs.items():
            df_export = df.copy()

            # If geometry exists (GeoDataFrame or "geometry" column),
            # store it as WKT string for portability.
            if (GEO_DATAFRAME_TYPE is not None and isinstance(df_export, GEO_DATAFRAME_TYPE)) or (
                "geometry" in df_export.columns
            ):
                if "geometry" in df_export.columns:
                    non_null = df_export["geometry"].dropna()
                    first_valid = non_null.iloc[0] if not non_null.empty else None

                    if first_valid is not None and hasattr(first_valid, "wkt"):
                        df_export["geometry"] = df_export["geometry"].apply(
                            lambda x: x.wkt if (x is not None and hasattr(x, "wkt")) else None
                        )
                    else:
                        df_export["geometry"] = df_export["geometry"].astype(str)

            # Convert object columns to string to avoid mixed-type issues in DuckDB
            for col in df_export.columns:
                if df_export[col].dtype == "object":
                    df_export[col] = df_export[col].astype(str)

            con.register("temp_df", df_export)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM temp_df")
            con.unregister("temp_df")

        # -----------------------------
        # 2) Pre-aggregated tables (existing)
        # -----------------------------
        print("Creating pre-aggregated tables (kpi_monthly, by_hour, by_dow, collision_geopoints, kpi_daily)...")

        con.execute(
            """
            CREATE OR REPLACE TABLE kpi_monthly AS
            SELECT 
                year, 
                month_num, 
                month, 
                SUM(CASE WHEN collision_severity = 'Fatal' THEN 1 ELSE 0 END) as fatal,
                SUM(CASE WHEN collision_severity = 'Serious' THEN 1 ELSE 0 END) as serious,
                SUM(CASE WHEN collision_severity = 'Slight' THEN 1 ELSE 0 END) as slight,
                SUM(CASE WHEN collision_severity = 'Fatal' THEN number_of_casualties ELSE 0 END) as fatal_casualties,
                SUM(CASE WHEN collision_severity = 'Serious' THEN number_of_casualties ELSE 0 END) as serious_casualties,
                SUM(CASE WHEN collision_severity = 'Slight' THEN number_of_casualties ELSE 0 END) as slight_casualties,
                SUM(CASE WHEN collision_severity = 'Fatal' THEN number_of_vehicles ELSE 0 END) as fatal_vehicles,
                SUM(CASE WHEN collision_severity = 'Serious' THEN number_of_vehicles ELSE 0 END) as serious_vehicles,
                SUM(CASE WHEN collision_severity = 'Slight' THEN number_of_vehicles ELSE 0 END) as slight_vehicles,
                SUM(CASE WHEN collision_severity = 'Fatal' THEN 1 ELSE 0 END) as adj_fatal,
                SUM(collision_adjusted_severity_serious) as adj_serious,
                SUM(collision_adjusted_severity_slight) as adj_slight
            FROM collision 
            GROUP BY year, month_num, month
            ORDER BY year, month_num
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TABLE by_hour AS
            SELECT 
                hour, 
                collision_severity, 
                COUNT(*) as count 
            FROM collision 
            WHERE hour IS NOT NULL
            GROUP BY hour, collision_severity
            ORDER BY hour
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TABLE by_dow AS
            SELECT 
                day_of_week, 
                collision_severity, 
                COUNT(*) as count 
            FROM collision 
            WHERE day_of_week IS NOT NULL
            GROUP BY day_of_week, collision_severity
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TABLE collision_geopoints AS
            SELECT 
                latitude, 
                longitude,
                year,
                month_num,
                collision_severity,
                date,
                time,
                number_of_casualties,
                number_of_vehicles,
                road_type,
                weather_conditions,
                light_conditions
            FROM collision 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        )

        print("Creating kpi_daily (daily aggregated KPI table)...")
        con.execute(
            """
            CREATE OR REPLACE TABLE kpi_daily AS
            SELECT
                date::DATE                AS date,
                year,
                month_num,
                collision_severity,
                COUNT(*)                  AS collisions,
                SUM(number_of_casualties) AS casualties,
                SUM(number_of_vehicles)   AS vehicles
            FROM collision
            GROUP BY date, year, month_num, collision_severity
            ORDER BY date;
            """
        )

        # -----------------------------
        # 3) Scheme A: geo_events_raw (NEW)
        # -----------------------------
        # This is a "raw geo fact table" used by the Hotspots tab.
        # We do NOT pre-materialize grid tables with a fixed GRID_SCALE.
        # Instead, the dashboard dynamically bins points into neighborhoods
        # using a user-selected grid size at query time.
        print("Creating geo_events_raw (raw geo fact table for dynamic neighborhood aggregation)...")
        con.execute(
            """
            CREATE OR REPLACE TABLE geo_events_raw AS
            SELECT
                latitude,
                longitude,
                date,
                year,
                month_num,
                collision_severity,
                weather_conditions,
                light_conditions,
                road_type,
                number_of_casualties AS casualties,
                number_of_vehicles   AS vehicles
            FROM collision
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
            """
        )

        # Optional indexes to speed up filters (DuckDB indexing support may vary by version)
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_geo_events_raw_year ON geo_events_raw(year);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_geo_events_raw_month ON geo_events_raw(month_num);")
            # date might be stored as string; we still can query with date::DATE in SQL.
            con.execute("CREATE INDEX IF NOT EXISTS idx_geo_events_raw_date ON geo_events_raw(date);")
            print("[opt] indexed geo_events_raw(year, month_num, date)")
        except Exception as e:
            print(f"[opt] Could not index geo_events_raw: {e}")

        # -----------------------------
        # 4) Optimizations / Indexes (existing)
        # -----------------------------
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_kpi_daily_date ON kpi_daily(date);")
            print("[opt] CREATE INDEX idx_kpi_daily_date ON kpi_daily(date);")
        except Exception as e:
            print(f"[opt] Could not create index on kpi_daily: {e}")

        try:
            con.execute("PRAGMA threads=4;")
            print("[opt] Set DuckDB threads = 4")
        except Exception as e:
            print(f"[opt] Could not set threads pragma: {e}")

        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_collision_index ON collision(collision_index);",
            "CREATE INDEX IF NOT EXISTS idx_vehicle_collision_index ON vehicle(collision_index);",
            "CREATE INDEX IF NOT EXISTS idx_casualty_collision_index ON casualty(collision_index);",
            "CREATE INDEX IF NOT EXISTS idx_collision_year ON collision(year);",
        ]

        for stmt in index_statements:
            try:
                con.execute(stmt)
                print(f"[opt] {stmt}")
            except Exception as e:
                print(f"[opt] Failed to run '{stmt}': {e}")

        print("DuckDB database created successfully.")

    finally:
        con.close()
