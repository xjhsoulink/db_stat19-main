# app.py
import streamlit as st
from src.shared.database import get_connection
from src.dashboard.components.filters import render_sidebar
from src.dashboard.tabs.overview import render_overview_tab
from src.dashboard.tabs.heatmap import render_heatmap_tab
from src.dashboard.tabs.demographics import render_demographics_tab
from src.dashboard.tabs.environment import render_environment_tab

st.set_page_config(
    page_title='GB Road Safety Dashboard',
    page_icon='🚗',
    layout='wide'
)

def main():
    st.title('Great Britain Road Safety Data (STATS19)')
    st.markdown('Analysis of police-reported road traffic collisions (2000–2024)')

    con = get_connection()
    if not con:
        st.stop()

    # ★ filters.py 应该返回这 6 个东西（下面会统一用）
    time_mode, selected_year, selected_month, selected_severity, severity_filter, date_range = render_sidebar(con)

    tab1, tab2, tab3, tab4 = st.tabs(['Overview', 'Heatmap', 'Mode & Demographics', 'Road & Environment'])

    with tab1:
        render_overview_tab(con, time_mode, selected_year, selected_month, selected_severity, date_range)

    with tab2:
        render_heatmap_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)

    with tab3:
        render_demographics_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)

    with tab4:
        render_environment_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)

if __name__ == "__main__":
    main()


'''
import streamlit as st
from src.shared.database import get_connection
from src.dashboard.components.filters import render_sidebar
from src.dashboard.tabs.overview import render_overview_tab
from src.dashboard.tabs.heatmap import render_heatmap_tab
from src.dashboard.tabs.demographics import render_demographics_tab
from src.dashboard.tabs.environment import render_environment_tab

# Page config
st.set_page_config(
    page_title='GB Road Safety Dashboard',
    page_icon='🚗',
    layout='wide'
)

def main():
    st.title('Great Britain Road Safety Data (STATS19)')
    st.markdown('Analysis of police-reported road traffic collisions (2020-2024)')

    # Database Connection
    con = get_connection()
    if not con:
        st.stop()

    # Sidebar
    #selected_year, selected_severity, severity_filter = render_sidebar(con)
    #selected_year, selected_month, selected_severity, severity_filter = render_sidebar(con)
    time_mode, selected_year, selected_month, selected_severity, severity_filter, date_range = render_sidebar(con)
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(['Overview', 'Heatmap', 'Mode & Demographics', 'Road & Environment'])

    with tab1:
        # 多传一个 selected_month
        render_overview_tab(con, time_mode, selected_year, selected_month, selected_severity, date_range)
    
    with tab2:
        render_heatmap_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)
        
    with tab3:
        render_demographics_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)
        
    with tab4:
        render_environment_tab(con, time_mode, selected_year, selected_month, severity_filter, date_range)


if __name__ == "__main__":
    main()
'''