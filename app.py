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
st.title("SOMA Public Safety Monitor v3")
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
            if not df_data.empty and 'point' in df_data.columns:
                if 'lat' in df_data.columns and 'long' in df_data.columns:
                    df_data['lat'] = pd.to_numeric(df_data['lat'])
                    df_data['lon'] = pd.to_numeric(df_data['long'])
                    df_data['min_dist'] = df_data.apply(lambda x: get_min_distance_to_any_site(x['lat'], x['lon']), axis=1)
                    df_data = df_data[df_data['min_dist'] <= radius_meters]
            return df_data
        else: return pd.DataFrame()
    except: return pd.DataFrame()

df = get_data(st.session_state.limit)

# --- MAP SECTION ---
with st.expander("🗺️ View Map & Incident Clusters", expanded=True):
    avg_lat = sum(s['lat'] for s in sites) / len(sites)
    avg_lon = sum(s['lon'] for s in sites) / len(sites)
    sites_df = pd.DataFrame(sites)
    
    layer_circles = pdk.Layer(
        "ScatterplotLayer", sites_df, get_position='[lon, lat]',
        get_color=[255, 0, 0, 50], get_radius=radius_meters,
        stroked=True, get_line_color=[255, 0, 0, 200], get_line_width=2
    )

    if not df.empty and 'lat' in df.columns:
        layer_points = pdk.Layer(
            "ScatterplotLayer", df, get_position='[lon, lat]',
            get_color=[0, 128, 255, 200], get_radius=3, pickable=True
        )
        layers = [layer_circles, layer_points]
    else: layers = [layer_circles]

    st.pydeck_chart(pdk.Deck(
        map_style=pdk.map_styles.CARTO_LIGHT,
        initial_view_state=pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=16.65),
        layers=layers, tooltip={"text": "{service_subtype}\n{requested_datetime}"}
    ))

st.markdown("---")

# 7. Helper: VERINT IMAGE CRACKER (With Handshake)
def fetch_verint_image(wrapper_url, case_id, debug_mode=False):
    logs = [] 
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mobile311.sfgov.org/",
        }

        # STEP 1: LOAD PAGE
        r_page = session.get(wrapper_url, headers=headers, timeout=5)
        if r_page.status_code != 200:
            if debug_mode: logs.append(f"❌ Step 1 Failed: {r_page.status_code}")
            return None, logs
        
        final_referer = r_page.url 
        html = r_page.text
        if debug_mode: logs.append("✅ Step 1 OK")

        # STEP 2: EXTRACT SECRETS
        formref_match = re.search(r'"formref"\s*:\s*"([^"]+)"', html)
        if not formref_match:
            if debug_mode: logs.append("❌ Step 2 Failed: No formref")
            return None, logs
        formref = formref_match.group(1)
        
        csrf_match = re.search(r'name="_csrf_token"\s+content="([^"]+)"', html)
        csrf_token = csrf_match.group(1) if csrf_match else None
        
        if debug_mode: logs.append(f"✅ Step 2 OK (CSRF: {bool(csrf_token)})")

        # STEP 2.5: CITIZEN HANDSHAKE (Gets Authorization Token)
        auth_token = None
        try:
            citizen_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
            headers["Referer"] = final_referer
            headers["Origin"] = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
            if csrf_token: headers["X-CSRF-TOKEN"] = csrf_token
            
            r_handshake = session.get(citizen_url, headers=headers, timeout=5)
            
            # Check for Auth Header in Response
            if 'Authorization' in r_handshake.headers:
                auth_token = r_handshake.headers['Authorization']
                if debug_mode: logs.append(f"✅ Step 2.5 Handshake OK. Token found: {auth_token[:10]}...")
            else:
                if debug_mode: logs.append(f"⚠️ Step 2.5 Warning: No Auth header in handshake (Status: {r_handshake.status_code})")
        except Exception as e:
            if debug_mode: logs.append(f"⚠️ Step 2.5 Failed: {str(e)}")

        # STEP 3: API CALL
        api_base = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/custom"
        headers["Content-Type"] = "application/json"
        
        # Inject the token if we found it
        if auth_token: headers["Authorization"] = auth_token
        
        details_payload = {
            "caseid": str(case_id),
            "data": {"formref": formref},
            "name": "download_attachments",
            "email": "", "xref": "", "xref1": "", "xref2": ""
        }

        r_list = session.post(
            f"{api_base}?action=get_attachments_details&actionedby=&loadform=true&access=citizen&locale=en",
            json=details_payload, headers=headers, timeout=5
        )
        
        if r_list.status_code != 200:
            if debug_mode: logs.append(f"❌ Step 3 Failed: {r_list.status_code}")
            return None, logs
        
        files_data = r_list.json()
        filename_str = ""
        if 'data' in files_data and 'formdata_filenames' in files_data['data']:
            filename_str = files_data['data']['formdata_filenames']
            
        if not filename_str:
            if debug_mode: logs.append("❌ Step 3 Failed: No filenames")
            return None, logs
            
        raw_files = filename_str.split(';')
        if debug_mode: logs.append(f"✅ Step 3 OK: {len(raw_files)} files")

        # STEP 4: FILTER
        target_filename = None
        for fname in raw_files:
            fname = fname.strip()
            if not fname: continue
            if not fname.lower().endswith('m.jpg') and fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                target_filename = fname
                break
        
        if not target_filename: 
             if debug_mode: logs.append("❌ Step 4 Failed: No valid image")
             return None, logs

        # STEP 5: DOWNLOAD
        download_payload = {
            "caseid": str(case_id),
            "data": {"formref": formref, "filename": target_filename},
            "name": "download_attachments",
            "email": "", "xref": "", "xref1": "", "xref2": ""
        }

        r_image = session.post(
            f"{api_base}?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en",
            json=download_payload, headers=headers, timeout=5
        )
        
        if r_image.status_code == 200:
            if debug_mode: logs.append(f"✅ Step 5 OK: {len(r_image.content)} bytes")
            return r_image.content, logs
        else:
             if debug_mode: logs.append(f"❌ Step 5 Failed: {r_image.status_code}")
             return None, logs
            
    except Exception as e:
        if debug_mode: logs.append(f"❌ Exception: {str(e)}")
        return None, logs
    return None, logs

def get_image_content(media_item, case_id, debug_flag=False):
    if not media_item: return None, False, []
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False, []
    clean_url = url.split('?')[0].lower()
    
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, "url", []
    
    if "caseid" in url.lower():
        image_bytes, debug_logs = fetch_verint_image(url, case_id, debug_flag)
        if image_bytes: return image_bytes, "bytes", debug_logs
        return url, "broken", debug_logs

    return url, "url", []

# 8. Feed
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        notes = str(row.get('status_notes', '')).lower()
        if 'duplicate' in notes: continue

        # DEBUG FIRST 3
        show_debug = (display_count < 3)
        
        case_id = row.get('service_request_id', '')
        media_content, media_type, logs = get_image_content(row.get('media_url'), case_id, debug_flag=show_debug)
        
        if media_content:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    
                    if show_debug and logs:
                        if media_type == "broken": st.error("\n".join(logs))
                        else: st.success("\n".join(logs))
                    
                    if media_type == "url" or media_type == "bytes":
                        st.image(media_content, width="stretch")
                    else:
                        st.image(media_content, width="stretch")

                    if 'requested_datetime' in row:
                        date_str = pd.to_datetime(row['requested_datetime']).strftime('%b %d, %I:%M %p')
                    else: date_str = "?"
                    
                    raw_subtype = row.get('service_subtype', 'Unknown Issue')
                    display_title = raw_subtype.replace('_', ' ').title()
                    address = row.get('address', 'Location N/A')
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    if case_id:
                        ticket_url = f"https://mobile311.sfgov.org/tickets/{case_id}"
                        date_display = f"[{date_str}]({ticket_url})"
                    else: date_display = date_str

                    site_name = get_closest_site_name(float(row['lat']), float(row['long']))
                    st.markdown(f"**{display_title}**")
                    st.markdown(f"{date_display} | [{address}]({map_url}) | **Near {site_name}**")
            
            display_count += 1
            
    if display_count == 0: st.info("No records found with media evidence.")
    
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current: {st.session_state.limit})"):
            st.session_state.limit += 500
            st.rerun()

else: st.info(f"No records found within 160ft of any monitored site in the last 5 months.")

st.markdown("---")
st.caption("Data source: [DataSF | Open Data Portal](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6/about_data)")
