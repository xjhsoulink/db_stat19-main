'''
import streamlit as st
import plotly.express as px
from src.dashboard.data import get_factor_data, get_interaction_data

def render_environment_tab(con, selected_year, severity_filter):
    st.header('Road & Environment Analysis')

    col_env_charts, col_env_controls = st.columns([3, 1])

    with col_env_controls:
        st.subheader('Analysis Settings')

        # Factor Selection
        factors = {
            'Speed Limit': 'speed_limit',
            'Road Type': 'road_type',
            'Weather': 'weather_conditions',
            'Light Conditions': 'light_conditions',
            'Road Surface': 'road_surface_conditions',
            'Junction Detail': 'junction_detail',
            'Urban/Rural': 'urban_or_rural_area'
        }

        primary_label = st.selectbox('Primary Factor', list(factors.keys()), index=0)
        primary_col = factors[primary_label]

        secondary_label = st.selectbox('Secondary Factor (Optional)', ['None'] + list(factors.keys()), index=0)

    with col_env_charts:
        # 1. Primary Factor Analysis
        st.subheader(f'Collisions by {primary_label}')

        try:
            df_1 = get_factor_data(con, selected_year, severity_filter, primary_col)

            if df_1 is None or df_1.empty:
                st.warning('No data found.')
            else:
                # Bar Chart
                fig_1 = px.bar(
                    df_1,
                    x=primary_col,
                    y='count',
                    color='collision_severity',
                    title=f'Collision Severity by {primary_label}',
                    labels={primary_col: primary_label, 'count': 'Number of Collisions'}
                )
                st.plotly_chart(fig_1, use_container_width=True)

                # 2. Secondary Factor Analysis (Cross-tab)
                if secondary_label != 'None' and secondary_label != primary_label:
                    secondary_col = factors[secondary_label]

                    st.divider()
                    st.subheader(f'Interaction: {primary_label} vs {secondary_label}')

                    df_2 = get_interaction_data(con, selected_year, severity_filter, primary_col, secondary_col)

                    if df_2 is not None and not df_2.empty:
                        # Heatmap
                        pivot_df = df_2.pivot(index=primary_col, columns=secondary_col, values='count').fillna(0)

                        fig_2 = px.imshow(
                            pivot_df,
                            labels=dict(x=secondary_label, y=primary_label, color='Collisions'),
                            x=pivot_df.columns,
                            y=pivot_df.index,
                            title=f'Heatmap: {primary_label} vs {secondary_label}',
                            aspect='auto'
                        )
                        st.plotly_chart(fig_2, use_container_width=True)

        except Exception as e:
            st.error(f'Error analyzing environment factors: {e}')
'''
'''
# src/dashboard/tabs/environment.py
import streamlit as st
import plotly.express as px
from src.dashboard.data import get_factor_data, get_interaction_data

def render_environment_tab(con, selected_year, selected_month, severity_filter):
    st.header('Road & Environment Analysis')

    # ★ Month filter: 选 All 就不限制月份；选 1~12 就用 month_num 过滤
    if selected_month == 'All':
        month_filter = ""
    else:
        # collision 表里我们在 ETL 时已经加了 month_num
        month_filter = f" AND month_num = {selected_month}"

    col_env_charts, col_env_controls = st.columns([3, 1])

    with col_env_controls:
        st.subheader('Analysis Settings')

        # Factor Selection
        factors = {
            'Speed Limit': 'speed_limit',
            'Road Type': 'road_type',
            'Weather': 'weather_conditions',
            'Light Conditions': 'light_conditions',
            'Road Surface': 'road_surface_conditions',
            'Junction Detail': 'junction_detail',
            'Urban/Rural': 'urban_or_rural_area'
        }

        primary_label = st.selectbox('Primary Factor', list(factors.keys()), index=0)
        primary_col = factors[primary_label]

        secondary_label = st.selectbox(
            'Secondary Factor (Optional)',
            ['None'] + list(factors.keys()),
            index=0
        )

    with col_env_charts:
        # 1. Primary Factor Analysis
        st.subheader(f'Collisions by {primary_label}')

        try:
            # ★ 多传一个 month_filter
            df_1 = get_factor_data(con, selected_year, month_filter, severity_filter, primary_col)

            if df_1 is None or df_1.empty:
                st.warning('No data found.')
            else:
                # Bar Chart
                fig_1 = px.bar(
                    df_1,
                    x=primary_col,
                    y='count',
                    color='collision_severity',
                    title=f'Collision Severity by {primary_label}',
                    labels={primary_col: primary_label, 'count': 'Number of Collisions'}
                )
                st.plotly_chart(fig_1, use_container_width=True)

                # 2. Secondary Factor Analysis (Cross-tab)
                if secondary_label != 'None' and secondary_label != primary_label:
                    secondary_col = factors[secondary_label]

                    st.divider()
                    st.subheader(f'Interaction: {primary_label} vs {secondary_label}')

                    # ★ 这里也多传 month_filter
                    df_2 = get_interaction_data(
                        con,
                        selected_year,
                        month_filter,
                        severity_filter,
                        primary_col,
                        secondary_col
                    )

                    if df_2 is not None and not df_2.empty:
                        # Heatmap
                        pivot_df = df_2.pivot(
                            index=primary_col,
                            columns=secondary_col,
                            values='count'
                        ).fillna(0)

                        fig_2 = px.imshow(
                            pivot_df,
                            labels=dict(
                                x=secondary_label,
                                y=primary_label,
                                color='Collisions'
                            ),
                            x=pivot_df.columns,
                            y=pivot_df.index,
                            title=f'Heatmap: {primary_label} vs {secondary_label}',
                            aspect='auto'
                        )
                        st.plotly_chart(fig_2, use_container_width=True)

        except Exception as e:
            st.error(f'Error analyzing environment factors: {e}')
'''

import streamlit as st
import plotly.express as px
from src.dashboard.data import get_factor_data, get_interaction_data

def render_environment_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range):
    st.header('Road & Environment Analysis')

    # ============ 时间过滤（collision 表） ============
    if time_mode == "Year/Month":
        if selected_year is None:
            st.error("Please select a year.")
            return

        if selected_month == 'All':
            time_filter = f" AND year = {selected_year}"
        else:
            time_filter = f" AND year = {selected_year} AND month(date) = {selected_month}"
    else:
        if not date_range or len(date_range) != 2:
            st.error("Please select a valid date range.")
            return
        start_date, end_date = date_range
        time_filter = f" AND date BETWEEN '{start_date}' AND '{end_date}'"

    col_env_charts, col_env_controls = st.columns([3, 1])

    with col_env_controls:
        st.subheader('Analysis Settings')

        factors = {
            'Speed Limit': 'speed_limit',
            'Road Type': 'road_type',
            'Weather': 'weather_conditions',
            'Light Conditions': 'light_conditions',
            'Road Surface': 'road_surface_conditions',
            'Junction Detail': 'junction_detail',
            'Urban/Rural': 'urban_or_rural_area'
        }

        primary_label = st.selectbox('Primary Factor', list(factors.keys()), index=0)
        primary_col = factors[primary_label]

        secondary_label = st.selectbox(
            'Secondary Factor (Optional)',
            ['None'] + list(factors.keys()),
            index=0
        )

    with col_env_charts:
        st.subheader(f'Collisions by {primary_label}')

        try:
            # ★ 现在传 time_filter
            df_1 = get_factor_data(con, time_filter, severity_filter, primary_col)

            if df_1 is None or df_1.empty:
                st.warning('No data found.')
                return

            fig_1 = px.bar(
                df_1,
                x=primary_col,
                y='count',
                color='collision_severity',
                title=f'Collision Severity by {primary_label}',
                labels={primary_col: primary_label, 'count': 'Number of Collisions'}
            )
            st.plotly_chart(fig_1, use_container_width=True)

            # 二维交互热力图
            if secondary_label != 'None' and secondary_label != primary_label:
                secondary_col = factors[secondary_label]

                st.divider()
                st.subheader(f'Interaction: {primary_label} vs {secondary_label}')

                df_2 = get_interaction_data(
                    con,
                    time_filter,
                    severity_filter,
                    primary_col,
                    secondary_col
                )

                if df_2 is not None and not df_2.empty:
                    pivot_df = df_2.pivot(
                        index=primary_col,
                        columns=secondary_col,
                        values='count'
                    ).fillna(0)

                    fig_2 = px.imshow(
                        pivot_df,
                        labels=dict(
                            x=secondary_label,
                            y=primary_label,
                            color='Collisions'
                        ),
                        x=pivot_df.columns,
                        y=pivot_df.index,
                        title=f'Heatmap: {primary_label} vs {secondary_label}',
                        aspect='auto'
                    )
                    st.plotly_chart(fig_2, use_container_width=True)

        except Exception as e:
            st.error(f'Error analyzing environment factors: {e}')
