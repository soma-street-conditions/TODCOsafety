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
st.set_page_config(page_title="Verint Inspector", page_icon="🕵️", layout="wide")
st.title("🕵️ Verint File Inspector")

# --- 2. THE INSPECTOR TOOL ---
debug_url = st.text_input("Paste a Verint URL to inspect filenames (e.g. from Ticket 101003150220):")

if st.button("Inspect Files"):
    if not debug_url:
        st.warning("Please paste a URL first.")
    else:
        st.info(f"Inspecting: {debug_url}")
        
        # --- THE CORE LOGIC (With Print Statements) ---
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://mobile311.sfgov.org/",
            }

            # A. Parse URL
            parsed = urlparse(debug_url)
            qs = parse_qs(parsed.query)
            url_case_id = qs.get('caseid', [None])[0]
            st.write(f"**Target Case ID:** `{url_case_id}`")

            # B. Visit Page
            r_page = session.get(debug_url, headers=headers, timeout=5)
            final_referer = r_page.url 
            html = r_page.text
            
            # C. Get Secrets
            formref_match = re.search(r'"formref"\s*:\s*"([^"]+)"', html)
            if formref_match:
                formref = formref_match.group(1)
                st.write(f"**FormRef:** `{formref}`")
            else:
                st.error("Could not find FormRef.")
                st.stop()
                
            csrf_match = re.search(r'name="_csrf_token"\s+content="([^"]+)"', html)
            csrf_token = csrf_match.group(1) if csrf_match else None
            
            # D. Handshake
            try:
                citizen_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
                headers["Referer"] = final_referer
                headers["Origin"] = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
                if csrf_token: headers["X-CSRF-TOKEN"] = csrf_token
                
                r_handshake = session.get(citizen_url, headers=headers, timeout=5)
                if 'Authorization' in r_handshake.headers:
                    headers["Authorization"] = r_handshake.headers['Authorization']
                    st.success("Handshake Successful (Auth Token Acquired)")
            except: pass

            # E. Get File List
            api_base = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/custom"
            headers["Content-Type"] = "application/json"
            
            payload = {
                "data": {"caseid": str(url_case_id), "formref": formref},
                "name": "download_attachments",
                "email": "", "xref": "", "xref1": "", "xref2": ""
            }
            
            r_list = session.post(
                f"{api_base}?action=get_attachments_details&actionedby=&loadform=true&access=citizen&locale=en",
                json=payload, headers=headers, timeout=5
            )
            
            if r_list.status_code == 200:
                files_data = r_list.json()
                st.write("**Raw API Response:**")
                st.json(files_data)
                
                filename_str = ""
                if 'data' in files_data and 'formdata_filenames' in files_data['data']:
                    filename_str = files_data['data']['formdata_filenames']
                    
                if filename_str:
                    raw_files = filename_str.split(';')
                    st.markdown("### 📂 Files Found on Server:")
                    for f in raw_files:
                        if f.strip():
                            st.code(f.strip())
                else:
                    st.error("No filenames found in response.")
            else:
                st.error(f"API Error: {r_list.status_code}")

        except Exception as e:
            st.error(f"Crash: {e}")

st.markdown("---")
st.write("*(The standard dashboard logic has been hidden to focus on debugging)*")
