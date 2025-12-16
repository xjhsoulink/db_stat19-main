# file: src/dashboard/data.py
from __future__ import annotations

from src.shared.database import run_query


def _quote_list_str(values: list[str]) -> str:
    """
    Quote a list of strings into SQL IN-list format:
      ["Fatal","Serious"] -> "('Fatal','Serious')"
    """
    quoted = ",".join([f"'{v}'" for v in values])
    return f"({quoted})"


def _sev_clause(severity_filter: str | None, alias: str | None = None) -> str:
    """
    Normalize a severity filter into a safe SQL fragment.

    Accept both styles:
      - "collision_severity IN ('Fatal','Serious')"     (recommended / new)
      - "AND collision_severity IN (...)"              (legacy / old)
      - "collision_severity = 'Fatal'"
      - "1=0"                                          (no selection)

    Return:
      - "" (empty) if input is None/blank
      - " AND (<expr>)" otherwise

    If alias is provided (e.g., alias="col"), replace column references:
      collision_severity -> col.collision_severity
    """
    if not severity_filter:
        return ""

    s = severity_filter.strip()
    if not s:
        return ""

    # Tolerate legacy style with a leading AND
    if s.upper().startswith("AND "):
        s = s[4:].strip()

    # Apply alias for joined-table queries
    if alias:
        s = s.replace("collision_severity", f"{alias}.collision_severity")

    return f" AND ({s})"


def get_years(con):
    try:
        tables = run_query("SHOW TABLES", con)
        if tables is None or "collision" not in tables["name"].values:
            return []
        years_df = run_query("SELECT DISTINCT year FROM collision ORDER BY year DESC", con)
        if years_df is None:
            return []
        return years_df["year"].tolist()
    except Exception:
        return []


def get_kpi_data(con, year, severity_filter_cols):
    """
    severity_filter_cols is a tuple of (cols_coll, cols_cas, cols_veh),
    e.g. ("fatal + serious", "fatal_casualties + serious_casualties", ...)
    """
    cols_coll, cols_cas, cols_veh = severity_filter_cols

    kpi_query = f"""
        SELECT 
            SUM({cols_coll})  AS total_collisions,
            SUM({cols_cas})   AS total_casualties,
            SUM({cols_veh})   AS total_vehicles
        FROM kpi_monthly
        WHERE year = {year}
    """
    return run_query(kpi_query, con)


def get_monthly_trend(con, year, cols):
    """
    Fetch monthly KPI trend from kpi_monthly for a given year.
    cols can be:
      - "fatal, serious, slight"
      - "adj_fatal as fatal, adj_serious as serious, adj_slight as slight"
    """
    trend_query = f"""
        SELECT 
            month_num,
            month,
            {cols}
        FROM kpi_monthly
        WHERE year = {year}
        ORDER BY month_num
    """
    return run_query(trend_query, con)


def get_daily_trend(con, year, month):
    """
    Return daily collisions by severity for a given year/month (for single-month view).
    """
    query = f"""
        SELECT 
            date,
            collision_severity,
            COUNT(*) AS count
        FROM collision
        WHERE year = {year}
          AND month(date) = {month}
        GROUP BY date, collision_severity
        ORDER BY date
    """
    return run_query(query, con)


def get_date_range(con):
    """
    Return (min_date, max_date) from collision table for custom range UI.
    """
    df = run_query("SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM collision", con)
    if df is None or df.empty:
        return None, None
    return df["min_date"].iloc[0], df["max_date"].iloc[0]


def get_kpi_range(con, start_date, end_date, selected_severity):
    """
    KPI totals under custom date range:
      - start_date / end_date: Python date objects or 'YYYY-MM-DD'
      - selected_severity: subset of ['Fatal','Serious','Slight']
    """
    if not selected_severity:
        return None

    # Build a local severity filter (this function receives a list, not the sidebar expression)
    if len(selected_severity) == 1:
        sev_filter = f" AND collision_severity = '{selected_severity[0]}'"
    else:
        sev_filter = f" AND collision_severity IN {_quote_list_str(selected_severity)}"

    query = f"""
        SELECT
            SUM(collisions)  AS total_collisions,
            SUM(casualties)  AS total_casualties,
            SUM(vehicles)    AS total_vehicles
        FROM kpi_daily
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        {sev_filter}
    """
    return run_query(query, con)


def get_daily_trend_range(con, start_date, end_date, selected_severity):
    """
    Return time series within date range: date × severity -> collisions count.
    """
    if not selected_severity:
        # Return empty DataFrame; caller can handle.
        return run_query("SELECT date, collision_severity AS severity, 0 AS count LIMIT 0", con)

    if len(selected_severity) == 1:
        sev_filter = f" AND collision_severity = '{selected_severity[0]}'"
    else:
        sev_filter = f" AND collision_severity IN {_quote_list_str(selected_severity)}"

    query = f"""
        SELECT
            date,
            collision_severity AS severity,
            SUM(collisions) AS count
        FROM kpi_daily
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        {sev_filter}
        GROUP BY date, collision_severity
        ORDER BY date
    """
    return run_query(query, con)


def get_map_data(con, time_filter, severity_filter,
                 road_type_filter, weather_filter, light_filter):
    """
    Map point data from collision_geopoints.

    - time_filter: a fragment produced by Heatmap tab (must start with ' AND ...')
                 e.g. " AND year = 2024" or " AND date BETWEEN '2024-01-01' AND '2024-03-31'"
    - severity_filter: recommended to be a pure boolean expression (no leading AND),
                       e.g. "collision_severity IN ('Fatal','Serious')"
                       but legacy "AND ..." is also tolerated.
    - other filters: fragments created in tab layer (typically start with ' AND ...')
    """
    sev = _sev_clause(severity_filter)

    map_query = f"""
        SELECT 
            latitude, 
            longitude,
            collision_severity,
            date,
            time,
            number_of_casualties,
            number_of_vehicles
        FROM collision_geopoints 
        WHERE 1=1
        {time_filter}
        {sev}
    """
    if road_type_filter:
        map_query += road_type_filter
    if weather_filter:
        map_query += weather_filter
    if light_filter:
        map_query += light_filter

    map_query += " LIMIT 50000"
    return run_query(map_query, con)


def get_demographics_data(con, time_filter, severity_filter, filters):
    """
    Demographics analysis via casualty JOIN collision.

    - time_filter: already built for alias 'col' (from demographics tab),
                  e.g. " AND col.year = 2024" or " AND col.date BETWEEN ..."
    - severity_filter: pure expression on collision_severity (no leading AND),
                       will be aliased to col.collision_severity here.
    - filters: additional fragments from demographics tab, typically like:
              [" AND c.sex_of_casualty = 'Male'", ...]
    """
    sev = _sev_clause(severity_filter, alias="col")

    demo_query = f"""
        SELECT 
            c.casualty_type,
            c.age_group,
            c.sex_of_casualty,
            c.casualty_severity,
            COUNT(*) as count
        FROM casualty c
        JOIN collision col ON c.collision_index = col.collision_index
        WHERE 1=1
        {time_filter}
        {sev}
    """
    for f in filters:
        demo_query += f

    demo_query += """
        GROUP BY 
            c.casualty_type, 
            c.age_group, 
            c.sex_of_casualty, 
            c.casualty_severity
    """
    return run_query(demo_query, con)


def get_factor_data(con, time_filter, severity_filter, primary_col):
    """
    Single-factor environment breakdown from collision table.

    - time_filter: produced by Environment tab (must start with ' AND ...')
    - severity_filter: pure expression preferred; legacy 'AND ...' tolerated.
    """
    sev = _sev_clause(severity_filter)

    query = f"""
        SELECT 
            {primary_col}, 
            collision_severity,
            COUNT(*) as count
        FROM collision
        WHERE 1=1
        {time_filter}
        {sev}
        GROUP BY {primary_col}, collision_severity
        ORDER BY count DESC
    """
    return run_query(query, con)


def get_interaction_data(con, time_filter, severity_filter, primary_col, secondary_col):
    """
    Two-factor interaction analysis (counts) from collision table.

    - time_filter: produced by Environment tab (must start with ' AND ...')
    - severity_filter: pure expression preferred; legacy 'AND ...' tolerated.
    """
    sev = _sev_clause(severity_filter)

    query = f"""
        SELECT 
            {primary_col}, 
            {secondary_col},
            COUNT(*) as count
        FROM collision
        WHERE 1=1
        {time_filter}
        {sev}
        GROUP BY {primary_col}, {secondary_col}
    """
    return run_query(query, con)
