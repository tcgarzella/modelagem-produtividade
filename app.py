"""
app.py — Monitora YieldGap
Interface principal com autenticação Supabase, mapa nativo e identidade visual.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

# ── Módulos do projeto ───────────────────────────────────────────────────────
from model_engine import simular_janela
from nasa_power import buscar_serie_climatica, calcular_tmed_ref
from auth import render_auth_page, logout
from brand import (
    inject_brand,
    render_header,
    render_sidebar_header,
    render_footer,
    efficiency_card,
    COLORS,
)


# ────────────────────────────────────────────────────────────────────────────
# Função de gráfico — definida antes de ser chamada
# ────────────────────────────────────────────────────────────────────────────

def _construir_grafico(resultados_anos: dict, prod_real: dict, anos: list, cultura: str):
    """Gráfico Plotly com faixa P10-P90, P50, real e eficiência."""

    anos_plot = sorted(resultados_anos.keys())
    p10_vals  = [resultados_anos[a]["prod_ating_p10"] for a in anos_plot]
    p50_vals  = [resultados_anos[a]["prod_ating_p50"] for a in anos_plot]
    p90_vals  = [resultados_anos[a]["prod_ating_p90"] for a in anos_plot]
    anos_str  = [str(a) for a in anos_plot]

    eff_vals = []
    for a in anos_plot:
        p50  = resultados_anos[a]["prod_ating_p50"]
        real = prod_real.get(a, 0)
        eff_vals.append((real / p50 * 100) if p50 > 0 and real > 0 else None)

    fig = go.Figure()

    # Envelope P10–P90
    fig.add_trace(go.Scatter(
        x=anos_str + anos_str[::-1],
        y=p90_vals + p10_vals[::-1],
        fill="toself",
        fillcolor="rgba(59,130,246,0.12)",
        line=dict(color="rgba(59,130,246,0.25)", width=1, dash="dot"),
        name="Faixa P10–P90",
        hoverinfo="skip",
    ))

    # P50
    fig.add_trace(go.Scatter(
        x=anos_str, y=p50_vals,
        mode="lines+markers",
        line=dict(color=COLORS["chart_blue"], width=2.5),
        marker=dict(size=7, color=COLORS["chart_blue"],
                    line=dict(width=2, color="#0e1117")),
        name="P50 atingível",
        line_shape="spline",
        hovertemplate="%{y:.0f} kg/ha<extra>P50 atingível</extra>",
    ))

    # Real
    real_vals_plot = [prod_real.get(a, 0) if prod_real.get(a, 0) > 0 else None
                      for a in anos_plot]
    fig.add_trace(go.Scatter(
        x=anos_str, y=real_vals_plot,
        mode="lines+markers",
        line=dict(color=COLORS["success"], width=2.5),
        marker=dict(size=8, color=COLORS["success"], symbol="diamond",
                    line=dict(width=2, color="#0e1117")),
        name="Produção real",
        line_shape="spline",
        connectgaps=False,
        hovertemplate="%{y:.0f} kg/ha<extra>Real</extra>",
    ))

    # Eficiência
    fig.add_trace(go.Scatter(
        x=anos_str, y=eff_vals,
        mode="lines+markers+text",
        line=dict(color=COLORS["chart_purple"], width=2, dash="dot"),
        marker=dict(size=6, color=COLORS["chart_purple"]),
        text=[f"{v:.1f}%" if v is not None else "" for v in eff_vals],
        textposition="top center",
        textfont=dict(color=COLORS["chart_purple"], size=11,
                      family="DM Mono, monospace"),
        name="Eficiência agronômica (%)",
        yaxis="y2",
        line_shape="spline",
        connectgaps=False,
        hovertemplate="%{y:.1f}%<extra>Eficiência agronômica</extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#13161f",
        font=dict(family="DM Sans, sans-serif", color="#d1d5db", size=12),
        title=dict(
            text=f"<b>{cultura}</b> — Produtividade Atingível vs. Real",
            font=dict(family="Rajdhani, sans-serif", size=18,
                      color=COLORS["primary_light"]),
            x=0.01,
        ),
        xaxis=dict(title="Safra", gridcolor="#1e2130", linecolor="#2a2e3e",
                   tickfont=dict(size=11), type="category"),
        yaxis=dict(title="Produtividade (kg/ha)", gridcolor="#1e2130",
                   linecolor="#2a2e3e", tickformat=".0f"),
        yaxis2=dict(title="Eficiência agronômica (%)", overlaying="y", side="right",
                    showgrid=False, tickformat=".0f", ticksuffix="%",
                    range=[0, 120], linecolor="#2a2e3e"),
        legend=dict(
            bgcolor="rgba(19,22,31,0.9)", bordercolor="#2a2e3e", borderwidth=1,
            font=dict(size=11), orientation="h",
            yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1e2130", bordercolor="#2a2e3e",
                        font=dict(family="DM Mono, monospace", size=11)),
        margin=dict(l=60, r=60, t=80, b=60),
        height=480,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Cards de eficiência — usando componentes nativos
    st.markdown("#### Eficiência por safra")
    anos_com_real = [a for a in anos_plot if prod_real.get(a, 0) > 0]
    if anos_com_real:
        cols = st.columns(len(anos_com_real))
        for i, ano in enumerate(anos_com_real):
            real = prod_real.get(ano, 0)
            p50  = resultados_anos[ano]["prod_ating_p50"]
            if p50 > 0:
                eff = real / p50 * 100
                label = "✅ Boa" if eff >= 85 else ("⚠️ Moderada" if eff >= 70 else "🔴 Baixa")
                with cols[i]:
                    st.metric(
                        label=f"{ano} — {label}",
                        value=f"{eff:.1f}%",
                        delta=f"Real: {real:.0f} kg/ha",
                    )

    # Tabela resumo
    st.markdown("#### Resumo numérico")
    rows = []
    for ano in anos_plot:
        r    = resultados_anos[ano]
        real = prod_real.get(ano, 0)
        p50  = r["prod_ating_p50"]
        eff  = f"{real/p50*100:.1f}%" if real > 0 and p50 > 0 else "—"
        rows.append({
            "Ano":        ano,
            "P10 (kg/ha)": f"{r['prod_ating_p10']:.0f}",
            "P50 (kg/ha)": f"{r['prod_ating_p50']:.0f}",
            "P90 (kg/ha)": f"{r['prod_ating_p90']:.0f}",
            "Real (kg/ha)": f"{real:.0f}" if real > 0 else "—",
            "Efic.": eff,
        })
    df = pd.DataFrame(rows).set_index("Ano")
    st.dataframe(df, use_container_width=True)

# ── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitora YieldGap",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Identidade visual global ─────────────────────────────────────────────────
inject_brand()

# ── Autenticação ─────────────────────────────────────────────────────────────
if not render_auth_page():
    st.stop()

# ── A partir daqui o usuário está autenticado ────────────────────────────────

render_header(show_user=True)

# ────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Parâmetros de simulação
# ────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()

    st.markdown("#### 🌿 Cultura")
    cultura = st.selectbox(
        "Cultura",
        ["Soja", "Milho", "Feijão", "Algodão", "Arroz", "Cana", "Trigo"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("#### 📅 Janela de Plantio")

    col_m1, col_d1 = st.columns(2)
    with col_m1:
        mes_ini = st.number_input("Mês ini", 1, 12, 10)
    with col_d1:
        dia_ini = st.number_input("Dia ini", 1, 31, 1)

    col_m2, col_d2 = st.columns(2)
    with col_m2:
        mes_fim = st.number_input("Mês fim", 1, 12, 11)
    with col_d2:
        dia_fim = st.number_input("Dia fim", 1, 31, 30)

    passo = st.number_input("Passo (dias)", 1, 15, 5)

    st.markdown("---")
    st.markdown("#### 🪨 Solo")
    argila = st.number_input("Argila (%)", 5.0, 80.0, 13.8, step=0.1, format="%.1f")
    prof   = st.number_input("Prof. radicular (cm)", 10, 100, 30, step=5)

    st.markdown("---")
    st.markdown("#### 📅 Anos simulados")
    ano_ini = st.number_input("Ano inicial", 2015, 2030, 2021)
    ano_fim = st.number_input("Ano final",   2015, 2030, 2025)

    st.markdown("---")
    if st.button("Sair", key="btn_logout"):
        logout()
        st.rerun()

    st.markdown(f"""
    <div style="font-family:'DM Sans',sans-serif;font-size:0.7rem;
                color:#374151;text-align:center;margin-top:1rem;">
        {st.session_state.get('user_email','')}
    </div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────────
# MAIN — Tabs
# ────────────────────────────────────────────────────────────────────────────

tab_loc, tab_sim = st.tabs(["📍 Localização", "📊 Simulação"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — LOCALIZAÇÃO
# ════════════════════════════════════════════════════════════════════════════
with tab_loc:

    st.markdown("#### Defina o ponto de análise")
    st.markdown(
        '<div style="font-family:\'DM Sans\',sans-serif;font-size:0.82rem;'
        'color:#6b7280;margin-bottom:1.25rem;">'
        'Insira as coordenadas do talhão ou região de interesse. '
        'Use o link abaixo para localizar no Google Maps e copiar as coordenadas.'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        lat_input = st.number_input(
            "Latitude",
            value=st.session_state.get("coord_lat", -18.5871),
            format="%.6f",
            min_value=-35.0,
            max_value=5.0,
            step=0.0001,
            key="coord_lat",
        )
    with col2:
        lon_input = st.number_input(
            "Longitude",
            value=st.session_state.get("coord_lon", -48.8891),
            format="%.6f",
            min_value=-74.0,
            max_value=-34.0,
            step=0.0001,
            key="coord_lon",
        )

    # Link para Google Maps
    gmaps_url = f"https://maps.google.com/?q={lat_input},{lon_input}"
    st.markdown(
        f'🔗 [Visualizar ponto no Google Maps]({gmaps_url}) '
        f'— clique com botão direito no mapa para copiar as coordenadas.',
    )

    st.markdown("---")

    # Mapa nativo do Streamlit (pydeck — sem iframe)
    st.markdown(
        '<div style="font-family:\'DM Sans\',sans-serif;font-size:0.78rem;'
        'color:#6b7280;margin-bottom:0.5rem;">Prévia da localização:</div>',
        unsafe_allow_html=True,
    )

    map_df = pd.DataFrame({"lat": [lat_input], "lon": [lon_input]})
    st.map(map_df, zoom=9)

    st.markdown(f"""
    <div style="
        background: #13161f;
        border: 1px solid #2a2e3e;
        border-left: 3px solid #788c00;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-top: 0.75rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.85rem;
        color: #d1d5db;
    ">
        <b style="color:#8ca000;">Ponto definido:</b>
        Lat <code style="color:#bcd44a;">{lat_input:.6f}</code> &nbsp;·&nbsp;
        Lon <code style="color:#bcd44a;">{lon_input:.6f}</code>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — SIMULAÇÃO
# ════════════════════════════════════════════════════════════════════════════
with tab_sim:

    lat = st.session_state.get("coord_lat")
    lon = st.session_state.get("coord_lon")

    if lat is None or lon is None:
        st.info("📍 Defina a localização na aba **Localização** antes de simular.")
        st.stop()

    # Cabeçalho informativo
    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    with col_i1:
        st.metric("Cultura", cultura)
    with col_i2:
        st.metric("Latitude", f"{lat:.4f}°")
    with col_i3:
        st.metric("Longitude", f"{lon:.4f}°")
    with col_i4:
        st.metric("Argila", f"{argila:.1f}%")

    st.markdown("---")

    # ── Entrada de produção real ──────────────────────────────────────────
    st.markdown("#### Produção Real (kg/ha)")
    st.markdown(
        '<div style="font-family:\'DM Sans\',sans-serif;font-size:0.78rem;'
        'color:#6b7280;margin-bottom:0.75rem;">'
        'Insira a produtividade real observada para cálculo de eficiência. '
        'Deixe 0 para omitir o ano.</div>',
        unsafe_allow_html=True,
    )

    anos = list(range(int(ano_ini), int(ano_fim) + 1))
    n_cols = min(len(anos), 5)
    cols_real = st.columns(n_cols)
    prod_real = {}
    for i, ano in enumerate(anos):
        with cols_real[i % n_cols]:
            prod_real[ano] = st.number_input(
                str(ano),
                min_value=0.0,
                max_value=20000.0,
                value=0.0,
                step=1.0,
                format="%.0f",
                key=f"real_{ano}",
            )

    st.markdown("---")

    # ── Botão de simulação ────────────────────────────────────────────────
    run = st.button("▶  Simular", key="btn_simular", use_container_width=True)

    if run:
        with st.spinner("Buscando dados climáticos e simulando..."):
            try:
                anos_lista = list(range(int(ano_ini), int(ano_fim) + 1))
                # Inclui ano seguinte ao fim para cobrir ciclos que cruzam virada
                anos_busca = list(range(int(ano_ini), int(ano_fim) + 2))
                dados_clima = buscar_serie_climatica(lat, lon, anos_busca)

                tmed_ref = calcular_tmed_ref(dados_clima)

                resultados_anos = {}
                for ano in anos_lista:
                    res = simular_janela(
                        cultura=cultura,
                        ano=ano,
                        data_inicio_janela=date(ano, int(mes_ini), int(dia_ini)),
                        data_fim_janela=date(ano, int(mes_fim), int(dia_fim)),
                        passo_dias=int(passo),
                        serie_climatica=dados_clima,
                        latitude=lat,
                        argila_pct=argila,
                        z_cm=float(prof),
                        tmed_ref=tmed_ref,
                    )
                    resultados_anos[ano] = res

                st.session_state["resultados_anos"] = resultados_anos
                st.session_state["prod_real_saved"] = prod_real
                st.session_state["anos_sim"]        = anos_lista
                st.session_state["cultura_sim"]     = cultura

            except Exception as e:
                st.error(f"Erro na simulação: {e}")
                st.stop()

    # ── Resultados ────────────────────────────────────────────────────────
    if "resultados_anos" in st.session_state:
        resultados_anos = st.session_state["resultados_anos"]
        prod_real_saved = st.session_state.get("prod_real_saved", {})
        anos_sim        = st.session_state.get("anos_sim", anos)
        cultura_sim     = st.session_state.get("cultura_sim", cultura)

        _construir_grafico(resultados_anos, prod_real_saved, anos_sim, cultura_sim)


render_footer()
