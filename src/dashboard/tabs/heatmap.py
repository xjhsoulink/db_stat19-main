'''
import streamlit as st
import pydeck as pdk
from src.dashboard.data import get_map_data

# def render_heatmap_tab(con, selected_year, severity_filter):
def render_heatmap_tab(con, selected_year, selected_month, severity_filter):

    st.header('Collision Heatmap')

    # Map Controls
    col_map, col_controls = st.columns([3, 1])

    with col_controls:
        st.subheader('Map Filters')

        # Road Type
        road_types = ['Single carriageway', 'Dual carriageway', 'Roundabout', 'One way street', 'Slip road']
        sel_road_type = st.multiselect('Road Type', road_types)

        # Weather
        weather_conds = ['Fine no high winds', 'Raining no high winds', 'Raining + high winds', 'Fine + high winds', 'Snowing', 'Fog or mist']
        sel_weather = st.multiselect('Weather', weather_conds)

        # Light
        light_conds = ['Daylight', 'Darkness - lights lit', 'Darkness - lights unlit', 'Darkness - no lighting']
        sel_light = st.multiselect('Light Conditions', light_conds)

    # Construct Filters
    road_filter = ""
    if sel_road_type:
        if len(sel_road_type) == 1:
            road_filter = f" AND road_type = '{sel_road_type[0]}'"
        else:
            road_filter = f" AND road_type IN {tuple(sel_road_type)}"

    weather_filter = ""
    if sel_weather:
        if len(sel_weather) == 1:
            weather_filter = f" AND weather_conditions = '{sel_weather[0]}'"
        else:
            weather_filter = f" AND weather_conditions IN {tuple(sel_weather)}"

    light_filter = ""
    if sel_light:
        if len(sel_light) == 1:
            light_filter = f" AND light_conditions = '{sel_light[0]}'"
        else:
            light_filter = f" AND light_conditions IN {tuple(sel_light)}"

    try:
        map_df = get_map_data(con, selected_year, severity_filter, road_filter, weather_filter, light_filter)

        if map_df is None or map_df.empty:
            st.warning('No collisions found with selected filters.')
        else:
            # Fix data types for tooltip
            map_df['date'] = map_df['date'].astype(str)
            map_df['time'] = map_df['time'].astype(str)
            
            def get_color(severity):
                if severity == 'Fatal':
                    return [255, 0, 0, 160] # Red
                elif severity == 'Serious':
                    return [255, 165, 0, 160] # Orange
                else:
                    return [0, 128, 255, 160] # Blue for Slight

            map_df['color'] = map_df['collision_severity'].apply(get_color)

            # PyDeck Layer: ScatterplotLayer
            layer = pdk.Layer(
                'ScatterplotLayer',
                map_df,
                get_position=['longitude', 'latitude'],
                get_fill_color='color',
                get_radius=30,
                pickable=True,
                opacity=0.8,
                stroked=True,
                filled=True,
                radius_min_pixels=3,
                radius_max_pixels=30,
            )

            # Set the viewport location
            mid_lat = map_df['latitude'].mean()
            mid_lon = map_df['longitude'].mean()

            view_state = pdk.ViewState(
                longitude=mid_lon,
                latitude=mid_lat,
                zoom=6,
                min_zoom=5,
                max_zoom=18,
                pitch=0,
                bearing=0,
            )

            # Render
            with col_map:
                st.markdown("""
                <style>
                .stDeckGlJsonChart {
                    height: 700px !important;
                }
                </style>
                """, unsafe_allow_html=True)

                deck = pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={  # type: ignore
                        'html': '<b>Severity:</b> {collision_severity}<br/>'
                                '<b>Date:</b> {date}<br/>'
                                '<b>Time:</b> {time}<br/>'
                                '<b>Casualties:</b> {number_of_casualties}<br/>'
                                '<b>Vehicles:</b> {number_of_vehicles}',
                        'style': {
                            'backgroundColor': 'steelblue',
                            'color': 'white'
                        }
                    }
                )
                st.pydeck_chart(deck, use_container_width=True)
                st.caption(f'Showing {len(map_df)} collisions.')

    except Exception as e:
        st.error(f'Error loading map: {e}')
'''
'''
# src/dashboard/tabs/heatmap.py
import streamlit as st
import pydeck as pdk
from src.dashboard.data import get_map_data

def render_heatmap_tab(con, selected_year, selected_month, severity_filter):
    st.header('Collision Heatmap')

    # Map Controls
    col_map, col_controls = st.columns([3, 1])

    with col_controls:
        st.subheader('Map Filters')

        # Road Type
        road_types = ['Single carriageway', 'Dual carriageway', 'Roundabout', 'One way street', 'Slip road']
        sel_road_type = st.multiselect('Road Type', road_types)

        # Weather
        weather_conds = ['Fine no high winds', 'Raining no high winds', 'Raining + high winds', 'Fine + high winds', 'Snowing', 'Fog or mist']
        sel_weather = st.multiselect('Weather', weather_conds)

        # Light
        light_conds = ['Daylight', 'Darkness - lights lit', 'Darkness - lights unlit', 'Darkness - no lighting']
        sel_light = st.multiselect('Light Conditions', light_conds)

    # ---------- Construct Filters ----------
    road_filter = ""
    if sel_road_type:
        if len(sel_road_type) == 1:
            road_filter = f" AND road_type = '{sel_road_type[0]}'"
        else:
            road_filter = f" AND road_type IN {tuple(sel_road_type)}"

    weather_filter = ""
    if sel_weather:
        if len(sel_weather) == 1:
            weather_filter = f" AND weather_conditions = '{sel_weather[0]}'"
        else:
            weather_filter = f" AND weather_conditions IN {tuple(sel_weather)}"

    light_filter = ""
    if sel_light:
        if len(sel_light) == 1:
            light_filter = f" AND light_conditions = '{sel_light[0]}'"
        else:
            light_filter = f" AND light_conditions IN {tuple(sel_light)}"

    # ★ Month Filter：基于 collision_geopoints 里的 date 字段
    #   选 All 不加条件；选具体月份用 DuckDB 的 month(date) 函数
    if selected_month == 'All':
        month_filter = ""
    else:
        month_filter = f" AND month(date) = {selected_month}"

    try:
        # ★ 多传一个 month_filter
        map_df = get_map_data(
            con,
            selected_year,
            month_filter,
            severity_filter,
            road_filter,
            weather_filter,
            light_filter,
        )

        if map_df is None or map_df.empty:
            st.warning('No collisions found with selected filters.')
        else:
            # Fix data types for tooltip
            map_df['date'] = map_df['date'].astype(str)
            map_df['time'] = map_df['time'].astype(str)
            
            def get_color(severity):
                if severity == 'Fatal':
                    return [255, 0, 0, 160]  # Red
                elif severity == 'Serious':
                    return [255, 165, 0, 160]  # Orange
                else:
                    return [0, 128, 255, 160]  # Blue for Slight

            map_df['color'] = map_df['collision_severity'].apply(get_color)

            # PyDeck Layer: ScatterplotLayer
            layer = pdk.Layer(
                'ScatterplotLayer',
                map_df,
                get_position=['longitude', 'latitude'],
                get_fill_color='color',
                get_radius=30,
                pickable=True,
                opacity=0.8,
                stroked=True,
                filled=True,
                radius_min_pixels=3,
                radius_max_pixels=30,
            )

            # Set the viewport location
            mid_lat = map_df['latitude'].mean()
            mid_lon = map_df['longitude'].mean()

            view_state = pdk.ViewState(
                longitude=mid_lon,
                latitude=mid_lat,
                zoom=6,
                min_zoom=5,
                max_zoom=18,
                pitch=0,
                bearing=0,
            )

            # Render
            with col_map:
                st.markdown("""
                <style>
                .stDeckGlJsonChart {
                    height: 700px !important;
                }
                </style>
                """, unsafe_allow_html=True)

                deck = pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={  # type: ignore
                        'html': '<b>Severity:</b> {collision_severity}<br/>'
                                '<b>Date:</b> {date}<br/>'
                                '<b>Time:</b> {time}<br/>'
                                '<b>Casualties:</b> {number_of_casualties}<br/>'
                                '<b>Vehicles:</b> {number_of_vehicles}',
                        'style': {
                            'backgroundColor': 'steelblue',
                            'color': 'white'
                        }
                    }
                )
                st.pydeck_chart(deck, use_container_width=True)
                st.caption(f'Showing {len(map_df)} collisions.')

    except Exception as e:
        st.error(f'Error loading map: {e}')
'''

import streamlit as st
import pydeck as pdk
from src.dashboard.data import get_map_data

def render_heatmap_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range):
    st.header('Collision Heatmap')

    # ============ 时间过滤片段：给 collision_geopoints 用 ============
    if time_mode == "Year/Month":
        if selected_year is None:
            st.error("Please select a year.")
            return

        if selected_month == 'All':
            # 只按年份过滤
            time_filter = f" AND year = {selected_year}"
        else:
            # 年份 + 指定月份
            time_filter = f" AND year = {selected_year} AND month(date) = {selected_month}"
    else:
        if not date_range or len(date_range) != 2:
            st.error("Please select a valid date range.")
            return
        start_date, end_date = date_range
        time_filter = f" AND date BETWEEN '{start_date}' AND '{end_date}'"

    # ============ 右侧控制面板 ============
    col_map, col_controls = st.columns([3, 1])

    with col_controls:
        st.subheader('Map Filters')

        # Road Type
        road_types = ['Single carriageway', 'Dual carriageway', 'Roundabout',
                      'One way street', 'Slip road']
        sel_road_type = st.multiselect('Road Type', road_types)

        # Weather
        weather_conds = [
            'Fine no high winds',
            'Raining no high winds',
            'Raining + high winds',
            'Fine + high winds',
            'Snowing',
            'Fog or mist'
        ]
        sel_weather = st.multiselect('Weather', weather_conds)

        # Light
        light_conds = [
            'Daylight',
            'Darkness - lights lit',
            'Darkness - lights unlit',
            'Darkness - no lighting'
        ]
        sel_light = st.multiselect('Light Conditions', light_conds)

    # ============ 其他过滤条件 ============
    road_filter = ""
    if sel_road_type:
        if len(sel_road_type) == 1:
            road_filter = f" AND road_type = '{sel_road_type[0]}'"
        else:
            road_filter = f" AND road_type IN {tuple(sel_road_type)}"

    weather_filter = ""
    if sel_weather:
        if len(sel_weather) == 1:
            weather_filter = f" AND weather_conditions = '{sel_weather[0]}'"
        else:
            weather_filter = f" AND weather_conditions IN {tuple(sel_weather)}"

    light_filter = ""
    if sel_light:
        if len(sel_light) == 1:
            light_filter = f" AND light_conditions = '{sel_light[0]}'"
        else:
            light_filter = f" AND light_conditions IN {tuple(sel_light)}"

    # ============ 查询 & 画图 ============
    try:
        # ★ 现在传的是 time_filter（包含 year/月/日期范围）
        map_df = get_map_data(
            con,
            time_filter,
            severity_filter,
            road_filter,
            weather_filter,
            light_filter,
        )

        if map_df is None or map_df.empty:
            st.warning('No collisions found with selected filters.')
            return

        # Tooltip 需要字符串
        map_df['date'] = map_df['date'].astype(str)
        map_df['time'] = map_df['time'].astype(str)

        def get_color(severity):
            if severity == 'Fatal':
                return [255, 0, 0, 160]      # Red
            elif severity == 'Serious':
                return [255, 165, 0, 160]    # Orange
            else:
                return [0, 128, 255, 160]    # Blue

        map_df['color'] = map_df['collision_severity'].apply(get_color)

        # Deck.gl 图层
        layer = pdk.Layer(
            'ScatterplotLayer',
            map_df,
            get_position=['longitude', 'latitude'],
            get_fill_color='color',
            get_radius=30,
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
            radius_min_pixels=3,
            radius_max_pixels=30,
        )

        # 视角位置
        mid_lat = map_df['latitude'].mean()
        mid_lon = map_df['longitude'].mean()

        view_state = pdk.ViewState(
            longitude=mid_lon,
            latitude=mid_lat,
            zoom=6,
            min_zoom=5,
            max_zoom=18,
            pitch=0,
            bearing=0,
        )

        with col_map:
            st.markdown("""
            <style>
            .stDeckGlJsonChart {
                height: 700px !important;
            }
            </style>
            """, unsafe_allow_html=True)

            deck = pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={
                    'html': '<b>Severity:</b> {collision_severity}<br/>'
                            '<b>Date:</b> {date}<br/>'
                            '<b>Time:</b> {time}<br/>'
                            '<b>Casualties:</b> {number_of_casualties}<br/>'
                            '<b>Vehicles:</b> {number_of_vehicles}',
                    'style': {
                        'backgroundColor': 'steelblue',
                        'color': 'white'
                    }
                }
            )
            st.pydeck_chart(deck, use_container_width=True)
            st.caption(f'Showing {len(map_df)} collisions.')

    except Exception as e:
        st.error(f'Error loading map: {e}')
