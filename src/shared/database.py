import duckdb
import streamlit as st
from .config import DB_PATH

@st.cache_resource
def get_connection():
    """
    Establishes a connection to the DuckDB database.
    Returns a DuckDB connection object or None if failed.
    """
    if not DB_PATH.exists():
        st.error(f'Database file not found at {DB_PATH}')
        return None

    try:
        # DuckDB requires string path.
        con = duckdb.connect(str(DB_PATH), read_only=True)
        return con
    except Exception as e:
        st.error(f'Failed to connect to database: {e}')
        return None

@st.cache_data
def run_query(query, _con):
    """
    Executes a SQL query and returns the result as a DataFrame.
    Uses caching to improve performance.
    """
    if _con is None:
        return None
    return _con.execute(query).fetchdf()
