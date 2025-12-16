# src/dashboard/tabs/hotspots.py

import streamlit as st
import pandas as pd
import io
import pydeck as pdk

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
        return (
            con.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?;",
                [table_name],
            ).fetchone()[0]
            > 0
        )
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
    # Required table check
    # -----------------------------
    if not _table_exists(con, "geo_events_raw"):
        st.error(
            "`geo_events_raw` not found in DuckDB.\n"
            "Please update ETL (loader.py) to create `geo_events_raw` and re-run:\n"
            "`python clean_stats19.py`"
        )
        return

    # -----------------------------
    # Core controls
    # -----------------------------
    metric = st.selectbox("Rank hotspots by", ["risk_score", "casualties", "collisions"], index=0)
    topk = st.slider("Top K", min_value=5, max_value=200, value=20, step=5)

    # Neighborhood size dropdown (grid cell size)
    grid_options = {
        "50 m": 2225,
        "100 m": 1113,
        "200 m": 556,
        "~0.5 km (0.005°)": 200,   # ~0.005°
        "~1.1 km (0.01°)": 100,    # ~0.01°
        "~2.2 km (0.02°)": 50,     # ~0.02°
        "~5.5 km (0.05°)": 20,     # ~0.05°
    }
    grid_label = st.selectbox("Neighborhood size (grid cell)", list(grid_options.keys()), index=1)
    scale = int(grid_options[grid_label])

    # -----------------------------
    # Condition Filters (dropdowns)
    # Cache these to avoid heavy GROUP BY on every rerun (e.g., map click)
    # -----------------------------
    st.markdown("### Condition Filters (optional)")

    if "hotspots_weather_opts" not in st.session_state:
        st.session_state.hotspots_weather_opts = _get_distinct_values(con, "geo_events_raw", "weather_conditions", limit=30)
    if "hotspots_light_opts" not in st.session_state:
        st.session_state.hotspots_light_opts = _get_distinct_values(con, "geo_events_raw", "light_conditions", limit=30)
    if "hotspots_road_opts" not in st.session_state:
        st.session_state.hotspots_road_opts = _get_distinct_values(con, "geo_events_raw", "road_type", limit=30)

    weather_opts = st.session_state.hotspots_weather_opts
    light_opts = st.session_state.hotspots_light_opts
    road_opts = st.session_state.hotspots_road_opts

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
    # Radius Query (click-to-select center) - optional
    # Important: selecting center should NOT trigger heavy query.
    # We require an explicit "Run" button.
    # =========================================================
    st.markdown("### Radius Query (optional)")
    use_radius = st.checkbox("Enable radius filter (find hotspots near a clicked location)", value=False)

    # gate flag
    if "run_radius_query" not in st.session_state:
        st.session_state.run_radius_query = False

    # Persist center in session state
    if "hotspot_center_lat" not in st.session_state:
        st.session_state.hotspot_center_lat = 51.5074   # London default
    if "hotspot_center_lon" not in st.session_state:
        st.session_state.hotspot_center_lon = -0.1278

    center_lat = float(st.session_state.hotspot_center_lat)
    center_lon = float(st.session_state.hotspot_center_lon)

    radius_miles = None
    if use_radius:
        st.info("Step 1: Click on the map to set the center point.")
        st.info("Step 2: Click **Run** to compute hotspots near the selected center.")

        if HAS_FOLIUM:
            # radius input first (circle uses latest value)
            radius_miles = st.number_input(
                "Radius (miles)",
                min_value=0.1,
                max_value=100.0,
                value=10.0,
                step=0.5,
            )

            m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles="cartodbpositron")
            folium.Marker([center_lat, center_lon], tooltip="Center").add_to(m)

            radius_meters = float(radius_miles) * 1609.344
            folium.Circle(
                location=[center_lat, center_lon],
                radius=radius_meters,
                color="#cc0000",
                fill=False,
                weight=2,
            ).add_to(m)

            out = st_folium(
                m,
                height=420,
                use_container_width=True,
                key="radius_center_map",
                returned_objects=["last_clicked"],  # reduce payload
            )

            if out and out.get("last_clicked"):
                st.session_state.hotspot_center_lat = float(out["last_clicked"]["lat"])
                st.session_state.hotspot_center_lon = float(out["last_clicked"]["lng"])
                st.session_state.run_radius_query = False  # ★center changed -> require Run again
                st.rerun()

        else:
            st.info("Tip: Install `folium` and `streamlit-folium` to enable click-to-select.")
            center_lat = st.number_input("Center latitude", value=center_lat, format="%.6f")
            center_lon = st.number_input("Center longitude", value=center_lon, format="%.6f")
            st.session_state.hotspot_center_lat = center_lat
            st.session_state.hotspot_center_lon = center_lon

            radius_miles = st.number_input(
                "Radius (miles)",
                min_value=0.1,
                max_value=100.0,
                value=10.0,
                step=0.5,
            )

        st.write(f"Selected center: **({center_lat:.6f}, {center_lon:.6f})**, radius: **{radius_miles} miles**")

        if st.button("Run hotspot query near selected center", type="primary"):
            st.session_state.run_radius_query = True

        if not st.session_state.run_radius_query:
            st.stop()
    else:
        # not using radius -> no gating
        st.session_state.run_radius_query = False

    # -----------------------------
    # Dynamic grid binning query
    # If radius enabled: filter aggregated cells by haversine distance to center.
    # -----------------------------
    R_MILES = 3958.8

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
    ORDER BY {metric} DESC, cell_id ASC
    LIMIT ?;
    """

    # Params order:
    base = params[:]
    select_dist = [center_lat, center_lat, center_lon]
    final_params = base + select_dist

    if use_radius and radius_miles is not None:
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

    cell_options = df["cell_id"].astype(str).tolist()
    if not cell_options:
        st.info("No hotspot cells available for drill-down.")
        return

    if "hotspot_cell_id" not in st.session_state or st.session_state.hotspot_cell_id not in cell_options:
        st.session_state.hotspot_cell_id = cell_options[0]

    default_idx = cell_options.index(st.session_state.hotspot_cell_id)

    cell = st.selectbox(
        "Select a hotspot cell_id",
        options=cell_options,
        index=default_idx,
        key="hotspot_cell_selectbox",
    )

    st.session_state.hotspot_cell_id = cell


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

        st.markdown("### See details (all raw points in this neighborhood)")
        

        with st.expander("See details / export raw rows for this cell", expanded=False):
            # 解析 cell_id -> gx, gy
            try:
                gx_str, gy_str = str(cell).split("_")
                gx_sel, gy_sel = int(gx_str), int(gy_str)
            except Exception:
                st.error(f"Invalid cell_id format: {cell}")
                st.stop()

            cA, cB, cC = st.columns([2, 2, 2])
            with cA:
                detail_limit = st.number_input("Rows to show", min_value=100, max_value=200000, value=2000, step=500)
            with cB:
                detail_offset = st.number_input("Offset (pagination)", min_value=0, max_value=10_000_000, value=0, step=2000)
            with cC:
                detail_order = st.selectbox("Order by", ["date", "collision_severity", "casualties"], index=0)

            cols_default = [
                "date", "year", "month_num",
                "latitude", "longitude",
                "collision_severity", "casualties", "vehicles",
                "weather_conditions", "light_conditions", "road_type"
            ]
            show_cols = st.multiselect("Columns to display", options=cols_default, default=cols_default)

            order_sql = {
                "date": "date",
                "collision_severity": "collision_severity",
                "casualties": "casualties"
            }[detail_order]

            detail_query = f"""
            WITH binned AS (
                SELECT
                    CAST(FLOOR(latitude  * {scale}) AS BIGINT) AS gx,
                    CAST(FLOOR(longitude * {scale}) AS BIGINT) AS gy,
                    date,
                    year,
                    month_num,
                    latitude,
                    longitude,
                    collision_severity,
                    casualties,
                    vehicles,
                    weather_conditions,
                    light_conditions,
                    road_type
                FROM geo_events_raw
                WHERE {where_sql}
            )
            SELECT {", ".join(show_cols)}
            FROM binned
            WHERE gx = ? AND gy = ?
            ORDER BY {order_sql} ASC
            LIMIT ? OFFSET ?;
            """

            run_details = st.button("Load details", type="primary")

            if run_details:
                try:
                    dparams = params + [gx_sel, gy_sel, int(detail_limit), int(detail_offset)]
                    detail_df = con.execute(detail_query, dparams).df()
                    st.dataframe(detail_df, use_container_width=True)

                    st.markdown("#### Map of raw points in this cell (Heatmap-style)")

                    plot_df = detail_df.copy()
                    plot_df = plot_df.dropna(subset=["latitude", "longitude"])

                    if plot_df.empty:
                        st.info("No valid lat/lon points to plot for this cell.")
                    else:
                        if "date" in plot_df.columns:
                            plot_df["date"] = plot_df["date"].astype(str)
                        if "time" in plot_df.columns:
                            plot_df["time"] = plot_df["time"].astype(str)

                        def get_color(sev: str):
                            if sev == "Fatal":
                                return [255, 0, 0, 160]
                            elif sev == "Serious":
                                return [255, 165, 0, 160]
                            else:
                                return [0, 128, 255, 160]

                        if "collision_severity" in plot_df.columns:
                            plot_df["color"] = plot_df["collision_severity"].apply(get_color)
                        else:
                            plot_df["color"] = [[0, 128, 255, 160]] * len(plot_df)

                        max_points = 8000
                        if len(plot_df) > max_points:
                            plot_df = plot_df.sample(n=max_points, random_state=42)
                            st.caption(f"Too many points. Showing a random sample of {max_points:,}.")

                        layer = pdk.Layer(
                            "ScatterplotLayer",
                            plot_df,
                            get_position=["longitude", "latitude"],
                            get_fill_color="color",

                            get_radius=6,
                            radius_min_pixels=1,
                            radius_max_pixels=6,

                            stroked=True,
                            get_line_color=[255, 255, 255, 220],   
                            line_width_min_pixels=1,
                            line_width_max_pixels=1,    

                            filled=True,
                            opacity=0.75,
                            pickable=True,
                        )


                        mid_lat = plot_df["latitude"].mean()
                        mid_lon = plot_df["longitude"].mean()

                        view_state = pdk.ViewState(
                            longitude=float(mid_lon),
                            latitude=float(mid_lat),
                            zoom=16,
                            min_zoom=5,
                            max_zoom=25,
                            pitch=0,
                            bearing=0,
                        )

                        deck = pdk.Deck(
                            layers=[layer],
                            initial_view_state=view_state,
                            tooltip={
                                "html": "<b>Severity:</b> {collision_severity}<br/>"
                                        "<b>Date:</b> {date}<br/>"
                                        "<b>Casualties:</b> {casualties}<br/>"
                                        "<b>Vehicles:</b> {vehicles}<br/>"
                                        "<b>Weather:</b> {weather_conditions}<br/>"
                                        "<b>Light:</b> {light_conditions}<br/>"
                                        "<b>Road:</b> {road_type}",
                                "style": {"backgroundColor": "steelblue", "color": "white"},
                            },
                        )

                        st.pydeck_chart(deck, use_container_width=True)
                        st.caption(f"Showing {len(plot_df)} points (from the selected cell).")


                    st.markdown("#### Map of raw points in this cell")

                    plot_df = detail_df.copy()
                    plot_df = plot_df.rename(columns={"latitude": "lat", "longitude": "lon"})
                    plot_df = plot_df.dropna(subset=["lat", "lon"])

                    csv_bytes = detail_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "Download this page (CSV)",
                        data=csv_bytes,
                        file_name=f"cell_{cell}_limit{detail_limit}_offset{detail_offset}.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"Detail query failed.\n\nError: {e}")

    except Exception as e:
        st.error(f"Drill-down query failed.\n\nError: {e}")
        return

