import streamlit as st
import pandas as pd
import glob
import os
import pydeck as pdk
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="NMS Data Portal", layout="wide")
st.title("NMS Data Portal")

# --- 1. Smart Path Detection ---
if os.path.exists('racestudio-compatible-data'):
    log_folder = 'racestudio-compatible-data'
elif os.path.exists('../racestudio-compatible-data'):
    log_folder = '../racestudio-compatible-data'
else:
    st.error("Telemetry folder not found.")
    st.stop()

# --- 2. File Selection (Showing only Filenames) ---
csv_paths = glob.glob(f"{log_folder}/*.csv")
if not csv_paths:
    st.warning("No .csv logs found in folder.")
    st.stop()

# Create a mapping of { 'filename.csv': 'full/path/to/filename.csv' }
file_mapping = {os.path.basename(p): p for p in csv_paths} #

# Sidebar shows only the keys (the clean filenames)
selected_filename = st.sidebar.selectbox("Select Session Log", sorted(file_mapping.keys()))
selected_path = file_mapping[selected_filename] # The script uses the full path here

# --- 3. Unit Selection ---
unit_system = st.sidebar.radio("Unit System", ["Imperial (mph)", "Metric (km/h)"])

# --- 4. Data Loading & Cleaning ---
df = pd.read_csv(selected_path, skiprows=14, low_memory=False)
df = df.drop(0).apply(pd.to_numeric, errors='coerce')

# --- 5. Unit Conversions ---
if unit_system == "Imperial (mph)":
    df['DisplaySpeed'] = df['GPS Speed'] * 0.621371
    speed_label = "mph"
else:
    df['DisplaySpeed'] = df['GPS Speed']
    speed_label = "km/h"

# --- 6. Battery Power Calculations ---
# targets specific battery columns identified in your 3.csv file
volt_col = next((c for c in df.columns if 'Pack Voltage' in c or 'External Voltage' in c), None)
curr_col = next((c for c in df.columns if 'Pack Current' in c or 'Current' in c), None)

if volt_col and curr_col:
    df['Power_kW'] = (df[volt_col].abs() * df[curr_col]) / 1000.0
    df['dt'] = df['Time'].diff().fillna(0)
    df['Energy_Ws'] = (df[volt_col].abs() * df[curr_col]) * df['dt']
    total_energy_wh = df['Energy_Ws'].sum() / 3600.0
else:
    df['Power_kW'] = 0
    total_energy_wh = 0

# --- 7. Dashboard Header Metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Max Speed", f"{df['DisplaySpeed'].max():.1f} {speed_label}")
col2.metric("Max Power", f"{df['Power_kW'].max():.1f} kW")
col3.metric("Total Energy", f"{total_energy_wh:.2f} Wh")
col4.metric("Avg HV Voltage", f"{df[volt_col].mean() if volt_col else 0:.1f} V")

# --- 8. Powertrain Visualization ---
st.subheader("Powertrain Analysis")
if volt_col and curr_col:
    st.line_chart(df, x="Time", y=["Power_kW", curr_col])
else:
    st.info("HV Voltage and Current columns missing for power analysis.")

# --- 9. Interactive Channel Comparison ---
st.divider()
st.subheader("Telemetry Channels")
helper_cols = ['Time', 'dt', 'Energy_Ws', 'Power_kW', 'DisplaySpeed']
available_channels = [c for c in df.columns if c not in helper_cols]

defaults = []
if "DisplaySpeed" in df.columns: defaults.append("DisplaySpeed")
if "RPM" in available_channels: defaults.append("RPM")

selected_channels = st.multiselect("Select Channels to Graph", available_channels + ["DisplaySpeed"], default=defaults)
if selected_channels:
    st.line_chart(df, x="Time", y=selected_channels)

# --- 10. Satellite Track Map ---
st.subheader("Track Map")
if 'GPS Latitude' in df and 'GPS Longitude' in df:
    map_data = df[['GPS Latitude', 'GPS Longitude']].dropna()
    map_data.columns = ['lat', 'lon']

    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/satellite-v9',
        initial_view_state=pdk.ViewState(
            latitude=map_data['lat'].mean(),
            longitude=map_data['lon'].mean(),
            zoom=16,
            pitch=0,
        ),
        layers=[
            pdk.Layer(
                'ScatterplotLayer',
                data=map_data,
                get_position='[lon, lat]',
                get_color='[255, 75, 75, 160]',
                get_radius=1.5,
            ),
        ],
    ))

# --- 11. Raw Data Access ---
with st.expander("View Raw Session Data"):
    st.dataframe(df)
