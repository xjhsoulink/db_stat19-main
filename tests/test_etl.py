import pytest
import duckdb
import pandas as pd
import os

DB_PATH = 'road_safety.duckdb'

@pytest.fixture(scope="module")
def db_con():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Database {DB_PATH} not found. Run ETL first.")
    con = duckdb.connect(DB_PATH, read_only=True)
    yield con
    con.close()

def test_tables_exist(db_con):
    """Check that all required tables exist."""
    required_tables = ['collision', 'vehicle', 'casualty', 'kpi_monthly', 'code_map']
    tables = db_con.execute("SHOW TABLES").fetchdf()['name'].tolist()
    for table in required_tables:
        assert table in tables, f"Table {table} is missing from database"

def test_coordinates_validity(db_con):
    """Check that mapped coordinates are within GB bounds roughly."""
    # GB bounding box approx: Lat 49-61, Lon -8 to 2
    # We allow some margin or check for NULLs if that's expected, 
    # but the proposal says "drop records with missing or invalid latitude or longitude"
    # So we expect valid coordinates for the cleaned dataset if we filtered them.
    # However, clean_stats19.py currently keeps them but format_sf drops them for the geo part.
    # The 'collision' table in DuckDB comes from the cleaned CSV.
    # Let's check if there are any wildly invalid coordinates that are NOT null.
    
    query = """
        SELECT count(*) 
        FROM collision 
        WHERE (latitude < 49 OR latitude > 61 OR longitude < -8 OR longitude > 2)
        AND latitude IS NOT NULL
    """
    result = db_con.execute(query).fetchone()[0]
    # This might fail if there are outliers, but it's a good check.
    assert result == 0, f"Found {result} records with invalid coordinates (outside GB bounds)"

def test_severity_codes(db_con):
    """Check that severity is decoded (strings, not numbers)."""
    query = "SELECT DISTINCT collision_severity FROM collision"
    severities = [x[0] for x in db_con.execute(query).fetchall()]
    expected = {'Fatal', 'Serious', 'Slight'}
    
    # Check if we have any unexpected values
    current = set(severities)
    assert current.issubset(expected), f"Unexpected severity values found: {current - expected}"
    assert len(current) > 0, "No severity values found"

def test_date_consistency(db_con):
    """Check derived time features match the date."""
    # Check year
    query = """
        SELECT count(*) 
        FROM collision 
        WHERE year != date_part('year', date)
    """
    result = db_con.execute(query).fetchone()[0]
    assert result == 0, "Mismatch between 'year' column and 'date' column"

def test_kpi_monthly_aggregation(db_con):
    """Verify kpi_monthly matches raw collision counts."""
    # Pick a random year/month to check
    query_agg = "SELECT sum(fatal + serious + slight) FROM kpi_monthly WHERE year = 2022"
    query_raw = "SELECT count(*) FROM collision WHERE year = 2022"
    
    agg_count = db_con.execute(query_agg).fetchone()[0]
    raw_count = db_con.execute(query_raw).fetchone()[0]
    
    # Handle None if no data
    if raw_count is None: raw_count = 0
    if agg_count is None: agg_count = 0
    
    assert agg_count == raw_count, f"KPI Aggregation mismatch: {agg_count} vs {raw_count}"

def test_foreign_key_consistency(db_con):
    """
    Check that all vehicles and casualties are linked to a valid collision.
    This ensures referential integrity between fact tables.
    """
    # Check Vehicle -> Collision
    # Note: We use LEFT JOIN and check for NULLs on the right side
    query_veh = """
        SELECT count(*) 
        FROM vehicle v 
        LEFT JOIN collision c ON v.collision_index = c.collision_index 
        WHERE c.collision_index IS NULL
    """
    orphaned_vehicles = db_con.execute(query_veh).fetchone()[0]
    
    # Check Casualty -> Collision
    query_cas = """
        SELECT count(*) 
        FROM casualty cas 
        LEFT JOIN collision c ON cas.collision_index = c.collision_index 
        WHERE c.collision_index IS NULL
    """
    orphaned_casualties = db_con.execute(query_cas).fetchone()[0]
    
    assert orphaned_vehicles == 0, f"Found {orphaned_vehicles} vehicles with invalid collision_index"
    assert orphaned_casualties == 0, f"Found {orphaned_casualties} casualties with invalid collision_index"

def test_categorical_values_validity(db_con):
    """
    Verify that categorical columns contain only valid labels defined in the schema (code_map).
    We check a few key columns to ensure the mapping process worked correctly.
    """
    # Define columns to check: (table, column_name, schema_variable_name)
    checks = [
        ('collision', 'road_surface_conditions', 'road_surface_conditions'),
        ('collision', 'weather_conditions', 'weather_conditions'),
        ('casualty', 'casualty_severity', 'casualty_severity'),
        ('vehicle', 'vehicle_type', 'vehicle_type')
    ]
    
    for table, col, var_name in checks:
        # Get valid labels from code_map
        valid_labels_query = f"SELECT DISTINCT label FROM code_map WHERE variable = '{var_name}'"
        valid_labels = [x[0] for x in db_con.execute(valid_labels_query).fetchall()]
        
        if not valid_labels:
            print(f"Warning: No codes found for {var_name} in code_map. Skipping.")
            continue
            
        # Get actual values from the data table
        actual_values_query = f"SELECT DISTINCT {col} FROM {table}"
        actual_values = [x[0] for x in db_con.execute(actual_values_query).fetchall()]
        
        invalid_values = []
        for val in actual_values:
            if val is None: continue 
            # Allow 'nan' string if it was produced by pandas/numpy
            if str(val).lower() == 'nan': continue
            
            if val not in valid_labels:
                invalid_values.append(val)
        
        assert len(invalid_values) == 0, f"Found invalid values in {table}.{col}: {invalid_values[:5]}..."

