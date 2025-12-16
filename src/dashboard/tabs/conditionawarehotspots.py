import streamlit as st
import duckdb
import pandas as pd

def get_con(db_path="road_safety.duckdb"):
    return duckdb.connect(db_path, read_only=True)

def condition_hotspots_tab(db_path="road_safety.duckdb"):
    st.header("Condition-aware Hotspots")
    con = get_con(db_path)

    # --- options for dropdowns ---
    years = con.execute("SELECT DISTINCT year FROM geo_grid_events ORDER BY year;").fetchall()
    years = [y[0] for y in years]
    year = st.selectbox("Year", years, index=len(years)-1)

    # Optional filters - load distinct values for current year to keep list smaller
    weather_opts = [r[0] for r in con.execute(
        "SELECT DISTINCT weather_conditions FROM geo_grid_events WHERE year=? ORDER BY 1;", [year]
    ).fetchall()]
    light_opts = [r[0] for r in con.execute(
        "SELECT DISTINCT light_conditions FROM geo_grid_events WHERE year=? ORDER BY 1;", [year]
    ).fetchall()]
    road_opts = [r[0] for r in con.execute(
        "SELECT DISTINCT road_type FROM geo_grid_events WHERE year=? ORDER BY 1;", [year]
    ).fetchall()]
    sev_opts = [r[0] for r in con.execute(
        "SELECT DISTINCT collision_severity FROM geo_grid_events WHERE year=? ORDER BY 1;", [year]
    ).fetchall()]

    weather = st.multiselect("Weather (optional)", weather_opts, default=[])
    light = st.multiselect("Light (optional)", light_opts, default=[])
    road = st.multiselect("Road type (optional)", road_opts, default=[])
    severity = st.multiselect("Severity (optional)", sev_opts, default=[])

    metric = st.selectbox("Rank by", ["risk_score", "casualties", "collisions"], index=0)
    topk = st.slider("Top K hotspots", 5, 100, 20, step=5)

    # --- build WHERE dynamically (safe, parameterized) ---
    where = ["year = ?"]
    params = [year]

    if weather:
        where.append("weather_conditions IN (" + ",".join(["?"] * len(weather)) + ")")
        params.extend(weather)
    if light:
        where.append("light_conditions IN (" + ",".join(["?"] * len(light)) + ")")
        params.extend(light)
    if road:
        where.append("road_type IN (" + ",".join(["?"] * len(road)) + ")")
        params.extend(road)
    if severity:
        where.append("collision_severity IN (" + ",".join(["?"] * len(severity)) + ")")
        params.extend(severity)

    where_sql = " AND ".join(where)

    query = f"""
    SELECT
      cell_id, grid_lat, grid_lon,
      COUNT(*) AS collisions,
      SUM(casualties) AS casualties,
      SUM(CASE WHEN collision_severity='Fatal' THEN 3
               WHEN collision_severity='Serious' THEN 2
               WHEN collision_severity='Slight' THEN 1
               ELSE 0 END) AS risk_score
    FROM geo_grid_events
    WHERE {where_sql}
    GROUP BY cell_id, grid_lat, grid_lon
    ORDER BY {metric} DESC
    LIMIT ?;
    """
    params2 = params + [topk]

    df = con.execute(query, params2).df()
    con.close()

    st.subheader("Top hotspots")
    st.dataframe(df)

    # Optional: quick map (grid centroids)
    if not df.empty:
        st.subheader("Map (grid centroids)")
        st.map(df.rename(columns={"grid_lat": "lat", "grid_lon": "lon"}))

