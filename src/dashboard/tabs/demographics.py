'''
import streamlit as st
import plotly.express as px
from src.dashboard.data import get_demographics_data

def render_demographics_tab(con, selected_year, severity_filter):
    st.header('Mode & Demographics')

    # Layout
    col_demo_charts, col_demo_filters = st.columns([3, 1])

    with col_demo_filters:
        st.subheader('Demographic Filters')

        # Casualty Class
        cas_classes = ['Driver or rider', 'Passenger', 'Pedestrian']
        sel_cas_class = st.multiselect('Casualty Class', cas_classes, default=cas_classes)

        # Sex
        sex_options = ['Male', 'Female']
        sel_sex = st.multiselect('Sex', sex_options, default=sex_options)

        # Age Group
        age_options = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']
        sel_age = st.multiselect('Age Group', age_options, default=age_options)

    # Construct Filters
    filters = []
    if sel_cas_class:
        if len(sel_cas_class) == 1:
            filters.append(f" AND c.casualty_class = '{sel_cas_class[0]}'")
        else:
            filters.append(f" AND c.casualty_class IN {tuple(sel_cas_class)}")

    if sel_sex:
        if len(sel_sex) == 1:
            filters.append(f" AND c.sex_of_casualty = '{sel_sex[0]}'")
        else:
            filters.append(f" AND c.sex_of_casualty IN {tuple(sel_sex)}")

    if sel_age:
        if len(sel_age) == 1:
            filters.append(f" AND c.age_group = '{sel_age[0]}'")
        else:
            filters.append(f" AND c.age_group IN {tuple(sel_age)}")

    try:
        demo_df = get_demographics_data(con, selected_year, severity_filter, filters)

        if demo_df is None or getattr(demo_df, 'empty', True):
            st.warning('No casualty data found with selected filters.')
        else:
            with col_demo_charts:
                # 1. Casualties by Mode (Casualty Type)
                mode_df = demo_df.groupby(['casualty_type', 'casualty_severity'])['count'].sum().reset_index()
                mode_order = mode_df.groupby('casualty_type')['count'].sum().sort_values(ascending=True).index.tolist()

                fig_mode = px.bar(
                    mode_df,
                    y='casualty_type',
                    x='count',
                    color='casualty_severity',
                    title='Casualties by Transport Mode',
                    orientation='h',
                    category_orders={'casualty_type': mode_order}
                )
                st.plotly_chart(fig_mode, use_container_width=True)

                # 2. Demographics: Age & Sex
                age_sex_df = demo_df.groupby(['age_group', 'sex_of_casualty'])['count'].sum().reset_index()
                age_order = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']

                fig_age = px.bar(
                    age_sex_df,
                    x='age_group',
                    y='count',
                    color='sex_of_casualty',
                    barmode='group',
                    title='Casualties by Age Group and Sex',
                    category_orders={'age_group': age_order}
                )
                st.plotly_chart(fig_age, use_container_width=True)

    except Exception as e:
        st.error(f'Error loading demographics: {e}')
'''
'''
# src/dashboard/tabs/demographics.py
import streamlit as st
import plotly.express as px
from src.dashboard.data import get_demographics_data

def render_demographics_tab(con, selected_year, selected_month, severity_filter):
    st.header('Mode & Demographics')

    # Layout
    col_demo_charts, col_demo_filters = st.columns([3, 1])

    with col_demo_filters:
        st.subheader('Demographic Filters')

        # Casualty Class
        cas_classes = ['Driver or rider', 'Passenger', 'Pedestrian']
        sel_cas_class = st.multiselect('Casualty Class', cas_classes, default=cas_classes)

        # Sex
        sex_options = ['Male', 'Female']
        sel_sex = st.multiselect('Sex', sex_options, default=sex_options)

        # Age Group
        age_options = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']
        sel_age = st.multiselect('Age Group', age_options, default=age_options)

    # Construct Filters
    filters = []
    if sel_cas_class:
        if len(sel_cas_class) == 1:
            filters.append(f" AND c.casualty_class = '{sel_cas_class[0]}'")
        else:
            filters.append(f" AND c.casualty_class IN {tuple(sel_cas_class)}")

    if sel_sex:
        if len(sel_sex) == 1:
            filters.append(f" AND c.sex_of_casualty = '{sel_sex[0]}'")
        else:
            filters.append(f" AND c.sex_of_casualty IN {tuple(sel_sex)}")

    if sel_age:
        if len(sel_age) == 1:
            filters.append(f" AND c.age_group = '{sel_age[0]}'")
        else:
            filters.append(f" AND c.age_group IN {tuple(sel_age)}")

    # ★ Month Filter：在 master/collision 里我们有 month_num
    if selected_month == 'All':
        month_filter = ""
    else:
        month_filter = f" AND month_num = {selected_month}"

    try:
        # ★ 多传一个 month_filter
        demo_df = get_demographics_data(con, selected_year, month_filter, severity_filter, filters)

        if demo_df is None or getattr(demo_df, 'empty', True):
            st.warning('No casualty data found with selected filters.')
        else:
            with col_demo_charts:
                # 1. Casualties by Mode (Casualty Type)
                mode_df = demo_df.groupby(['casualty_type', 'casualty_severity'])['count'].sum().reset_index()
                mode_order = mode_df.groupby('casualty_type')['count'].sum().sort_values(ascending=True).index.tolist()

                fig_mode = px.bar(
                    mode_df,
                    y='casualty_type',
                    x='count',
                    color='casualty_severity',
                    title='Casualties by Transport Mode',
                    orientation='h',
                    category_orders={'casualty_type': mode_order}
                )
                st.plotly_chart(fig_mode, use_container_width=True)

                # 2. Demographics: Age & Sex
                age_sex_df = demo_df.groupby(['age_group', 'sex_of_casualty'])['count'].sum().reset_index()
                age_order = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']

                fig_age = px.bar(
                    age_sex_df,
                    x='age_group',
                    y='count',
                    color='sex_of_casualty',
                    barmode='group',
                    title='Casualties by Age Group and Sex',
                    category_orders={'age_group': age_order}
                )
                st.plotly_chart(fig_age, use_container_width=True)

    except Exception as e:
        st.error(f'Error loading demographics: {e}')
'''

import streamlit as st
import plotly.express as px
from src.dashboard.data import get_demographics_data

def render_demographics_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range):
    st.header('Mode & Demographics')

    col_demo_charts, col_demo_filters = st.columns([3, 1])

    with col_demo_filters:
        st.subheader('Demographic Filters')

        cas_classes = ['Driver or rider', 'Passenger', 'Pedestrian']
        sel_cas_class = st.multiselect('Casualty Class', cas_classes, default=cas_classes)

        sex_options = ['Male', 'Female']
        sel_sex = st.multiselect('Sex', sex_options, default=sex_options)

        age_options = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']
        sel_age = st.multiselect('Age Group', age_options, default=age_options)

    # ============ 构造人口过滤条件 ============
    filters = []
    if sel_cas_class:
        if len(sel_cas_class) == 1:
            filters.append(f" AND c.casualty_class = '{sel_cas_class[0]}'")
        else:
            filters.append(f" AND c.casualty_class IN {tuple(sel_cas_class)}")

    if sel_sex:
        if len(sel_sex) == 1:
            filters.append(f" AND c.sex_of_casualty = '{sel_sex[0]}'")
        else:
            filters.append(f" AND c.sex_of_casualty IN {tuple(sel_sex)}")

    if sel_age:
        if len(sel_age) == 1:
            filters.append(f" AND c.age_group = '{sel_age[0]}'")
        else:
            filters.append(f" AND c.age_group IN {tuple(sel_age)}")

    # ============ 时间过滤（注意 alias 是 col.） ============
    if time_mode == "Year/Month":
        if selected_year is None:
            st.error("Please select a year.")
            return

        if selected_month == 'All':
            time_filter = f" AND col.year = {selected_year}"
        else:
            time_filter = f" AND col.year = {selected_year} AND month(col.date) = {selected_month}"
    else:
        if not date_range or len(date_range) != 2:
            st.error("Please select a valid date range.")
            return
        start_date, end_date = date_range
        time_filter = f" AND col.date BETWEEN '{start_date}' AND '{end_date}'"

    try:
        # ★ 现在传 time_filter
        demo_df = get_demographics_data(con, time_filter, severity_filter, filters)

        if demo_df is None or getattr(demo_df, 'empty', True):
            st.warning('No casualty data found with selected filters.')
            return

        with col_demo_charts:
            # 1) 按交通方式和严重程度
            mode_df = demo_df.groupby(['casualty_type', 'casualty_severity'])['count'].sum().reset_index()
            mode_order = mode_df.groupby('casualty_type')['count'].sum().sort_values(ascending=True).index.tolist()

            fig_mode = px.bar(
                mode_df,
                y='casualty_type',
                x='count',
                color='casualty_severity',
                title='Casualties by Transport Mode',
                orientation='h',
                category_orders={'casualty_type': mode_order}
            )
            st.plotly_chart(fig_mode, use_container_width=True)

            # 2) 年龄 × 性别
            age_sex_df = demo_df.groupby(['age_group', 'sex_of_casualty'])['count'].sum().reset_index()
            age_order = ['Child', 'Young Adult', 'Adult', 'Senior', 'Unknown']

            fig_age = px.bar(
                age_sex_df,
                x='age_group',
                y='count',
                color='sex_of_casualty',
                barmode='group',
                title='Casualties by Age Group and Sex',
                category_orders={'age_group': age_order}
            )
            st.plotly_chart(fig_age, use_container_width=True)

    except Exception as e:
        st.error(f'Error loading demographics: {e}')
