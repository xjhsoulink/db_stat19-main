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
    - cleaned_dfs: dict, e.g. {"collision": df_collision, "vehicle": df_vehicle, ...}
    - db_path: path to road_safety.duckdb
    """
    print(f"Creating DuckDB database at {db_path}...")
    con = duckdb.connect(str(db_path))

    # ========== 1. 把所有 DataFrame 写入 DuckDB ==========
    for name, df in cleaned_dfs.items():
        df_export = df.copy()

        # --- 1.1 处理 GeoDataFrame / geometry 列 ---
        if (GEO_DATAFRAME_TYPE is not None and isinstance(df_export, GEO_DATAFRAME_TYPE)) or (
            "geometry" in df_export.columns
        ):
            if "geometry" in df_export.columns:
                # 看看这一列里有没有真正的 geometry 对象
                non_null = df_export["geometry"].dropna()
                first_valid = non_null.iloc[0] if not non_null.empty else None

                if first_valid is not None and hasattr(first_valid, "wkt"):
                    # 真的有 shapely 几何 → 转成 WKT 字符串
                    df_export["geometry"] = df_export["geometry"].apply(
                        lambda x: x.wkt if (x is not None and hasattr(x, "wkt")) else None
                    )
                else:
                    # 否则当普通对象列，直接转成字符串，避免 UserWarning
                    df_export["geometry"] = df_export["geometry"].astype(str)

        # --- 1.2 DuckDB 不喜欢混类型的 object 列 → 统一转成 str ---
        for col in df_export.columns:
            if df_export[col].dtype == "object":
                df_export[col] = df_export[col].astype(str)

        # --- 1.3 注册临时表写入 DuckDB ---
        con.register("temp_df", df_export)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM temp_df")
        con.unregister("temp_df")

    # ========== 2. 创建预聚合表 ==========
    print("Creating pre-aggregated tables (kpi_monthly, by_hour, by_dow)...")

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
    con.execute("""
        CREATE OR REPLACE TABLE kpi_daily AS
        SELECT
            date::DATE           AS date,
            year,
            month_num,
            collision_severity,
            COUNT(*)             AS collisions,
            SUM(number_of_casualties) AS casualties,
            SUM(number_of_vehicles)   AS vehicles
        FROM collision
        GROUP BY date, year, month_num, collision_severity
        ORDER BY date;
    """)

    

    # 可选：给 kpi_daily 加索引，进一步加速 date 范围查询（DuckDB 新版才支持）
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_kpi_daily_date ON kpi_daily(date);")
        print("[opt] CREATE INDEX idx_kpi_daily_date ON kpi_daily(date);")
    except Exception as e:
        print(f"[opt] Could not create index on kpi_daily: {e}")

    # ========== 3. DuckDB 侧优化：线程数 + 索引 ==========
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
            # 有些 DuckDB 版本可能不支持持久化索引，失败就打印一下，不影响主流程
            print(f"[opt] Failed to run '{stmt}': {e}")

    con.close()
    print("DuckDB database created successfully.")
