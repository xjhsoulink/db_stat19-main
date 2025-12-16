# file: src/dashboard/components/filters.py
import streamlit as st
from src.dashboard.data import get_years, get_date_range


def render_sidebar(con):
    st.sidebar.title('Filters')

    time_mode = st.sidebar.radio(
        "Time Mode",
        ["Year/Month", "Custom Range"],
        index=0
    )

    if time_mode == "Year/Month":
        years = get_years(con)
        years = sorted({int(round(y)) for y in years}, reverse=True)
        selected_year = st.sidebar.selectbox('Select Year', years, index=0)

        month_options = ['All'] + list(range(1, 13))
        selected_month = st.sidebar.selectbox('Select Month', month_options, index=0)

        date_range = None
    else:
        min_date, max_date = get_date_range(con)
        if min_date is None:
            st.error("No date information found.")
            st.stop()

        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        selected_year = None
        selected_month = 'All'

    # Severity Filter
    severity_options = ['Fatal', 'Serious', 'Slight']
    selected_severity = st.sidebar.multiselect(
        'Severity',
        severity_options,
        default=severity_options
    )

    # Construct Severity Filter Expression (NO leading AND)
    if not selected_severity:
        severity_filter = "1=0"  # no selection => return empty result
    elif len(selected_severity) == 1:
        severity_filter = f"collision_severity = '{selected_severity[0]}'"
    else:
        quoted = ",".join([f"'{s}'" for s in selected_severity])
        severity_filter = f"collision_severity IN ({quoted})"

    return time_mode, selected_year, selected_month, selected_severity, severity_filter, date_range
