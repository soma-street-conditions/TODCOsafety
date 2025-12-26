import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
import math
import re
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="TODCO Safety Monitor", page_icon="🚨", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.95rem; line-height: 1.5; margin-bottom: 10px; }
        .stMarkdown h2 { padding-top: 1rem; }
        div.stButton > button { width: 100%; border-radius: 5px; }
        .site-card { background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 2000

# 3. Configuration & Sites
five_months_ago = (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"
radius_meters = 48.8 

# SITE CONFIGURATION
sites = [
    {"name": "Knox SRO", "short_name": "Knox", "address": "241 6th Street", "lat": 37.77947681979851, "lon": -122.40646722115551},
    {"name": "Bayanihan House", "short_name": "Bayanihan", "address": "88 6th Street", "lat": 37.78092868326207, "lon": -122.40917338372577},
    {"name": "Hotel Isabel", "short_name": "Isabel", "address": "1095 Mission Street", "lat": 37.779230374811554, "lon": -122.4107826194545}
]

# 4. Header
st.title("SOMA Public Safety Monitor")
st.markdown("""
**Subject Properties Managed By:** TODCO Group
This independent dashboard monitors the immediate vicinity of three key properties in SOMA.
""")

c1, c2, c3 = st.columns(3)
for i, site in enumerate(sites):
    with [c1, c2, c3][i]:
        st.info(f"**{site['name']}**\n\n📍 {site['address']}")

st.markdown("---")

# 5. Query
location_clauses = [f"within_circle(point, {s['lat']}, {s['lon']}, {radius_meters})" for s in sites]
location_filter = f"({' OR '.join(location_clauses)})"
params = {
    "$where": f"{location_filter} AND requested_datetime > '{five_months_ago}' AND media_url IS NOT NULL AND service_name != 'Tree Maintenance' AND service_subtype != 'garbage_and_debris' AND service_subtype != 'not_offensive'",
    "$order": "requested_datetime DESC",
    "$limit": st.session_state.limit
}

# --- DISTANCE HELPER ---
def get_min_distance_to_any_site(row_lat, row_lon):
    min_dist = float('inf')
    R = 6371000
    for site in sites:
        lat1, lon1 = math.radians(site['lat']), math.radians(site['lon'])
        lat2, lon2 = math.radians(row_lat), math.radians(row_lon)
        dphi = lat2 - lat1
        dlambda = lon2 - lon1
        a = math.sin(dphi/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        dist = R*c
        if dist < min_dist: min_dist = dist
    return min_dist

def get_closest_site_name(row_lat, row_lon):
    min_dist = float('inf')
    closest_name = ""
    R = 6371000 
    for site in sites:
        lat1, lon1 = math.radians(site['lat']), math.radians(site['lon'])
        lat2, lon2 = math.radians(row_lat), math.radians(row_lon)
        dphi = lat2 - lat1
        dlambda = lon2 - lon1
        a = math.sin(dphi/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        dist = R*c
        if dist < min_dist:
            min_dist = dist
            closest_name = site['short_name']
    return closest_name

# 6. Fetch Data
@st.cache_data(ttl=300)
def get_data(query_limit):
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            df_data = pd.DataFrame(r.json())
            if not df_data.
