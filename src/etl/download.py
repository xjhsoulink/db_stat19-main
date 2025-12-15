'''
import os
import requests

def download_data():
    """
    Downloads the last 5 years of STATS19 data (Collision, Vehicle, Casualty)
    from the official DfT website to data/raw.
    """
    base_url = "https://data.dft.gov.uk/road-accidents-safety-data/"
    files = [
        "dft-road-casualty-statistics-collision-last-5-years.csv",
        "dft-road-casualty-statistics-vehicle-last-5-years.csv",
        "dft-road-casualty-statistics-casualty-last-5-years.csv"
    ]
    
    # Determine project root (assuming this script is in src/etl/)
    # We want to go up two levels from src/etl to project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    output_dir = os.path.join(project_root, "data", "raw")
    
    if not os.path.exists(output_dir):
        print(f"Creating directory: {output_dir}")
        os.makedirs(output_dir)
        
    for filename in files:
        url = base_url + filename
        output_path = os.path.join(output_dir, filename)
        
        if os.path.exists(output_path):
            print(f"File already exists: {filename}. Skipping...")
            continue

        print(f"Downloading {filename} from {url}...")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully saved to {output_path}")
            
        except Exception as e:
            print(f"Failed to download {filename}: {e}")

if __name__ == "__main__":
    download_data()
'''

# src/etl/download.py

import os
import requests

BASE_URL = "https://data.dft.gov.uk/road-accidents-safety-data"

FILES = [
    "dft-road-casualty-statistics-collision-1979-latest-published-year.csv",
    "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv",
    "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv",
]

def download_file(file_name: str, dest_dir: str):
    url = f"{BASE_URL}/{file_name}"
    dest_path = os.path.join(dest_dir, file_name)

    if os.path.exists(dest_path):
        print(f"[skip] {dest_path} already exists")
        return

    print(f"[download] {url}")
    resp = requests.get(url, stream=True)
    resp.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    print(f"[ok] saved to {dest_path}")

def main():
    base_dir = os.getcwd()
    raw_dir = os.path.join(base_dir, "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    for fname in FILES:
        download_file(fname, raw_dir)

if __name__ == "__main__":
    main()
