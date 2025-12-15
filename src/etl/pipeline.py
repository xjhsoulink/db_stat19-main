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
    """
    只保留 [START_YEAR, END_YEAR] 的数据。
    - 对 collision：用 add_derived_features 生成的 year 列
    - 对其它表：用 date 列的年份
    """
    # collision 在 add_derived_features 之后有 year 列
    if "year" in df.columns:
        mask = (df["year"] >= START_YEAR) & (df["year"] <= END_YEAR)
        return df.loc[mask].copy()

    # 其它表使用 date 列（cleaning.py 里已经把 date 转成 datetime）
    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        years = df["date"].dt.year
        mask = (years >= START_YEAR) & (years <= END_YEAR)
        return df.loc[mask].copy()

    # fallback：如果啥都没有，就原样返回（一般用不上）
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

    # Files to process: 换成 1979-latest-published-year 三个大文件
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

        # 1) 清洗 + 解码
        df_clean = clean_dataset(df, table_type, schema_df)

        # 2) 派生特征（year / month / hour / age_group 等）
        df_clean = add_derived_features(df_clean, table_type)

        # 3) 限定年份到 2000–2024
        df_clean = _filter_year_range(df_clean, table_type)
        print(
            f"After filtering to [{START_YEAR}, {END_YEAR}] "
            f"{table_type} rows = {len(df_clean)}"
        )

        # 4) 碰撞表做地理格式化（GeoDataFrame）
        if table_type == "collision":
            df_clean = format_sf(df_clean)

        # 5) 存一份清洗后的 CSV（方便 debug）
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
