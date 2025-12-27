import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
import math
import re
import base64
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# 1. Page Config
st.set_page_config(page_title="TODCO Safety Monitor", page_icon="🚨", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.95rem; line-height: 1.5; margin-bottom: 10px; }
        .stMarkdown h1 { padding-bottom: 0rem; }
        .stMarkdown h3 { font-weight: 400; font-size: 1.2rem; color: #444; padding-bottom: 1rem; }
        div.stButton > button { width: 100%; border-radius: 5px; }
        .site-card { background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        img { border-radius: 5px; }
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

# 4. Header & Executive Text
st.title("SOMA Neighborhood Safety Monitor: TODCO Portfolio Watch")
st.markdown("### Daily feed of public safety and sanitation incidents surrounding TODCO-managed properties.")

st.markdown("""
This automated dashboard aggregates daily 311 service request data from the City of San Francisco to track environmental conditions at three key subsidized housing sites managed by the **Tenants and Owners Development Corporation (TODCO)**.

The data visualizes the density of safety hazards, including biohazards, encampments, and blocked sidewalks, clustered immediately around these facilities. This tool serves as a transparency mechanism for neighbors, city officials, and regulators to monitor adherence to *"Good Neighbor Policies"* and HUD *"Decent, Safe, and Sanitary"* standards.
""")

c1, c2, c3 = st.columns(3)
for i, site in enumerate(sites):
    with [c1, c2, c3][i]:
        st.info(f"**{site['name']}**\n\n📍 {site['address']}")

st.markdown("---")

# 5. Query Construction
location_clauses = [f"within_circle(point, {s['lat']}, {s['lon']}, {radius_meters})" for s in sites]
location_filter = f"({' OR '.join(location_clauses)})"

# EXCLUSION LIST
exclusions = [
    "service_name != 'Tree Maintenance'",
    "service_subtype != 'garbage_and_debris'",
    "service_subtype != 'not_offensive'",
    "service_subtype != 'Toters_left_out_24x7'",
    "service_subtype != 'Other_including_abandoned_toter'",
    "service_subtype != 'Other_Illegal_Parking'",
    "service_subtype != 'Add_remove_garbage_can'",
    "service_subtype != 'City_garbage_can_overflowing'",
    "service_subtype != 'Pavement_Defect'",
    "service_subtype != 'Sidewalk_Defect'",
    "service_subtype != 'other_garbage_can_repair'"
]
exclusion_string = " AND ".join(exclusions)

params = {
    "$where": f"{location_filter} AND requested_datetime > '{five_months_ago}' AND media_url IS NOT NULL AND {exclusion_string}",
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

# 7. Helper: VERINT IMAGE CRACKER (PRODUCTION)
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_verint_image(wrapper_url):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mobile311.sfgov.org/",
        }

        # A. Sync Case ID from URL
        parsed = urlparse(wrapper_url)
        qs = parse_qs(parsed.query)
        url_case_id = qs.get('caseid', [None])[0]
        if not url_case_id: return None

        # STEP 1: Visit Page
        r_page = session.get(wrapper_url, headers=headers, timeout=5)
        if r_page.status_code != 200: return None
        
        final_referer = r_page.url 
        html = r_page.text

        # STEP 2: Extract Secrets
        formref_match = re.search(r'"formref"\s*:\s*"([^"]+)"', html)
        if not formref_match: return None
        formref = formref_match.group(1)
        
        csrf_match = re.search(r'name="_csrf_token"\s+content="([^"]+)"', html)
        csrf_token = csrf_match.group(1) if csrf_match else None

        # STEP 3: Handshake
        try:
            citizen_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
            headers["Referer"] = final_referer
            headers["Origin"] = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
            if csrf_token: headers["X-CSRF-TOKEN"] = csrf_token
            
            r_handshake = session.get(citizen_url, headers=headers, timeout=5)
            if 'Authorization' in r_handshake.headers:
                headers["Authorization"] = r_handshake.headers['Authorization']
        except: pass

        # STEP 4: Get Files (Using "Nested" Payload)
        api_base = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/custom"
        headers["Content-Type"] = "application/json"
        
        nested_payload = {
            "data": {"caseid": str(url_case_id), "formref": formref},
            "name": "download_attachments",
            "email": "", "xref": "", "xref1": "", "xref2": ""
        }
        
        r_list = session.post(
            f"{api_base}?action=get_attachments_details&actionedby=&loadform=true&access=citizen&locale=en",
            json=nested_payload, headers=headers, timeout=5
        )
        
        if r_list.status_code != 200: return None
        
        files_data = r_list.json()
        filename_str = ""
        if 'data' in files_data and 'formdata_filenames' in files_data['data']:
            filename_str = files_data['data']['formdata_filenames']
            
        if not filename_str: return None
        raw_files = filename_str.split(';')

        # STEP 5: Filter Image (UPDATED FOR _MAP.JPG)
        target_filename = None
        for fname in raw_files:
            fname = fname.strip()
            if not fname: continue
            
            # Skip ANY file that looks like a map
            f_lower = fname.lower()
            if f_lower.endswith('m.jpg') or f_lower.endswith('_map.jpg') or f_lower.endswith('_map.jpeg'):
                continue
                
            # Accept valid images
            if f_lower.endswith(('.jpg', '.jpeg', '.png')):
                target_filename = fname
                break
        
        if not target_filename: return None

        # STEP 6: Download & Unwrap JSON
        download_payload = nested_payload.copy()
        download_payload["data"]["filename"] = target_filename
        
        r_image = session.post(
            f"{api_base}?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en",
            json=download_payload, headers=headers, timeout=5
        )
        
        if r_image.status_code == 200:
            try:
                # Unwrap the Base64 JSON response
                response_json = r_image.json()
                if 'data' in response_json and 'txt_file' in response_json['data']:
                    b64_data = response_json['data']['txt_file']
                    if "," in b64_data: b64_data = b64_data.split(",")[1]
                    return base64.b64decode(b64_data)
            except:
                return None
            
    except Exception: return None
    return None

def get_image_content(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    clean_url = url.split('?')[0].lower()
    
    # 1. Standard Images
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, "url"
    
    # 2. Verint Logic
    if "caseid" in url.lower():
        image_bytes = fetch_verint_image(url)
        if image_bytes: return image_bytes, "bytes"
        return None, False

    # 3. Fallback
    return url, "url"

# 8. Feed Display
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        notes = str(row.get('status_notes', '')).lower()
        if 'duplicate' in notes: continue

        media_content, media_type = get_image_content(row.get('media_url'))
        
        if media_content:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    
                    try:
                        st.image(media_content, width="stretch")
                    except:
                        st.image("https://placehold.co/600x400?text=Image+Error", width="stretch")

                    if 'requested_datetime' in row:
                        date_str = pd.to_datetime(row['requested_datetime']).strftime('%b %d, %I:%M %p')
                    else: date_str = "?"
                    
                    raw_subtype = row.get('service_subtype', 'Unknown Issue')
                    display_title = raw_subtype.replace('_', ' ').title()
                    address = row.get('address', 'Location N/A')
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    case_id = row.get('service_request_id', '')
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
