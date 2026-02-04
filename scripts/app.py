import streamlit as st
import pandas as pd
import glob
import os
import pydeck as pdk
import numpy as np

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

# --- 2. File Selection (Clean Names Only) ---
csv_paths = glob.glob(f"{log_folder}/*.csv")
if not csv_paths:
    st.warning("No .csv logs found.")
    st.stop()

file_mapping = {os.path.basename(p): p for p in csv_paths}
selected_filename = st.sidebar.selectbox("Select Session Log", sorted(file_mapping.keys()))
selected_path = file_mapping[selected_filename]

# --- 3. Sidebar Configuration ---
unit_system = st.sidebar.radio("Unit System", ["Imperial (mph)", "Metric (km/h)"])

# --- 4. Data Loading ---
df = pd.read_csv(selected_path, skiprows=14, low_memory=False)
df = df.drop(0).apply(pd.to_numeric, errors='coerce')

# --- 5. Unit Conversions ---
if unit_system == "Imperial (mph)":
    df['DisplaySpeed'] = df['GPS Speed'] * 0.621371
    speed_label = "mph"
else:
    df['DisplaySpeed'] = df['GPS Speed']
    speed_label = "km/h"

# --- 6. Advanced Powertrain & Regen Calculations ---
# Prioritize 'Pack' sensors for High Voltage data
hv_volt_col = next((c for c in df.columns if 'Pack Voltage' in c), None)
hv_curr_col = next((c for c in df.columns if 'Pack Current' in c), None)

if hv_volt_col and hv_curr_col:
    # Use .abs() because Pack Voltage in 3.csv is recorded as negative potential
    df['Power_kW'] = (df[hv_volt_col].abs() * df[hv_curr_col]) / 1000.0
    df['dt'] = df['Time'].diff().fillna(0)
    
    # Discharge vs Regen Logic
    # Positive Power = Consuming energy | Negative Power = Recovering energy
    discharge_mask = df['Power_kW'] > 0
    regen_mask = df['Power_kW'] < 0
    
    # Energy in Watt-hours (Wh)
    # (kW * 1000) * seconds / 3600
    spent_wh = (df.loc[discharge_mask, 'Power_kW'] * df.loc[discharge_mask, 'dt']).sum() * (1000/3600)
    recovered_wh = (df.loc[regen_mask, 'Power_kW'].abs() * df.loc[regen_mask, 'dt']).sum() * (1000/3600)
    
    regen_efficiency = (recovered_wh / spent_wh * 100) if spent_wh > 0 else 0
    net_energy_wh = spent_wh - recovered_wh
else:
    st.sidebar.error("HV Pack sensors not found.")
    spent_wh = recovered_wh = regen_efficiency = net_energy_wh = 0

# --- 7. Dashboard Metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Max Power", f"{df['Power_kW'].max():.1f} kW")
col2.metric("Net Energy", f"{net_energy_wh:.1f} Wh")
col3.metric("Regen Recovery", f"{regen_efficiency:.1f} %")
# Metric shows absolute HV voltage (300V+)
col4.metric("Avg HV Voltage", f"{df[hv_volt_col].abs().mean():.1f} V" if hv_volt_col else "N/A")

# --- 8. Visual Analysis ---
st.subheader("Powertrain Analysis")
if hv_volt_col and hv_curr_col:
    st.line_chart(df, x="Time", y=["Power_kW", hv_curr_col])
    st.caption("Power (kW) and Battery Current (A) over session time.")

# --- 9. Channel Comparison ---
st.divider()
st.subheader("Telemetry Channels")
ignore_cols = ['Time', 'dt', 'Power_kW', 'DisplaySpeed']
available_channels = [c for c in df.columns if c not in ignore_cols]
selected_channels = st.multiselect("Select Channels", available_channels + ["DisplaySpeed"], default=["DisplaySpeed"])
if selected_channels:
    st.line_chart(df, x="Time", y=selected_channels)

# --- 10. Satellite Track Map ---
st.subheader("Track Map")
if 'GPS Latitude' in df and 'GPS Longitude' in df:
    map_data = df[['GPS Latitude', 'GPS Longitude']].dropna()
    map_data.columns = ['lat', 'lon']
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/satellite-v9',
        initial_view_state=pdk.ViewState(latitude=map_data['lat'].mean(), longitude=map_data['lon'].mean(), zoom=16),
        layers=[pdk.Layer('ScatterplotLayer', data=map_data, get_position='[lon, lat]', get_color='[255, 75, 75, 160]', get_radius=1.5)],
    ))

with st.expander("View Raw Data"):
    st.dataframe(df)
