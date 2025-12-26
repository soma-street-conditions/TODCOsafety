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
radius_meters = 48.8  # ~160 feet

# SITE CONFIGURATION
sites = [
    {
        "name": "Knox SRO",
        "short_name": "Knox",
        "address": "241 6th Street",
        "lat": 37.77947681979851,
        "lon": -122.40646722115551
    },
    {
        "name": "Bayanihan House",
        "short_name": "Bayanihan",
        "address": "88 6th Street",
        "lat": 37.78092868326207,
        "lon": -122.40917338372577
    },
    {
        "name": "Hotel Isabel",
        "short_name": "Isabel",
        "address": "1095 Mission Street",
        "lat": 37.779230374811554,
        "lon": -122.4107826194545
    }
]

# 4. Header & Executive Text
st.title("SOMA Public Safety Monitor")

st.markdown("""
**Subject Properties Managed By:** TODCO Group

This independent dashboard monitors the immediate vicinity of three key properties in SOMA. It aggregates real-time 311 service requests filed within **160 feet** of each building's entrance to identify persistent patterns of disorder, including open-air drug activity, violence, and unsafe street conditions.

**Monitored Locations:**
""")

c1, c2, c3 = st.columns(3)
for i, site in enumerate(sites):
    with [c1, c2, c3][i]:
        st.info(f"**{site['name']}**\n\n📍 {site['address']}")

st.markdown("---")
st.markdown("Download the **Solve SF** app to submit reports: [iOS](https://apps.apple.com/us/app/solve-sf/id6737751237) | [Android](https://play.google.com/store/apps/details?id=com.woahfinally.solvesf)")
st.markdown("---")

# 5. Dynamic Query Construction
location_clauses = [
    f"within_circle(point, {s['lat']}, {s['lon']}, {radius_meters})" 
    for s in sites
]
location_filter = f"({' OR '.join(location_clauses)})"

params = {
    "$where": f"{location_filter} AND requested_datetime > '{five_months_ago}' AND media_url IS NOT NULL AND service_name != 'Tree Maintenance' AND service_subtype != 'garbage_and_debris' AND service_subtype != 'not_offensive'",
    "$order": "requested_datetime DESC",
    "$limit": st.session_state.limit
}

# --- DISTANCE CALCULATION HELPER ---
def get_min_distance_to_any_site(row_lat, row_lon):
    """Returns the distance (in meters) to the closest of the 3 sites."""
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
        
        if dist < min_dist:
            min_dist = dist
            
    return min_dist

def get_closest_site_name(row_lat, row_lon):
    """Returns the short name of the closest site."""
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
            
            if not df_data.empty and 'point' in df_data.columns:
                if 'lat' in df_data.columns and 'long' in df_data.columns:
                    df_data['lat'] = pd.to_numeric(df_data['lat'])
                    df_data['lon'] = pd.to_numeric(df_data['long'])
                    
                    # Strict Python Filter
                    df_data['min_dist'] = df_data.apply(
                        lambda x: get_min_distance_to_any_site(x['lat'], x['lon']), axis=1
                    )
                    df_data = df_data[df_data['min_dist'] <= radius_meters]
                    
            return df_data
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

df = get_data(st.session_state.limit)

# --- MAP SECTION ---
with st.expander("🗺️ View Map & Incident Clusters", expanded=True):
    avg_lat = sum(s['lat'] for s in sites) / len(sites)
    avg_lon = sum(s['lon'] for s in sites) / len(sites)

    sites_df = pd.DataFrame(sites)
    
    layer_circles = pdk.Layer(
        "ScatterplotLayer",
        sites_df,
        get_position='[lon, lat]',
        get_color=[255, 0, 0, 50],
        get_radius=radius_meters,
        stroked=True,
        get_line_color=[255, 0, 0, 200],
        get_line_width=2,
        radius_scale=1,
        radius_min_pixels=1,
        radius_max_pixels=1000,
    )

    if not df.empty and 'lat' in df.columns:
        layer_points = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color=[0, 128, 255, 200],
            get_radius=3, 
            pickable=True,
        )
        layers = [layer_circles, layer_points]
    else:
        layers = [layer_circles]

    view_state = pdk.ViewState(
        latitude=avg_lat,
        longitude=avg_lon,
        zoom=17.1, 
        pitch=0,
    )

    st.pydeck_chart(pdk.Deck(
        map_style=pdk.map_styles.CARTO_LIGHT,
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "{service_subtype}\n{requested_datetime}"}
    ))

st.markdown("---")

# 7. Helper: VERINT IMAGE CRACKER
# This caches the image bytes so we don't re-download on every interaction
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_verint_image(wrapper_url, case_id):
    """
    1. Visits the wrapper page.
    2. Regex searches for the hidden 'formref' and 'filename'.
    3. POSTs to the API to get the raw image.
    """
    try:
        # Step 1: Get the wrapper page HTML
        session = requests.Session()
        r_page = session.get(wrapper_url, timeout=5)
        if r_page.status_code != 200:
            return None
            
        html = r_page.text
        
        # Step 2: Hunt for the variables using Regex
        # We look for: formref: "XYZ" and filename: "ABC.jpg"
        formref_match = re.search(r'formref:\s*"([^"]+)"', html)
        filename_match = re.search(r'filename:\s*"([^"]+)"', html)
        
        if not formref_match or not filename_match:
            return None
            
        formref = formref_match.group(1)
        filename = filename_match.group(1)
        
        # Step 3: Construct the API Payload
        api_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/custom?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en"
        
        payload = {
            "caseid": str(case_id),
            "data": {
                "formref": formref,
                "filename": filename
            },
            "email": "",
            "name": "download_attachments",
            "xref": "",
            "xref1": "",
            "xref2": ""
        }
        
        # Step 4: Fire the POST request
        r_image = session.post(api_url, json=payload, timeout=5)
        
        if r_image.status_code == 200:
            return r_image.content # Return raw bytes
            
    except Exception as e:
        return None
        
    return None

def get_image_content(media_item, case_id):
    """Returns either a URL (string) or Raw Bytes (for Verint)."""
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    
    clean_url = url.split('?')[0].lower()
    
    # Case A: Standard Image (Public Cloud) -> Return URL
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, "url"
    
    # Case B: Verint Wrapper -> Try to fetch bytes
    # We only try this if it looks like a Verint wrapper (usually has caseid param)
    if "caseid" in url.lower():
        image_bytes = fetch_verint_image(url, case_id)
        if image_bytes:
            return image_bytes, "bytes"

    # Case C: Fallback -> Return URL (will be a clickable link)
    return url, "link"

# 8. Display Feed
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        notes = str(row.get('status_notes', '')).lower()
        if 'duplicate' in notes:
            continue

        # Get Image Data
        case_id = row.get('service_request_id', '')
        media_content, media_type = get_image_content(row.get('media_url'), case_id)
        
        if media_content:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    
                    # RENDER IMAGE OR BUTTON
                    if media_type == "url":
                        st.image(media_content, use_container_width=True)
                    elif media_type == "bytes":
                        st.image(media_content, use_container_width=True)
                    else:
                        # Fallback Button
                        st.markdown(f"""
                        <div style="background-color:#f0f2f6; height:200px; display:flex; align-items:center; justify-content:center; border-radius:10px; margin-bottom:10px;">
                            <a href="{media_content}" target="_blank" style="text-decoration:none; color:#333; font-weight:bold; text-align:center;">
                                📷 View Evidence<br><span style="font-size:0.8rem; color:#666;">(External Portal)</span>
                            </a>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Metadata
                    if 'requested_datetime' in row:
                        date_str = pd.to_datetime(row['requested_datetime']).strftime('%b %d, %I:%M %p')
                    else:
                        date_str = "?"
                    
                    raw_subtype = row.get('service_subtype', 'Unknown Issue')
                    display_title = raw_subtype.replace('_', ' ').title()
                    
                    address = row.get('address', 'Location N/A')
                    map_url = f"http://googleusercontent.com/maps.
