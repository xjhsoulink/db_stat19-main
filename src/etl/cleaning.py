import pandas as pd
import re

def format_column_names(column_names):
    """
    Replicates the format_column_names function from stats19 R package.
    """
    x = [col.lower() for col in column_names]
    x = [col.replace(" ", "_") for col in x]
    x = [re.sub(r"\(|\)", "", col) for col in x]
    x = [col.replace("1st", "first") for col in x]
    x = [col.replace("2nd", "second") for col in x]
    x = [col.replace("-", "_") for col in x]
    x = [col.replace("?", "") for col in x]
    return x

def clean_dataset(df, table_type, schema_df):
    """
    Cleans the dataset using the schema.
    """
    # Rename columns
    df.columns = format_column_names(df.columns)
    
    # Filter schema for this table type
    table_schema = schema_df[schema_df['table'] == table_type]
    
    if table_schema.empty:
        print(f"Warning: No schema found for table type '{table_type}'")
        return df

    # Iterate over columns
    for col in df.columns:
        # Find variable in schema
        var_schema = table_schema[table_schema['variable'] == col]
        
        if var_schema.empty:
            continue
            
        # Check if we have codes to replace
        valid_codes = var_schema.dropna(subset=['code'])
        
        if valid_codes.empty:
            continue
            
        mapping = {}
        for _, row in valid_codes.iterrows():
            code = row['code']
            label = row['label']
            mapping[code] = label
            
        try:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_mapping = {}
                for k, v in mapping.items():
                    try:
                        k_num = float(k)
                        if pd.api.types.is_integer_dtype(df[col]):
                            k_final = int(k_num)
                        else:
                            k_final = k_num
                        numeric_mapping[k_final] = v
                    except ValueError:
                        numeric_mapping[k] = v
                
                df[col] = df[col].replace(numeric_mapping)
                
            else:
                str_mapping = {str(k): v for k, v in mapping.items()}
                df[col] = df[col].replace(str_mapping)
                
        except Exception as e:
            print(f"Error processing column {col}: {e}")

    # Handle Date
    if 'date' in df.columns:
        try:
            df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y', errors='coerce')
            
            if 'time' in df.columns:
                date_str = df['date'].dt.strftime('%Y-%m-%d')
                time_str = df['time'].fillna('')
                combined = date_str + ' ' + time_str
                df['datetime'] = pd.to_datetime(combined, format='%Y-%m-%d %H:%M', errors='coerce')
                
        except Exception as e:
            print(f"Error parsing date/time: {e}")

    return df
