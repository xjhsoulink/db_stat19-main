import pandas as pd

def merge_datasets(collision, vehicle, casualty):
    """
    Merges collision, vehicle, and casualty datasets.
    """
    print("Merging datasets...")
    
    print("Merging Casualty with Collision...")
    cas_col = pd.merge(casualty, collision, on='collision_index', how='left', suffixes=('_cas', '_col'))
    
    print("Merging Vehicle info...")
    master = pd.merge(cas_col, vehicle, on=['collision_index', 'vehicle_reference'], how='left', suffixes=('', '_veh'))
    
    return master

def add_derived_features(df, table_type):
    """
    Adds derived features required by the proposal (Time & Age).
    """
    # 1. Time Features (for Collision table)
    if table_type == 'collision' and 'datetime' in df.columns:
        print("Adding time features (year, month, hour, day_of_week)...")
        dt = df['datetime'].dt
        df['year'] = dt.year
        df['month'] = dt.month_name() # e.g., 'January'
        df['month_num'] = dt.month    # Useful for sorting
        df['hour'] = dt.hour
        df['day_of_week'] = dt.day_name() # e.g., 'Monday'
    
    # 2. Age Group (for Casualty table)
    if table_type == 'casualty' and 'age_of_casualty' in df.columns:
        print("Adding age_group feature...")
        bins = [-1, 15, 24, 64, 120]
        labels = ['Child', 'Young Adult', 'Adult', 'Senior']
        age_numeric = pd.to_numeric(df['age_of_casualty'], errors='coerce')
        df['age_group'] = pd.cut(age_numeric, bins=bins, labels=labels)
        df['age_group'] = df['age_group'].astype(str).replace('nan', 'Unknown')

    return df
