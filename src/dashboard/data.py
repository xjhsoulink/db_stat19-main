'''

from src.shared.database import run_query

def get_years(con):
    try:
        tables = run_query("SHOW TABLES", con)
        if tables is None or 'collision' not in tables['name'].values:
            return []
        years_df = run_query("SELECT DISTINCT year FROM collision ORDER BY year DESC", con)
        if years_df is None:
            return []
        return years_df['year'].tolist()
    except Exception:
        return []

def get_kpi_data(con, year, severity_filter_cols):
    # severity_filter_cols is a tuple of (cols_coll, cols_cas, cols_veh)
    cols_coll, cols_cas, cols_veh = severity_filter_cols
    
    kpi_query = f"""
        SELECT 
            SUM({cols_coll}) as total_collisions,
            SUM({cols_cas}) as total_casualties,
            SUM({cols_veh}) as total_vehicles
        FROM kpi_monthly
        WHERE year = {year}
    """
    return run_query(kpi_query, con)

def get_monthly_trend(con, year, cols):
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

def get_map_data(con, year, severity_filter, road_type_filter, weather_filter, light_filter):
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
        WHERE year = {year}
        {severity_filter}
    """
    if road_type_filter:
        map_query += road_type_filter
    if weather_filter:
        map_query += weather_filter
    if light_filter:
        map_query += light_filter
        
    map_query += " LIMIT 50000"
    return run_query(map_query, con)

def get_demographics_data(con, year, severity_filter, filters):
    demo_query = f"""
        SELECT 
            c.casualty_type,
            c.age_group,
            c.sex_of_casualty,
            c.casualty_severity,
            COUNT(*) as count
        FROM casualty c
        JOIN collision col ON c.collision_index = col.collision_index
        WHERE col.year = {year}
        {severity_filter.replace('collision_severity', 'col.collision_severity')}
    """
    for f in filters:
        demo_query += f
        
    demo_query += """
        GROUP BY c.casualty_type, c.age_group, c.sex_of_casualty, c.casualty_severity
    """
    return run_query(demo_query, con)

def get_factor_data(con, year, severity_filter, primary_col):
    query = f"""
        SELECT 
            {primary_col}, 
            collision_severity,
            COUNT(*) as count
        FROM collision
        WHERE year = {year}
        {severity_filter}
        GROUP BY {primary_col}, collision_severity
        ORDER BY count DESC
    """
    return run_query(query, con)

def get_interaction_data(con, year, severity_filter, primary_col, secondary_col):
    query = f"""
        SELECT 
            {primary_col}, 
            {secondary_col},
            COUNT(*) as count
        FROM collision
        WHERE year = {year}
        {severity_filter}
        GROUP BY {primary_col}, {secondary_col}
    """
    return run_query(query, con)
'''

from src.shared.database import run_query

def get_years(con):
    try:
        tables = run_query("SHOW TABLES", con)
        if tables is None or 'collision' not in tables['name'].values:
            return []
        years_df = run_query("SELECT DISTINCT year FROM collision ORDER BY year DESC", con)
        if years_df is None:
            return []
        return years_df['year'].tolist()
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
    从 kpi_monthly 中取出某年的每月趋势。
    cols 是类似 "fatal, serious, slight" 或
    "adj_fatal as fatal, adj_serious as serious, adj_slight as slight"。
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
    返回某年某月的“每天 × 严重程度”的碰撞数量，用于单月视图。
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
    返回 collision 表里的 (min_date, max_date)，用于自定义时间范围控件。
    """
    df = run_query("SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM collision", con)
    if df is None or df.empty:
        return None, None
    return df["min_date"].iloc[0], df["max_date"].iloc[0]


def get_kpi_range(con, start_date, end_date, selected_severity):
    """
    自定义日期范围下的三大 KPI：
    - start_date / end_date: Python 的 date 对象或 'YYYY-MM-DD' 字符串
    - selected_severity: ['Fatal','Serious','Slight'] 的子集
    """
    if not selected_severity:
        return None

    # 构造严重程度过滤条件
    if len(selected_severity) == 1:
        sev_filter = f"AND collision_severity = '{selected_severity[0]}'"
    else:
        sev_filter = f"AND collision_severity IN {tuple(selected_severity)}"

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
    返回某个日期范围内，按“日期 × 严重程度”的时间序列，用于画折线图。
    """
    if not selected_severity:
        # 返回空 DataFrame，调用端自己处理
        return run_query("SELECT date, collision_severity AS severity, 0 AS count LIMIT 0", con)

    if len(selected_severity) == 1:
        sev_filter = f"AND collision_severity = '{selected_severity[0]}'"
    else:
        sev_filter = f"AND collision_severity IN {tuple(selected_severity)}"

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


'''
def get_map_data(con, year, month_filter, severity_filter,
                 road_type_filter, weather_filter, light_filter):
    """
    热力图使用的地理点数据，来自 collision_geopoints。
    - year: 年份
    - month_filter: "" 或 " AND month(date) = X"
    - severity_filter: 形如 "AND collision_severity IN (...)" 的片段
    - road_type_filter / weather_filter / light_filter: 由 heatmap tab 拼好的 SQL 片段
    """
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
        WHERE year = {year}
        {month_filter}
        {severity_filter}
    """
    if road_type_filter:
        map_query += road_type_filter
    if weather_filter:
        map_query += weather_filter
    if light_filter:
        map_query += light_filter
        
    map_query += " LIMIT 50000"
    return run_query(map_query, con)


def get_demographics_data(con, year, month_filter, severity_filter, filters):
    """
    人群画像（demographics）分析：
    - year: 年份
    - month_filter: "" 或 " AND month(col.date) = X"
    - severity_filter: 形如 "AND collision_severity IN (...)" 的片段，
      在这里会自动替换成 "col.collision_severity"
    - filters: 来自 demographics tab 的其他条件列表
    """
    demo_query = f"""
        SELECT 
            c.casualty_type,
            c.age_group,
            c.sex_of_casualty,
            c.casualty_severity,
            COUNT(*) as count
        FROM casualty c
        JOIN collision col ON c.collision_index = col.collision_index
        WHERE col.year = {year}
        {month_filter}
        {severity_filter.replace('collision_severity', 'col.collision_severity')}
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


def get_factor_data(con, year, month_filter, severity_filter, primary_col):
    """
    按单一环境因素统计不同严重程度下的碰撞数量。
    - year: 年份
    - month_filter: "" 或 " AND month(date) = X"
    - severity_filter: "AND collision_severity IN (...)" 之类
    - primary_col: 要分析的列名（如 'road_type'）
    """
    query = f"""
        SELECT 
            {primary_col}, 
            collision_severity,
            COUNT(*) as count
        FROM collision
        WHERE year = {year}
        {month_filter}
        {severity_filter}
        GROUP BY {primary_col}, collision_severity
        ORDER BY count DESC
    """
    return run_query(query, con)


def get_interaction_data(con, year, month_filter, severity_filter, primary_col, secondary_col):
    """
    两个环境因素的交叉分析，用于环境 tab 里的热力图。
    """
    query = f"""
        SELECT 
            {primary_col}, 
            {secondary_col},
            COUNT(*) as count
        FROM collision
        WHERE year = {year}
        {month_filter}
        {severity_filter}
        GROUP BY {primary_col}, {secondary_col}
    """
    return run_query(query, con)
'''

def get_map_data(con, time_filter, severity_filter,
                 road_type_filter, weather_filter, light_filter):
    """
    热力图用的地理点数据（collision_geopoints）：
    - time_filter: 形如 " AND year = 2024" 或 " AND date BETWEEN '2024-01-01' AND '2024-03-31'"
    - severity_filter: "AND collision_severity IN (...)" 这种
    其他 filter 由 tab 拼好传入。
    """
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
        {severity_filter}
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
    人群统计：
    - time_filter: 注意使用 col.year / col.date（在 tab 里已经按 alias 拼好）
    - severity_filter: 用 collision_severity 写，内部会替换成 col.collision_severity
    - filters: demographics.py 里的人口条件 [" AND c.casualty_class = ...", ...]
    """
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
        {severity_filter.replace('collision_severity', 'col.collision_severity')}
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
    环境因素单维统计：
    - time_filter: year/month/date 范围，对 collision 直接用 year/date 列
    """
    query = f"""
        SELECT 
            {primary_col}, 
            collision_severity,
            COUNT(*) as count
        FROM collision
        WHERE 1=1
        {time_filter}
        {severity_filter}
        GROUP BY {primary_col}, collision_severity
        ORDER BY count DESC
    """
    return run_query(query, con)


def get_interaction_data(con, time_filter, severity_filter, primary_col, secondary_col):
    """
    环境因素交互统计。
    """
    query = f"""
        SELECT 
            {primary_col}, 
            {secondary_col},
            COUNT(*) as count
        FROM collision
        WHERE 1=1
        {time_filter}
        {severity_filter}
        GROUP BY {primary_col}, {secondary_col}
    """
    return run_query(query, con)
