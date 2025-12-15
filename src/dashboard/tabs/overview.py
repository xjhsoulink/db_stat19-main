# src/dashboard/tabs/overview.py
import calendar
from datetime import date
import streamlit as st
import plotly.express as px

from src.dashboard.data import (
    get_kpi_data,          # 年度 KPI（用 kpi_monthly）
    get_kpi_range,         # 自定义日期范围 KPI（用 kpi_daily）
    get_monthly_trend,     # 年度按月趋势（用 kpi_monthly）
    get_daily_trend_range  # 任意日期范围按日趋势（用 kpi_daily）
)


def render_overview_tab(con, time_mode, selected_year, selected_month,
                        selected_severity, date_range):
    """
    Overview 页：
    - time_mode: "Year/Month" 或 "Custom Range"
    - selected_year: 年度模式下的年份（int），自定义模式下可为 None
    - selected_month: 年度模式下的月份（"All" 或 1-12），自定义模式下一般为 "All"
    - selected_severity: ['Fatal', 'Serious', 'Slight'] 的子集
    - date_range: 自定义模式下的 (start_date, end_date)，Year/Month 模式下为 None
    """
    st.header("Safety Overview")

    # ==========================
    # Top-level KPI 指标
    # ==========================
    col1, col2, col3 = st.columns(3)

    # ---------- Year/Month 模式：用 kpi_monthly ----------
    if time_mode == "Year/Month":
        # 没选严重程度：全部置 0
        if not selected_severity:
            cols_coll = "0"
            cols_cas = "0"
            cols_veh = "0"
        else:
            # e.g. ['Fatal', 'Serious'] -> "fatal + serious"
            cols_coll = " + ".join([s.lower() for s in selected_severity])
            cols_cas = " + ".join([f"{s.lower()}_casualties" for s in selected_severity])
            cols_veh = " + ".join([f"{s.lower()}_vehicles" for s in selected_severity])

        try:
            kpi_df = get_kpi_data(con, selected_year, (cols_coll, cols_cas, cols_veh))
            if kpi_df is None or kpi_df.empty:
                raise ValueError("No KPI data returned for the selected filters.")
            kpi_data = kpi_df.iloc[0]

            # 尝试拿上一年的数据做 delta
            prev_year = selected_year - 1
            try:
                kpi_prev_df = get_kpi_data(con, prev_year, (cols_coll, cols_cas, cols_veh))
                if kpi_prev_df is None or kpi_prev_df.empty:
                    raise ValueError("No KPI data returned for the previous year.")
                kpi_data_prev = kpi_prev_df.iloc[0]

                delta_col = int(kpi_data["total_collisions"] - kpi_data_prev["total_collisions"])
                delta_cas = int(kpi_data["total_casualties"] - kpi_data_prev["total_casualties"])
                delta_veh = int(kpi_data["total_vehicles"] - kpi_data_prev["total_vehicles"])

                col1.metric(
                    "Total Collisions",
                    f"{int(kpi_data['total_collisions']):,}",
                    delta=f"{delta_col:,} vs {prev_year}",
                )
                col2.metric(
                    "Total Casualties",
                    f"{int(kpi_data['total_casualties']):,}",
                    delta=f"{delta_cas:,} vs {prev_year}",
                )
                col3.metric(
                    "Vehicles Involved",
                    f"{int(kpi_data['total_vehicles']):,}",
                    delta=f"{delta_veh:,} vs {prev_year}",
                )
            except Exception:
                # 没有上一年数据就不展示 delta
                col1.metric("Total Collisions", f"{int(kpi_data['total_collisions']):,}")
                col2.metric("Total Casualties", f"{int(kpi_data['total_casualties']):,}")
                col3.metric("Vehicles Involved", f"{int(kpi_data['total_vehicles']):,}")

        except Exception as e:
            st.error(f"Error calculating KPIs: {e}")

    # ---------- Custom Range 模式：用 kpi_daily ----------
    else:
        if not date_range or len(date_range) != 2:
            st.error("Please select a valid date range.")
        else:
            start_date, end_date = date_range
            try:
                kpi_df = get_kpi_range(con, start_date, end_date, selected_severity)
                if kpi_df is None or kpi_df.empty:
                    raise ValueError("No KPI data for selected date range.")
                kpi_data = kpi_df.iloc[0]

                col1.metric(
                    "Total Collisions",
                    f"{int(kpi_data['total_collisions']):,}",
                )
                col2.metric(
                    "Total Casualties",
                    f"{int(kpi_data['total_casualties']):,}",
                )
                col3.metric(
                    "Vehicles Involved",
                    f"{int(kpi_data['total_vehicles']):,}",
                )
            except Exception as e:
                st.error(f"Error calculating KPIs for selected date range: {e}")

    st.divider()

    # ==========================
    # 时间趋势：按月 / 按日
    # ==========================
    st.subheader("Trends")

    severity_type = st.radio(
        "Severity Series",
        ["Original", "Adjusted"],
        horizontal=True,
    )

    # ---------- Year/Month 模式 ----------
    if time_mode == "Year/Month":
        # 选择列：只对“按月视图”有用
        if severity_type == "Original":
            cols = "fatal, serious, slight"
        else:
            cols = "adj_fatal as fatal, adj_serious as serious, adj_slight as slight"

        try:
            # 1) 全年：按月折线（kpi_monthly）
            if selected_month == "All":
                trend_df = get_monthly_trend(con, selected_year, cols)
                if trend_df is None or trend_df.empty:
                    raise ValueError("No monthly trend data returned for the selected filters.")

                trend_long = trend_df.melt(
                    id_vars=["month_num", "month"],
                    value_vars=["fatal", "serious", "slight"],
                    var_name="severity",
                    value_name="count",
                )

                trend_long["severity"] = trend_long["severity"].str.capitalize()

                # 用 sidebar 里选的 severity 过滤
                if selected_severity:
                    trend_long = trend_long[trend_long["severity"].isin(selected_severity)]

                fig_trend = px.line(
                    trend_long,
                    x="month",
                    y="count",
                    color="severity",
                    markers=True,
                    title=f"Monthly Collisions by Severity ({selected_year}) - {severity_type}",
                    category_orders={
                        "month": [
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        ]
                    },
                )
                st.plotly_chart(fig_trend, use_container_width=True)

            # 2) 单月：按日折线（从 kpi_daily 取）
            else:
                # “Adjusted” 目前只在按月聚合时有意义，单日视图就提示一下
                if severity_type == "Adjusted":
                    st.info(
                        "Daily view currently shows original counts "
                        "(adjusted severities are only available at monthly level)."
                    )

                # 计算当月起止日期
                first_day = date(selected_year, selected_month, 1)
                last_day_num = calendar.monthrange(selected_year, selected_month)[1]
                last_day = date(selected_year, selected_month, last_day_num)

                daily_df = get_daily_trend_range(
                    con, first_day, last_day, selected_severity
                )
                if daily_df is None or daily_df.empty:
                    raise ValueError("No daily trend data returned for the selected month.")

                # severity 字段应该已经是 "Fatal"/"Serious"/"Slight"
                month_name = calendar.month_name[selected_month]

                fig_trend = px.line(
                    daily_df,
                    x="date",
                    y="count",
                    color="severity",
                    markers=True,
                    title=f"Daily Collisions by Severity in {month_name} {selected_year}",
                    labels={"date": "Date", "count": "Collisions"},
                )
                st.plotly_chart(fig_trend, use_container_width=True)

        except Exception as e:
            st.info(
                f"Could not load trends in Year/Month mode. "
                f"Ensure 'kpi_monthly' / 'kpi_daily' tables exist. Error: {e}"
            )

    # ---------- Custom Range 模式：直接按日折线 ----------
    else:
        if not date_range or len(date_range) != 2:
            st.info("Please select a valid date range to see daily trends.")
            return

        start_date, end_date = date_range

        if severity_type == "Adjusted":
            st.info(
                "Daily view in custom range currently uses original counts "
                "(adjusted severities are only available at monthly level)."
            )

        try:
            daily_df = get_daily_trend_range(
                con, start_date, end_date, selected_severity
            )
            if daily_df is None or daily_df.empty:
                raise ValueError("No daily trend data for selected date range.")

            # 画按日折线
            fig_trend = px.line(
                daily_df,
                x="date",
                y="count",
                color="severity",
                markers=True,
                title=f"Daily Collisions by Severity "
                      f"({start_date} to {end_date})",
                labels={"date": "Date", "count": "Collisions"},
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        except Exception as e:
            st.info(
                f"Could not load trends in Custom Range mode. "
                f"Ensure 'kpi_daily' table exists. Error: {e}"
            )


'''
import streamlit as st
import plotly.express as px
# from src.dashboard.data import get_kpi_data, get_monthly_trend
from src.dashboard.data import get_kpi_data, get_monthly_trend, get_daily_trend

# def render_overview_tab(con, selected_year, selected_severity):
# def render_overview_tab(con, selected_year, selected_month, selected_severity):
def render_overview_tab(con, time_mode, selected_year, selected_month, selected_severity, date_range):

    st.header('Safety Overview')

    # Top Level KPIs
    col1, col2, col3 = st.columns(3)

    # Construct columns to sum based on selection
    if not selected_severity:
        cols_coll = "0"
        cols_cas = "0"
        cols_veh = "0"
    else:
        cols_coll = " + ".join([s.lower() for s in selected_severity])
        cols_cas = " + ".join([f"{s.lower()}_casualties" for s in selected_severity])
        cols_veh = " + ".join([f"{s.lower()}_vehicles" for s in selected_severity])

    try:
        kpi_df = get_kpi_data(con, selected_year, (cols_coll, cols_cas, cols_veh))
        if kpi_df is None:
            raise ValueError('No KPI data returned for the selected filters.')
        if kpi_df.empty:
            raise ValueError('KPI query returned no rows for the selected year.')
        kpi_data = kpi_df.iloc[0]

        # Try to get previous year data
        prev_year = selected_year - 1
        try:
            kpi_prev_df = get_kpi_data(con, prev_year, (cols_coll, cols_cas, cols_veh))
            if kpi_prev_df is None or kpi_prev_df.empty:
                raise ValueError('No KPI data returned for the previous year.')
            kpi_data_prev = kpi_prev_df.iloc[0]

            # Calculate deltas
            delta_col = int(kpi_data['total_collisions'] - kpi_data_prev['total_collisions'])
            delta_cas = int(kpi_data['total_casualties'] - kpi_data_prev['total_casualties'])
            delta_veh = int(kpi_data['total_vehicles'] - kpi_data_prev['total_vehicles'])

            col1.metric('Total Collisions', f"{kpi_data['total_collisions']:,}", delta=f"{delta_col:,} vs {prev_year}")
            col2.metric('Total Casualties', f"{kpi_data['total_casualties']:,}", delta=f"{delta_cas:,} vs {prev_year}")
            col3.metric('Vehicles Involved', f"{kpi_data['total_vehicles']:,}", delta=f"{delta_veh:,} vs {prev_year}")

        except Exception:
            # Fallback if no previous year data
            col1.metric('Total Collisions', f"{kpi_data['total_collisions']:,}")
            col2.metric('Total Casualties', f"{kpi_data['total_casualties']:,}")
            col3.metric('Vehicles Involved', f"{kpi_data['total_vehicles']:,}")

    except Exception as e:
        st.error(f'Error calculating KPIs: {e}')

    st.divider()
    # Monthly Trend
        # Monthly Trend
    st.subheader('Monthly Trends')

    severity_type = st.radio('Severity Series', ['Original', 'Adjusted'], horizontal=True)

    # 选择列：只对“按月视图”有用
    if severity_type == 'Original':
        cols = "fatal, serious, slight"
    else:
        cols = "adj_fatal as fatal, adj_serious as serious, adj_slight as slight"

    try:
        # ======================
        # 1) 全年视图：按月折线
        # ======================
        if selected_month == 'All':
            trend_df = get_monthly_trend(con, selected_year, cols)
            if trend_df is None or trend_df.empty:
                raise ValueError('No monthly trend data returned for the selected filters.')

            trend_long = trend_df.melt(
                id_vars=['month_num', 'month'],
                value_vars=['fatal', 'serious', 'slight'],
                var_name='severity',
                value_name='count'
            )

            trend_long['severity'] = trend_long['severity'].str.capitalize()

            # 用 sidebar 里选的 severity 过滤
            if selected_severity:
                trend_long = trend_long[trend_long['severity'].isin(selected_severity)]

            fig_trend = px.line(
                trend_long,
                x='month',
                y='count',
                color='severity',
                markers=True,
                title=f'Monthly Collisions by Severity ({selected_year}) - {severity_type}',
                category_orders={
                    'month': [
                        'January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'
                    ]
                }
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # ======================
        # 2) 单月视图：按日折线
        # ======================
        else:
            # “Adjusted” 目前只在按月聚合时有意义，单日视图就提示一下
            if severity_type == 'Adjusted':
                st.info("Daily view currently shows original counts (adjusted severities are only available at monthly level).")

            daily_df = get_daily_trend(con, selected_year, selected_month)
            if daily_df is None or daily_df.empty:
                raise ValueError('No daily trend data returned for the selected month.')

            # 统一 severity 名字，方便和 sidebar 的 ['Fatal','Serious','Slight'] 对齐
            daily_df['severity'] = daily_df['collision_severity'].str.capitalize()

            # 过滤 sidebar 选中的严重程度
            if selected_severity:
                daily_df = daily_df[daily_df['severity'].isin(selected_severity)]

            # 月份名字（用 Python 自带）
            import calendar
            month_name = calendar.month_name[selected_month]

            fig_trend = px.line(
                daily_df,
                x='date',
                y='count',
                color='severity',
                markers=True,
                title=f'Daily Collisions by Severity in {month_name} {selected_year}',
                labels={'date': 'Date', 'count': 'Collisions'}
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.info(f"Could not load trends. Ensure required tables exist. Error: {e}")
'''
    
'''
    st.subheader('Monthly Trends')

    severity_type = st.radio('Severity Series', ['Original', 'Adjusted'], horizontal=True)

    # Select columns based on toggle
    if severity_type == 'Original':
        cols = "fatal, serious, slight"
    else:
        cols = "adj_fatal as fatal, adj_serious as serious, adj_slight as slight"

    try:
        trend_df = get_monthly_trend(con, selected_year, cols)
        if trend_df is None or trend_df.empty:
            raise ValueError('No monthly trend data returned for the selected filters.')

        # ★ 如果 sidebar 选择了具体月份，只保留对应 month_num
        #   注意：selected_month 在 filters.py 里是 ['All', 1, 2, ..., 12] 之一
        if selected_month != 'All':
            trend_df = trend_df[trend_df['month_num'] == selected_month]

        # Melt for Plotly
        trend_long = trend_df.melt(
            id_vars=['month_num', 'month'],
            value_vars=['fatal', 'serious', 'slight'],
            var_name='severity',
            value_name='count'
        )

        # Capitalize severity names
        trend_long['severity'] = trend_long['severity'].str.capitalize()

        # Filter by selected severity from sidebar
        if selected_severity:
            trend_long = trend_long[trend_long['severity'].isin(selected_severity)]

        fig_trend = px.line(
            trend_long,
            x='month',
            y='count',
            color='severity',
            markers=True,
            title=f'Monthly Collisions by Severity ({selected_year}) - {severity_type}',
            category_orders={
                'month': [
                    'January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'
                ]
            }
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    except Exception as e:
        st.info(f"Could not load monthly trends. Ensure 'kpi_monthly' table exists. Error: {e}")
'''