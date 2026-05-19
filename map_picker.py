"""
map_picker.py — Seleção de coordenadas via mapa interativo
Usa streamlit-folium com camada de satélite Esri World Imagery
"""

import streamlit as st
import folium
from streamlit_folium import st_folium


# Tile layers disponíveis
TILE_LAYERS = {
    "Satélite (Esri)": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri World Imagery",
        "name": "Satélite",
        "overlay": False,
        "control": True,
    },
    "OpenStreetMap": {
        "tiles": "OpenStreetMap",
        "attr": "OpenStreetMap contributors",
        "name": "Mapa",
        "overlay": False,
        "control": True,
    },
    "Satélite + Labels (Esri)": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri Reference",
        "name": "Labels",
        "overlay": True,
        "control": True,
    },
}

# CSS para o componente de mapa
MAP_CSS = """
<style>
.map-section {
    background: #13161f;
    border: 1px solid #2a2e3e;
    border-radius: 12px;
    padding: 1.25rem 1.5rem 1rem;
    margin-bottom: 1rem;
}
.map-section-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    color: #788c00;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}
.coord-display {
    display: flex;
    gap: 1rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
}
.coord-chip {
    background: #1e2130;
    border: 1px solid #2a2e3e;
    border-radius: 8px;
    padding: 0.4rem 0.85rem;
    font-family: 'DM Mono', 'Courier New', monospace;
    font-size: 0.82rem;
    color: #8ca000;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.coord-chip span {
    color: #6b7280;
    font-size: 0.75rem;
}
.map-hint {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem;
    color: #4b5563;
    margin-top: 0.5rem;
    font-style: italic;
}
</style>
"""


def render_map_picker(
    default_lat: float = -18.59,
    default_lon: float = -48.89,
    zoom_start: int = 10,
    height: int = 420,
    key: str = "map_picker",
) -> tuple[float | None, float | None]:
    """
    Renderiza mapa interativo para seleção de coordenadas.
    
    Retorna (latitude, longitude) do ponto clicado, ou os valores
    default se nenhum clique foi registrado ainda.
    
    O ponto selecionado persiste em st.session_state[key + '_lat/_lon'].
    """
    st.markdown(MAP_CSS, unsafe_allow_html=True)

    # Estado persistente
    lat_key = f"{key}_lat"
    lon_key = f"{key}_lon"

    if lat_key not in st.session_state:
        st.session_state[lat_key] = default_lat
    if lon_key not in st.session_state:
        st.session_state[lon_key] = default_lon

    current_lat = st.session_state[lat_key]
    current_lon = st.session_state[lon_key]

    # ── Construção do mapa ──────────────────────────────────────────────────
    m = folium.Map(
        location=[current_lat, current_lon],
        zoom_start=zoom_start,
        tiles=None,  # Sem tile padrão; adicionamos manualmente
    )

    # Camada base: satélite Esri
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satélite",
        overlay=False,
        control=True,
    ).add_to(m)

    # Camada de labels sobre satélite
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Reference Labels",
        name="Nomes/Labels",
        overlay=True,
        control=True,
        opacity=0.85,
    ).add_to(m)

    # Camada OSM alternativa
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    # Marcador do ponto atual
    folium.Marker(
        location=[current_lat, current_lon],
        popup=folium.Popup(
            f"<b>Ponto selecionado</b><br>Lat: {current_lat:.4f}<br>Lon: {current_lon:.4f}",
            max_width=200,
        ),
        tooltip="Clique no mapa para mover",
        icon=folium.Icon(
            color="green",
            icon="leaf",
            prefix="fa",
        ),
    ).add_to(m)

    # Controle de camadas
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Renderização ────────────────────────────────────────────────────────
    st.markdown('<div class="map-hint">🖱 Clique em qualquer ponto do mapa para selecionar as coordenadas</div>',
                unsafe_allow_html=True)

    map_data = st_folium(
        m,
        height=height,
        width="100%",
        key=key,
        returned_objects=["last_clicked"],
    )

    # Captura clique
    if map_data and map_data.get("last_clicked"):
        clicked = map_data["last_clicked"]
        st.session_state[lat_key] = round(clicked["lat"], 6)
        st.session_state[lon_key] = round(clicked["lng"], 6)
        current_lat = st.session_state[lat_key]
        current_lon = st.session_state[lon_key]

    # Display das coordenadas selecionadas
    st.markdown(f"""
    <div class="coord-display">
        <div class="coord-chip">
            <span>LAT</span> {current_lat:.6f}
        </div>
        <div class="coord-chip">
            <span>LON</span> {current_lon:.6f}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Opção de entrada manual como fallback
    with st.expander("✏️ Inserir coordenadas manualmente", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            manual_lat = st.number_input(
                "Latitude", value=current_lat, format="%.6f",
                min_value=-35.0, max_value=5.0, step=0.0001,
                key=f"{key}_manual_lat",
            )
        with col2:
            manual_lon = st.number_input(
                "Longitude", value=current_lon, format="%.6f",
                min_value=-74.0, max_value=-34.0, step=0.0001,
                key=f"{key}_manual_lon",
            )
        if st.button("Aplicar coordenadas", key=f"{key}_apply_manual"):
            st.session_state[lat_key] = manual_lat
            st.session_state[lon_key] = manual_lon
            st.rerun()

    return st.session_state[lat_key], st.session_state[lon_key]
