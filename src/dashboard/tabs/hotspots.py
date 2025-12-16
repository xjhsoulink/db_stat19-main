# src/dashboard/tabs/hotspots.py

import streamlit as st
import pandas as pd

# Optional: enable click-to-select-center on map
HAS_FOLIUM = True
try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    HAS_FOLIUM = False


def _sanitize_severity_filter(severity_filter: str | None) -> str | None:
    """
    Accept both styles:
      - "AND collision_severity IN (...)"   (legacy)
      - "collision_severity IN (...)"       (recommended)
    Return a pure boolean expression without leading AND.
    """
    if not severity_filter:
        return None
    s = severity_filter.strip()
    if not s:
        return None
    if s.upper().startswith("AND "):
        s = s[4:].strip()
    return s or None


def _table_exists(con, table_name: str) -> bool:
    try:
        return con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?;",
            [table_name],
        ).fetchone()[0] > 0
    except Exception:
        return False


def _get_distinct_values(con, table: str, col: str, limit: int = 30) -> list[str]:
    """
    Fetch top distinct values for a column (by frequency) to populate dropdowns.
    Returns a list of strings (no NULL/blank).
    """
    try:
        df = con.execute(
            f"""
            SELECT {col} AS v, COUNT(*) AS n
            FROM {table}
            WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS VARCHAR)) <> ''
            GROUP BY {col}
            ORDER BY n DESC
            LIMIT ?;
            """,
            [int(limit)],
        ).df()
        if df is None or df.empty:
            return []
        return [str(x) for x in df["v"].tolist()]
    except Exception:
        return []


def render_hotspots_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range):
    st.subheader("Hotspot Explorer (Neighborhood Aggregation)")
    st.caption(
        "Neighborhoods are defined as grid cells derived from latitude/longitude. "
        "This aggregates nearby collisions into neighborhood hotspots (not just point plotting)."
    )

    # -----------------------------
    # Required table check (Scheme A)
    # -----------------------------
    if not _table_exists(con, "geo_events_raw"):
        st.error(
            "`geo_events_raw` not found in DuckDB.\n"
            "Please update ETL (loader.py) to create `geo_events_raw` and re-run:\n"
            "`python clean_stats19.py`"
        )
        return

    # -----------------------------
    # Core controls (keep your existing behavior)
    # -----------------------------
    metric = st.selectbox("Rank hotspots by", ["risk_score", "casualties", "collisions"], index=0)
    topk = st.slider("Top K", min_value=5, max_value=200, value=20, step=5)

    # Neighborhood size dropdown (grid cell size)
    grid_options = {
        "50 m": 2225, 
        "100 m": 1113,
        "200 m": 556,  
        "~0.5 km (0.005°)": 200,  # 0.005°
        "~1.1 km (0.01°)": 100,   # 0.01°
        "~2.2 km (0.02°)": 50,    # 0.02°
        "~5.5 km (0.05°)": 20,    # 0.05°
    }
    grid_label = st.selectbox("Neighborhood size (grid cell)", list(grid_options.keys()), index=1)
    scale = int(grid_options[grid_label])

    # -----------------------------
    # Condition Filters (dropdowns) - keep your existing behavior
    # -----------------------------
    st.markdown("### Condition Filters (optional)")

    weather_opts = _get_distinct_values(con, "geo_events_raw", "weather_conditions", limit=30)
    light_opts = _get_distinct_values(con, "geo_events_raw", "light_conditions", limit=30)
    road_opts = _get_distinct_values(con, "geo_events_raw", "road_type", limit=30)

    cols = st.columns(3)
    with cols[0]:
        weather_sel = st.selectbox("weather_conditions", options=["All"] + weather_opts, index=0)
    with cols[1]:
        light_sel = st.selectbox("light_conditions", options=["All"] + light_opts, index=0)
    with cols[2]:
        road_sel = st.selectbox("road_type", options=["All"] + road_opts, index=0)

    # -----------------------------
    # Build WHERE (parameterized)
    # -----------------------------
    sev_expr = _sanitize_severity_filter(severity_filter)

    where: list[str] = []
    params: list = []

    # Time filtering: support both sidebar modes
    if time_mode == "Year/Month":
        if selected_year is None:
            st.warning("Please select a Year (Year/Month mode) in the sidebar.")
            return
        where.append("year = ?")
        params.append(int(selected_year))

        if selected_month is not None and selected_month != "All":
            try:
                where.append("month_num = ?")
                params.append(int(selected_month))
            except Exception:
                pass

    else:
        # Custom Range mode
        if not date_range or len(date_range) != 2:
            st.warning("Please select a valid date range in the sidebar.")
            return
        start_date, end_date = date_range
        where.append("date::DATE BETWEEN ? AND ?")
        params.extend([str(start_date), str(end_date)])

    # Severity
    if sev_expr:
        where.append(f"({sev_expr})")

    # Conditions (exact match via dropdown)
    if weather_sel != "All":
        where.append("weather_conditions = ?")
        params.append(weather_sel)
    if light_sel != "All":
        where.append("light_conditions = ?")
        params.append(light_sel)
    if road_sel != "All":
        where.append("road_type = ?")
        params.append(road_sel)

    where_sql = " AND ".join(where) if where else "1=1"

    # =========================================================
    # Radius Query (click-to-select center) - ADDITIVE feature
    # =========================================================
    st.markdown("### Radius Query (optional)")
    use_radius = st.checkbox("Enable radius filter (find hotspots near a clicked location)", value=False)

    # Persist center in session state (so it survives reruns)
    if "hotspot_center_lat" not in st.session_state:
        st.session_state.hotspot_center_lat = 51.5074   # London default
    if "hotspot_center_lon" not in st.session_state:
        st.session_state.hotspot_center_lon = -0.1278

    center_lat = float(st.session_state.hotspot_center_lat)
    center_lon = float(st.session_state.hotspot_center_lon)

    radius_miles = None
    if use_radius:
        c1, c2, c3 = st.columns([2, 2, 2])

        # Clickable map (best UX)
        st.info("Step 1: Click on the map to set the center point (and adjust the radius above). ")
        st.info("Step 2: Scroll down to see the hotspot ranking table and map results below ⬇️")

        if HAS_FOLIUM:
            with c1:
                st.caption("Click on the map to set the center point.")
            with c2:
                st.caption("Current center updates automatically after clicking.")
            with c3:
                st.caption("Pick a radius (miles).")

            # 1) Let user input radius FIRST (so the circle uses the latest value)
            radius_miles = st.number_input(
                "Radius (miles)",
                min_value=0.1,
                max_value=100.0,
                value=10.0,
                step=0.5,
            )

            m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles="cartodbpositron")
            folium.Marker([center_lat, center_lon], tooltip="Center").add_to(m)

            # 2) Use the selected radius to draw circle (meters)
            radius_meters = float(radius_miles) * 1609.344
            folium.Circle(
                location=[center_lat, center_lon],
                radius=radius_meters,   # <-- dynamic now
                color="#cc0000",
                fill=False,
                weight=2,
            ).add_to(m)

            out = st_folium(m, height=420, use_container_width=True)
            if out and out.get("last_clicked"):
                st.session_state.hotspot_center_lat = float(out["last_clicked"]["lat"])
                st.session_state.hotspot_center_lon = float(out["last_clicked"]["lng"])
                center_lat = float(st.session_state.hotspot_center_lat)
                center_lon = float(st.session_state.hotspot_center_lon)


        # Fallback: manual inputs if folium is not available
        else:
            st.info("Tip: Install `folium` and `streamlit-folium` to enable click-to-select.")
            center_lat = st.number_input("Center latitude", value=center_lat, format="%.6f")
            center_lon = st.number_input("Center longitude", value=center_lon, format="%.6f")
            st.session_state.hotspot_center_lat = center_lat
            st.session_state.hotspot_center_lon = center_lon


        st.write(f"Selected center: **({center_lat:.6f}, {center_lon:.6f})**, radius: **{radius_miles} miles**")

    # -----------------------------
    # Dynamic grid binning query
    # If radius enabled: filter aggregated cells by haversine distance to center.
    # -----------------------------
    # Earth radius in miles
    R_MILES = 3958.8

    # Haversine distance in SQL (between centroid and center)
    # NOTE: DuckDB supports trig functions like radians/sin/cos/asin/sqrt.
    dist_expr = f"""
    ({R_MILES} * 2 * ASIN(SQRT(
        POW(SIN(RADIANS((grid_lat - ?) / 2)), 2) +
        COS(RADIANS(?)) * COS(RADIANS(grid_lat)) *
        POW(SIN(RADIANS((grid_lon - ?) / 2)), 2)
    )))
    """

    radius_filter_sql = ""
    radius_params: list = []
    if use_radius and radius_miles is not None:
        radius_filter_sql = f"WHERE {dist_expr} <= ?"
        radius_params = [center_lat, center_lat, center_lon, float(radius_miles)]

    query = f"""
    WITH binned AS (
        SELECT
            CAST(FLOOR(latitude  * {scale}) AS BIGINT) AS gx,
            CAST(FLOOR(longitude * {scale}) AS BIGINT) AS gy,
            year,
            month_num,
            date,
            collision_severity,
            weather_conditions,
            light_conditions,
            road_type,
            casualties,
            vehicles
        FROM geo_events_raw
        WHERE {where_sql}
    ),
    agg AS (
        SELECT
            CONCAT(CAST(gx AS VARCHAR), '_', CAST(gy AS VARCHAR)) AS cell_id,
            (gx + 0.5) / {scale} AS grid_lat,
            (gy + 0.5) / {scale} AS grid_lon,
            COUNT(*) AS collisions,
            SUM(casualties) AS casualties,
            SUM(
                CASE
                    WHEN collision_severity='Fatal' THEN 3
                    WHEN collision_severity='Serious' THEN 2
                    WHEN collision_severity='Slight' THEN 1
                    ELSE 0
                END
            ) AS risk_score
        FROM binned
        GROUP BY cell_id, grid_lat, grid_lon
    )
    SELECT
        *,
        {dist_expr} AS distance_miles
    FROM agg
    {radius_filter_sql}
    ORDER BY {metric} DESC
    LIMIT ?;
    """

    # Params order:
    # 1) base WHERE params
    # 2) dist_expr for SELECT distance_miles: (grid_lat - clat), clat, (grid_lon - clon)
    # 3) if radius enabled: dist_expr again + radius
    # 4) topk
    base = params[:]
    select_dist = [center_lat, center_lat, center_lon]
    final_params = base + select_dist

    if use_radius and radius_miles is not None:
        # radius_filter_sql includes dist_expr again + radius
        final_params += radius_params

    final_params += [int(topk)]

    try:
        df = con.execute(query, final_params).df()
    except Exception as e:
        st.error(f"Hotspot query failed.\n\nError: {e}")
        return

    st.markdown("### Top Hotspots")
    st.dataframe(df, use_container_width=True)

    if df is None or df.empty:
        st.info("No hotspots returned for the current filters.")
        return

    st.markdown("### Map View (grid centroids)")
    mdf = df.rename(columns={"grid_lat": "lat", "grid_lon": "lon"})
    st.map(mdf)

    st.markdown("### Drill-down (selected neighborhood)")
    cell = st.selectbox("Select a hotspot cell_id", df["cell_id"].tolist(), index=0)

    drill_query = f"""
    WITH binned AS (
        SELECT
            CAST(FLOOR(latitude  * {scale}) AS BIGINT) AS gx,
            CAST(FLOOR(longitude * {scale}) AS BIGINT) AS gy,
            collision_severity,
            casualties
        FROM geo_events_raw
        WHERE {where_sql}
    ),
    labeled AS (
        SELECT
            CONCAT(CAST(gx AS VARCHAR), '_', CAST(gy AS VARCHAR)) AS cell_id,
            collision_severity,
            casualties
        FROM binned
    )
    SELECT
        collision_severity,
        COUNT(*) AS collisions,
        SUM(casualties) AS casualties
    FROM labeled
    WHERE cell_id = ?
    GROUP BY collision_severity
    ORDER BY collisions DESC;
    """

    try:
        ddf = con.execute(drill_query, params + [cell]).df()
        st.dataframe(ddf, use_container_width=True)
    except Exception as e:
        st.error(f"Drill-down query failed.\n\nError: {e}")
        return
