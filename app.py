# ... (previous code remains the same) ...

        # Map View State
        view_state = pdk.ViewState(
            latitude=target_lat,
            longitude=target_lon,
            zoom=18,
            pitch=0,
        )

        st.pydeck_chart(pdk.Deck(
            # CHANGE: Use CARTO_LIGHT instead of mapbox to get streets without an API key
            map_style=pdk.map_styles.CARTO_LIGHT, 
            initial_view_state=view_state,
            layers=[layer_radius, layer_points],
            tooltip={"text": "{service_name}\n{requested_datetime}"}
        ))
    else:
        st.info("Map data unavailable.")
