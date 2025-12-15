'''
import os
import pandas as pd
import geopandas as gpd
from .cleaning import clean_dataset
from .geo import format_sf
from .transformation import add_derived_features, merge_datasets
from .loader import save_to_duckdb

def run_pipeline():
    # Paths
    base_dir = os.getcwd() # Assuming running from root
    raw_dir = os.path.join(base_dir, "data/raw")
    cleaned_dir = os.path.join(base_dir, "data/cleaned")
    schema_path = os.path.join(base_dir, "ref/stats19/data-raw/stats19_schema.csv")
    
    if not os.path.exists(cleaned_dir):
        os.makedirs(cleaned_dir)
    
    # Load Schema
    print("Loading schema...")
    schema_df = pd.read_csv(schema_path)
    
    # Store cleaned dfs
    cleaned_dfs = {}
    cleaned_dfs['code_map'] = schema_df
    
    # Files to process
    files = [
        {
            "filename": "dft-road-casualty-statistics-casualty-last-5-years.csv",
            "type": "casualty"
        },
        {
            "filename": "dft-road-casualty-statistics-collision-last-5-years.csv",
            "type": "collision"
        },
        {
            "filename": "dft-road-casualty-statistics-vehicle-last-5-years.csv",
            "type": "vehicle"
        }
    ]
    
    for item in files:
        input_path = os.path.join(raw_dir, item["filename"])
        output_path = os.path.join(cleaned_dir, item["filename"])
        
        if not os.path.exists(input_path):
            print(f"File not found: {input_path}")
            continue
            
        print(f"Processing {item['filename']} as {item['type']}...")
        
        df = pd.read_csv(input_path, low_memory=False)
        df_clean = clean_dataset(df, item["type"], schema_df)
        df_clean = add_derived_features(df_clean, item["type"])
        
        if item["type"] == "collision":
            df_clean = format_sf(df_clean)
            
        print(f"Saving to {output_path}...")
        if isinstance(df_clean, gpd.GeoDataFrame):
            df_clean.to_csv(output_path, index=False)
        else:
            df_clean.to_csv(output_path, index=False)
            
        cleaned_dfs[item["type"]] = df_clean
        print("Done.")

    # Enforce Foreign Key Consistency
    if "collision" in cleaned_dfs:
        print("Enforcing foreign key consistency...")
        valid_indices = set(cleaned_dfs["collision"]["collision_index"])
        
        for table_type in ["vehicle", "casualty"]:
            if table_type in cleaned_dfs:
                df = cleaned_dfs[table_type]
                n_before = len(df)
                cleaned_dfs[table_type] = df[df["collision_index"].isin(valid_indices)]
                n_dropped = n_before - len(cleaned_dfs[table_type])
                if n_dropped > 0:
                    print(f"Dropped {n_dropped} orphaned records from {table_type}.")

    # Merge
    if all(k in cleaned_dfs for k in ["collision", "vehicle", "casualty"]):
        master_df = merge_datasets(
            cleaned_dfs["collision"],
            cleaned_dfs["vehicle"],
            cleaned_dfs["casualty"]
        )
        
        master_path = os.path.join(cleaned_dir, "master_dataset.csv")
        print(f"Saving master dataset to {master_path}...")
        master_df.to_csv(master_path, index=False)
        print("Master dataset saved.")
        
        cleaned_dfs['master'] = master_df

    # Save to DuckDB
    db_path = os.path.join(base_dir, "road_safety.duckdb")
    save_to_duckdb(cleaned_dfs, db_path)

if __name__ == "__main__":
    run_pipeline()
'''

# src/etl/pipeline.py
'''
import os
import pandas as pd
import geopandas as gpd

from .cleaning import clean_dataset
from .geo import format_sf
from .transformation import add_derived_features, merge_datasets
from .loader import save_to_duckdb


START_YEAR = 2000
END_YEAR = 2024


def _filter_year_range(df: pd.DataFrame, table_type: str) -> pd.DataFrame:


    if "year" in df.columns:
        mask = (df["year"] >= START_YEAR) & (df["year"] <= END_YEAR)
        return df.loc[mask].copy()

    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        years = df["date"].dt.year
        mask = (years >= START_YEAR) & (years <= END_YEAR)
        return df.loc[mask].copy()

    # fallback
    print(f"Warning: could not filter {table_type} by year, returning full dataframe.")
    return df


def run_pipeline():
    # Paths
    base_dir = os.getcwd()  # Assuming running from project root
    raw_dir = os.path.join(base_dir, "data", "raw")
    cleaned_dir = os.path.join(base_dir, "data", "cleaned")
    schema_path = os.path.join(base_dir, "ref", "stats19", "data-raw", "stats19_schema.csv")

    if not os.path.exists(cleaned_dir):
        os.makedirs(cleaned_dir)

    # Load Schema
    print("Loading schema...")
    schema_df = pd.read_csv(schema_path)

    # Store cleaned dfs
    cleaned_dfs: dict[str, pd.DataFrame] = {}
    cleaned_dfs["code_map"] = schema_df

    # Files to process:  1979-latest-published-year 
    files = [
        {
            "filename": "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv",
            "type": "casualty",
        },
        {
            "filename": "dft-road-casualty-statistics-collision-1979-latest-published-year.csv",
            "type": "collision",
        },
        {
            "filename": "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv",
            "type": "vehicle",
        },
    ]

    for item in files:
        input_path = os.path.join(raw_dir, item["filename"])
        output_path = os.path.join(cleaned_dir, item["filename"])
        table_type = item["type"]

        if not os.path.exists(input_path):
            print(f"[WARN] File not found: {input_path}")
            continue

        print(f"\n=== Processing {item['filename']} as {table_type} ===")
        df = pd.read_csv(input_path, low_memory=False)

        df_clean = clean_dataset(df, table_type, schema_df)

        df_clean = add_derived_features(df_clean, table_type)

        df_clean = _filter_year_range(df_clean, table_type)
        print(
            f"After filtering to [{START_YEAR}, {END_YEAR}] "
            f"{table_type} rows = {len(df_clean)}"
        )

        if table_type == "collision":
            df_clean = format_sf(df_clean)

        print(f"Saving cleaned {table_type} to {output_path}...")
        if isinstance(df_clean, gpd.GeoDataFrame):
            df_clean.to_csv(output_path, index=False)
        else:
            df_clean.to_csv(output_path, index=False)

        cleaned_dfs[table_type] = df_clean

    print("\n=== Finished cleaning all base tables ===")

    # Enforce Foreign Key Consistency
    if "collision" in cleaned_dfs:
        print("Enforcing foreign key consistency...")
        valid_indices = set(cleaned_dfs["collision"]["collision_index"])
        for table_type in ["vehicle", "casualty"]:
            if table_type in cleaned_dfs:
                df = cleaned_dfs[table_type]
                n_before = len(df)
                df = df[df["collision_index"].isin(valid_indices)]
                n_dropped = n_before - len(df)
                cleaned_dfs[table_type] = df
                if n_dropped > 0:
                    print(f"Dropped {n_dropped} orphaned records from {table_type}.")

    # Merge master
    if all(k in cleaned_dfs for k in ["collision", "vehicle", "casualty"]):
        master_df = merge_datasets(
            cleaned_dfs["collision"], cleaned_dfs["vehicle"], cleaned_dfs["casualty"]
        )
        master_path = os.path.join(cleaned_dir, "master_dataset.csv")
        print(f"Saving master dataset to {master_path}...")
        master_df.to_csv(master_path, index=False)
        print("Master dataset saved.")
        cleaned_dfs["master"] = master_df

    # Save to DuckDB
    db_path = os.path.join(base_dir, "road_safety.duckdb")
    save_to_duckdb(cleaned_dfs, db_path)


if __name__ == "__main__":
    run_pipeline()
'''

# src/etl/pipeline.py
import pandas as pd
import geopandas as gpd
from pathlib import Path

from .cleaning import clean_dataset
from .geo import format_sf
from .transformation import add_derived_features, merge_datasets
from .loader import save_to_duckdb


START_YEAR = 2000
END_YEAR = 2024


def _project_root() -> Path:
    """
    Resolve project root robustly, independent of current working directory.
    This file: <root>/src/etl/pipeline.py -> parents[2] == <root>
    """
    return Path(__file__).resolve().parents[2]


def _filter_year_range(df: pd.DataFrame, table_type: str) -> pd.DataFrame:
    if "year" in df.columns:
        mask = (df["year"] >= START_YEAR) & (df["year"] <= END_YEAR)
        return df.loc[mask].copy()

    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        years = df["date"].dt.year
        mask = (years >= START_YEAR) & (years <= END_YEAR)
        return df.loc[mask].copy()

    print(f"[WARN] could not filter {table_type} by year/date, returning full dataframe.")
    return df


def _load_schema(base_dir: Path) -> pd.DataFrame:
    """
    1) Prefer CSV at ref/stats19/data-raw/stats19_schema.csv
    2) If missing, fallback to bundled RDA at ref/stats19/data/stats19_schema.rda
       (export CSV for future runs).
    """
    csv_path = base_dir / "ref" / "stats19" / "data-raw" / "stats19_schema.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)

    rda_path = base_dir / "ref" / "stats19" / "data" / "stats19_schema.rda"
    if rda_path.exists():
        try:
            import pyreadr  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Schema CSV is missing and fallback requires `pyreadr`.\n"
                "Install it with: pip install pyreadr"
            ) from e

        res = pyreadr.read_r(str(rda_path))

        if "stats19_schema" in res:
            df = res["stats19_schema"]
        else:
            # If object name differs, take the first object
            df = next(iter(res.values()))

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        print(f"[INFO] Exported schema CSV to: {csv_path}")
        return df

    raise FileNotFoundError(
        "Schema not found.\n"
        f"Expected CSV: {csv_path}\n"
        f"Or bundled RDA: {rda_path}\n"
        "Fix by generating the CSV (or adding the RDA) under ref/stats19/."
    )


def run_pipeline() -> None:
    base_dir = _project_root()
    raw_dir = base_dir / "data" / "raw"
    cleaned_dir = base_dir / "data" / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    print("Loading schema...")
    schema_df = _load_schema(base_dir)

    cleaned_dfs: dict[str, pd.DataFrame] = {"code_map": schema_df}

    files = [
        {
            "filename": "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv",
            "type": "casualty",
        },
        {
            "filename": "dft-road-casualty-statistics-collision-1979-latest-published-year.csv",
            "type": "collision",
        },
        {
            "filename": "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv",
            "type": "vehicle",
        },
    ]

    for item in files:
        filename = item["filename"]
        table_type = item["type"]

        input_path = raw_dir / filename
        output_path = cleaned_dir / filename

        if not input_path.exists():
            print(f"[WARN] File not found: {input_path}")
            continue

        print(f"\n=== Processing {filename} as {table_type} ===")
        df = pd.read_csv(input_path, low_memory=False)

        df_clean = clean_dataset(df, table_type, schema_df)
        df_clean = add_derived_features(df_clean, table_type)

        df_clean = _filter_year_range(df_clean, table_type)
        print(f"After filtering to [{START_YEAR}, {END_YEAR}] {table_type} rows = {len(df_clean)}")

        if table_type == "collision":
            df_clean = format_sf(df_clean)

        print(f"Saving cleaned {table_type} to {output_path}...")
        df_clean.to_csv(output_path, index=False)

        cleaned_dfs[table_type] = df_clean

    print("\n=== Finished cleaning all base tables ===")

    # Enforce Foreign Key Consistency
    if "collision" in cleaned_dfs and "collision_index" in cleaned_dfs["collision"].columns:
        print("Enforcing foreign key consistency...")
        valid_indices = set(cleaned_dfs["collision"]["collision_index"].dropna().unique())

        for table_type in ["vehicle", "casualty"]:
            if table_type in cleaned_dfs and "collision_index" in cleaned_dfs[table_type].columns:
                df2 = cleaned_dfs[table_type]
                n_before = len(df2)
                df2 = df2[df2["collision_index"].isin(valid_indices)]
                n_dropped = n_before - len(df2)
                cleaned_dfs[table_type] = df2
                if n_dropped > 0:
                    print(f"Dropped {n_dropped} orphaned records from {table_type}.")
    else:
        print("[WARN] Cannot enforce FK consistency (collision table missing or no collision_index).")

    # Merge master
    if all(k in cleaned_dfs for k in ["collision", "vehicle", "casualty"]):
        master_df = merge_datasets(cleaned_dfs["collision"], cleaned_dfs["vehicle"], cleaned_dfs["casualty"])
        master_path = cleaned_dir / "master_dataset.csv"
        print(f"Saving master dataset to {master_path}...")
        master_df.to_csv(master_path, index=False)
        print("Master dataset saved.")
        cleaned_dfs["master"] = master_df
    else:
        print("[WARN] Skipping master merge (missing one of collision/vehicle/casualty).")

    # Save to DuckDB
    db_path = base_dir / "road_safety.duckdb"
    save_to_duckdb(cleaned_dfs, str(db_path))
    print(f"[OK] DuckDB saved to {db_path}")


if __name__ == "__main__":
    run_pipeline()
