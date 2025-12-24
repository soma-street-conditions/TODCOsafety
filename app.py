import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="Knox SRO Safety Monitor", page_icon="🚨", layout="wide")

# --- NO CRAWL & STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
        .report-text { font-size: 1.1rem; line-height: 1.5; color: #333; }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# 2. Session State for "Load More"
if 'limit' not in st.session_state:
    st.session_state.limit = 800

# 3. Date & API Setup
# Window: 5 months (approx 150 days)
five_months_ago = (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# TARGET COORDINATES (Knox SRO Center Point)
target_lat = 37.779421866793456
target_lon = -122.4064255044886
radius_meters = 48.8  # ~160 feet

# Header & Executive Briefing
st.header("Knox SRO: Public Safety Impact Report")

st.markdown(f"""
**Location:** 241 6th Street (The Knox SRO) | **Operator:** TODCO

This dashboard monitors the immediate vicinity of the Knox SRO, identifying it as a persistent focal point for street-level disorder. Data suggests that current management practices and security measures are insufficient, contributing to an environment of open-air drug activity, violence, and unsafe conditions for local residents.

The feed below aggregates real-time 311 service requests filed within **160 feet** of the building's entrance, providing a documented timeline of the public safety challenges at this specific location.
""")

st.markdown("Download the **Solve SF** app to submit reports: [iOS](https://apps.apple.com/us/app/solve-sf/id6737751237) | [Android](https://play.google.com/store/apps/details?id=com.woahfinally.solvesf)")
st.markdown("---")

# 4. Query
params = {
    "$where": f"within_circle(point, {target_lat}, {target_lon}, {radius_meters}) AND requested_datetime > '{five_months_ago}' AND media_url IS NOT NULL",
    "$order": "requested_datetime DESC",
    "$limit": st.session_state.limit
}

# 5. Fetch Data
@st.cache_data(ttl=300)
def get_data(query_limit):
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            df_data = pd.DataFrame(r.json())
            
            # Extract Lat/Lon for mapping if data exists
            if not df_data.empty and 'point' in df_data.columns:
                if 'lat' in df_data.columns and 'long' in df_data.columns:
                    df_data['lat'] = pd.to_numeric(df_data['lat'])
                    df_data['lon'] = pd.to_numeric(df_data['long'])
            return df_data
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

df = get_data(st.session_state.limit)

# --- MAP SECTION ---
with st.expander("🗺️ View Map & Incident Distribution", expanded=False):
    if not df.empty and 'lat' in df.columns:
        # Layer 1: The Target Radius (Red Circle)
        target_data = pd.DataFrame({'lat': [target_lat], 'lon': [target_lon]})
        
        layer_radius = pdk.Layer(
            "ScatterplotLayer",
            target_data,
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

        # Layer 2: The Reports (Blue Dots)
        layer_points = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color=[0, 128, 255, 200],
            get_radius=3,
            pickable=True,
        )

        # Map View State
        view_state = pdk.ViewState(
            latitude=target_lat,
            longitude=target_lon,
            zoom=18,
            pitch=0,
        )

        # Render Map with CARTO Style (No API Key needed)
        st.pydeck_chart(pdk.Deck(
            map_style=pdk.map_styles.CARTO_LIGHT,
            initial_view_state=view_state,
            layers=[layer_radius, layer_points],
            tooltip={"text": "{service_name}\n{requested_datetime}"}
        ))
    else:
        st.info("Map data unavailable or no records found.")

st.markdown("---")

# 6. Helper: Identify Image vs Portal Link
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    clean_url = url.split('?')[0].lower()
    
    # Case A: Standard Image (Public Cloud)
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, True # True = It's an image we can display inline
        
    # Case B: Portal Link (HTML wrapper)
    return url, False # False = It's a link, but not an inline image

# 7. Display Feed
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        notes = str(row.get('status_notes', '')).lower()
        if 'duplicate' in notes:
            continue

        full_url, is_image = get_image_info(row.get('media_url'))
        
        # SHOW IF: It is an image OR it is a valid portal link
        if full_url:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    
                    # LOGIC: If image, show it. If portal link, show placeholder button.
                    if is_image:
                        st.image(full_url, use_container_width=True)
                    else:
                        # Placeholder for non-image links
                        st.markdown(f"""
                        <div style="background-color:#f0f2f6; height:200px; display:flex; align-items:center; justify-content:center; border-radius:10px; margin-bottom:10px;">
                            <a href="{full_url}" target="_blank" style="text-decoration:none; color:#333; font-weight:bold; text-align:center;">
                                📷 View Evidence<br><span style="font-size:0.8rem; color:#666;">(External Portal)</span>
                            </a>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Metadata
                    if 'requested_datetime' in row:
                        date_str = pd.to_datetime(row['requested_datetime']).strftime('%b %d, %I:%M %p')
                    else:
                        date_str = "?"
                    
                    category = row.get('service_name', 'Unknown Issue')
                    address = row.get('address', 'Location N/A')
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    st.markdown(f"**{category}**")
                    st.markdown(f"{date_str} | [{address}]({map_url})")
            
            display_count += 1
            
    if display_count == 0:
        st.info("No records found with media evidence.")
    
    # Load More Button
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current: {st.session_state.limit})"):
            st.session_state.limit += 300
            st.rerun()

else:
    st.info(f"No records found within 160ft of target in the last 5 months.")

# Footer
st.markdown("---")
st.caption("Data source: [DataSF | Open Data Portal](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6/about_data)")
