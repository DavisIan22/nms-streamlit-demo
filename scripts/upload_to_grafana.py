import pandas as pd
import requests
import os
import time
import glob

# Credentials from GitHub Secrets
URL = os.getenv("GRAFANA_URL")
USER_ID = os.getenv("GRAFANA_USER")
TOKEN = os.getenv("GRAFANA_TOKEN")

def upload_csv():
    # Confirm path for debugging
    target_path = 'racestudio-compatible-data/*.csv'
    print(f"🔍 Searching for files in: {target_path}")
    
    csv_files = glob.glob(target_path)
    
    if not csv_files:
        print(f"Error: No CSV files found. Current directory: {os.getcwd()}")
        print(f"Contents: {os.listdir('.')}")
        return

    for file_path in csv_files:
        print(f"Processing: {file_path}")
        
        try:
            # Skip AiM metadata
            df = pd.read_csv(file_path, skiprows=14)
            df = df.drop(0) # Remove units row
            
            base_time = int(time.time())
            lines = []
            
            for _, row in df.iterrows():
                try:
                    ts_ns = int((base_time + float(row['Time'])) * 1e9)
                    line = (
                        f"fsae_telemetry,vehicle=BillieJean "
                        f"gps_speed={float(row['GPS Speed'])},"
                        f"rpm={float(row['RPM'])},"
                        f"voltage={float(row['External Voltage'])} "
                        f"{ts_ns}"
                    )
                    lines.append(line)
                except:
                    continue 

            if lines:
                payload = "\n".join(lines)
                response = requests.post(
                    URL,
                    data=payload,
                    headers={'Content-Type': 'text/plain'},
                    auth=(USER_ID, TOKEN)
                )
                print(f"Uploaded {file_path} - Status: {response.status_code}")
        except Exception as e:
            print(f"Failed {file_path}: {e}")

if __name__ == "__main__":
    upload_csv()
