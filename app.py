import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="The Knox SRO Watch", page_icon="📍", layout="wide")

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
ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# TARGET COORDINATES (6th & Tehama / Knox SRO)
target_lat = 37.77935708464253
target_lon = -122.4064893420712
radius_meters = 48.8  # ~160 feet

# Header & Advocacy Text
st.header("The Knox SRO: Neighborhood Impact")

st.markdown(f"""
The Knox SRO at 241 6th Street, operated by TODCO, through permissive management and a lack of security have invited open air drug markets, violence, open drug use, and disorderly neighbors to a residential neighborhood.

This website displays 311 tickets filed within **160 feet** of the Knox SRO, to demonstrate the general chaos, open-air drug use and dealing, unsafe and inhumane conditions that continue to persist within **160 feet** of its entrance. Cases are updated daily when 311 data refreshes.
""")

st.markdown("Download the **Solve SF** app to submit reports: [iOS](https://apps.apple.com/us/app/solve-sf/id6737751237) | [Android](https://play.google.com/store/apps/details?id=com.woahfinally.solvesf)")
st.markdown("---")

# 4. Query
params = {
    "$where": f"within_circle(point, {target_lat}, {target_lon}, {radius_meters}) AND requested_datetime > '{ninety_days_ago}' AND media_url IS NOT NULL",
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

# --- MAP SECTION (FIXED INDENTATION) ---
with st.expander("🗺️ View Map & Radius", expanded=False):
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
    
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, True
    return url, False

# 7. Display Feed
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        notes = str(row.get('status_notes', '')).lower()
        if 'duplicate' in notes:
            continue

        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        if full_url and is_viewable:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    st.image(full_url, use_container_width=True)
                    
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
        st.info("No viewable images found in this radius.")
    
    # Load More Button
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current: {st.session_state.limit})"):
            st.session_state.limit += 300
            st.rerun()

else:
    st.info(f"No records found within 160ft of the Knox SRO in the last 90 days.")

# Footer
st.markdown("---")
st.caption("Data source: [DataSF | Open Data Portal](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6/about_data)")
