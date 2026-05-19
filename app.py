"""
app.py — Monitora YieldGap
Interface principal com autenticação Supabase, seleção por mapa e identidade visual.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

# ── Módulos do projeto ───────────────────────────────────────────────────────
from model_engine import simular_janela
from nasa_power import buscar_serie_climatica, calcular_tmed_ref
from auth import render_auth_page, logout
from map_picker import render_map_picker
from brand import (
    inject_brand,
    render_header,
    render_sidebar_header,
    render_footer,
    efficiency_card,
    COLORS,
)

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
        mes_ini = st.number_input("Mês ini", 1, 12, 10, label_visibility="visible")
    with col_d1:
        dia_ini = st.number_input("Dia ini", 1, 31, 1, label_visibility="visible")

    col_m2, col_d2 = st.columns(2)
    with col_m2:
        mes_fim = st.number_input("Mês fim", 1, 12, 11, label_visibility="visible")
    with col_d2:
        dia_fim = st.number_input("Dia fim", 1, 31, 30, label_visibility="visible")

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

    # Logout
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

tab_sim, tab_loc = st.tabs(["📊 Simulação", "📍 Localização"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SIMULAÇÃO
# ════════════════════════════════════════════════════════════════════════════
with tab_sim:

    # Verifica se coordenadas foram definidas
    lat = st.session_state.get("map_picker_lat")
    lon = st.session_state.get("map_picker_lon")

    if lat is None or lon is None:
        st.info("📍 Defina a localização na aba **Localização** antes de simular.")
        st.stop()

    # Cabeçalho da simulação
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    with col_info1:
        st.metric("Cultura", cultura)
    with col_info2:
        st.metric("Latitude", f"{lat:.4f}°")
    with col_info3:
        st.metric("Longitude", f"{lon:.4f}°")
    with col_info4:
        st.metric("Argila", f"{argila:.1f}%")

    st.markdown("---")

    # ── Entrada de produção real ──────────────────────────────────────────
    st.markdown("#### Produção Real (t/ha)")
    st.markdown(
        '<div style="font-family:\'DM Sans\',sans-serif;font-size:0.78rem;'
        'color:#6b7280;margin-bottom:0.75rem;">Insira a produtividade real '
        'observada para cálculo de eficiência. Deixe 0 para omitir o ano.</div>',
        unsafe_allow_html=True,
    )

    anos = list(range(int(ano_ini), int(ano_fim) + 1))
    cols_real = st.columns(min(len(anos), 5))
    prod_real = {}
    for i, ano in enumerate(anos):
        with cols_real[i % 5]:
            prod_real[ano] = st.number_input(
                str(ano), min_value=0.0, max_value=20.0,
                value=0.0, step=0.1, format="%.3f",
                key=f"real_{ano}",
            )

    st.markdown("---")

    # ── Botão de simulação ────────────────────────────────────────────────
    run = st.button("▶  Simular", key="btn_simular", use_container_width=True)

    if run:
        with st.spinner("Buscando dados climáticos e simulando..."):
            try:
                # Busca dados NASA POWER
                anos_lista = list(range(int(ano_ini), int(ano_fim) + 1))
                dados_clima = buscar_serie_climatica(lat, lon, anos_lista)

                # Simula para cada ano
                resultados_anos = {}
                for ano in anos:
                    res = simular_janela(
                        dados_clima=dados_clima,
                        ano=ano,
                        cultura=cultura,
                        lat=lat,
                        lon=lon,
                        argila=argila,
                        prof_rad_cm=prof,
                        mes_ini=int(mes_ini),
                        dia_ini=int(dia_ini),
                        mes_fim=int(mes_fim),
                        dia_fim=int(dia_fim),
                        passo=int(passo),
                    )
                    resultados_anos[ano] = res

                st.session_state["resultados_anos"] = resultados_anos
                st.session_state["prod_real"]       = prod_real
                st.session_state["anos_sim"]        = anos
                st.session_state["cultura_sim"]     = cultura

            except Exception as e:
                st.error(f"Erro na simulação: {e}")
                st.stop()

    # ── Renderização dos resultados ───────────────────────────────────────
    if "resultados_anos" in st.session_state:
        resultados_anos = st.session_state["resultados_anos"]
        prod_real_saved = st.session_state.get("prod_real", {})
        anos_sim        = st.session_state.get("anos_sim", anos)
        cultura_sim     = st.session_state.get("cultura_sim", cultura)

        construir_grafico(resultados_anos, prod_real_saved, anos_sim, cultura_sim)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — LOCALIZAÇÃO
# ════════════════════════════════════════════════════════════════════════════
with tab_loc:
    st.markdown("#### Selecione a área de interesse")
    st.markdown(
        '<div style="font-family:\'DM Sans\',sans-serif;font-size:0.82rem;'
        'color:#6b7280;margin-bottom:1rem;">Clique no mapa para definir o '
        'ponto central da análise. Use a camada de satélite para identificar '
        'o talhão ou região de interesse.</div>',
        unsafe_allow_html=True,
    )

    lat_sel, lon_sel = render_map_picker(
        default_lat=-18.5871,
        default_lon=-48.8891,
        zoom_start=9,
        height=500,
        key="map_picker",
    )

    st.markdown("---")
    st.markdown(f"""
    <div style="
        background: #13161f;
        border: 1px solid #2a2e3e;
        border-left: 3px solid #788c00;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.85rem;
        color: #d1d5db;
    ">
        <b style="color:#8ca000;">Ponto selecionado:</b>
        Lat <code style="color:#bcd44a;">{lat_sel:.6f}</code> &nbsp;·&nbsp;
        Lon <code style="color:#bcd44a;">{lon_sel:.6f}</code>
        <br>
        <span style="color:#6b7280;font-size:0.75rem;">
        Clique em qualquer ponto do mapa ou use a entrada manual para ajustar.
        </span>
    </div>
    """, unsafe_allow_html=True)

render_footer()


# ────────────────────────────────────────────────────────────────────────────
# Função de gráfico (mantida do app original, com ajustes de estilo)
# ────────────────────────────────────────────────────────────────────────────

def construir_grafico(resultados_anos: dict, prod_real: dict, anos: list, cultura: str):
    """Constrói o gráfico Plotly com faixa P10-P90, P70, real e eficiência."""

    anos_plot   = sorted(resultados_anos.keys())
    p10_vals    = [resultados_anos[a]["prod_ating_p10"]   for a in anos_plot]
    p30_vals    = [resultados_anos[a]["prod_ating_p30"]   for a in anos_plot]
    p70_vals    = [resultados_anos[a]["prod_ating_p70"]   for a in anos_plot]
    p90_vals    = [resultados_anos[a]["prod_ating_p90"]   for a in anos_plot]
    real_vals   = [prod_real.get(a, 0) for a in anos_plot]
    anos_str    = [str(a) for a in anos_plot]

    # Eficiência relativa ao P70
    eff_vals = []
    for a in anos_plot:
        p70 = resultados_anos[a]["prod_ating_p70"]
        real = prod_real.get(a, 0)
        eff_vals.append((real / p70 * 100) if p70 > 0 and real > 0 else None)

    fig = go.Figure()

    # Envelope P10–P90 (área preenchida)
    fig.add_trace(go.Scatter(
        x=anos_str + anos_str[::-1],
        y=p90_vals + p10_vals[::-1],
        fill="toself",
        fillcolor="rgba(59,130,246,0.12)",
        line=dict(color="rgba(59,130,246,0.25)", width=1, dash="dot"),
        name="Faixa P10–P90",
        hoverinfo="skip",
        showlegend=True,
    ))

    # P30 (linha interna suave)
    fig.add_trace(go.Scatter(
        x=anos_str, y=p30_vals,
        mode="lines",
        line=dict(color="rgba(59,130,246,0.35)", width=1, dash="dash"),
        name="P30 atingível",
        line_shape="spline",
        hovertemplate="%{y:.3f} t/ha<extra>P30</extra>",
    ))

    # P70 — linha central
    fig.add_trace(go.Scatter(
        x=anos_str, y=p70_vals,
        mode="lines+markers",
        line=dict(color=COLORS["chart_blue"], width=2.5),
        marker=dict(size=7, color=COLORS["chart_blue"],
                    line=dict(width=2, color="#0e1117")),
        name="P70 atingível",
        line_shape="spline",
        hovertemplate="%{y:.3f} t/ha<extra>P70 atingível</extra>",
    ))

    # Produção real
    real_vals_plot = [v if v > 0 else None for v in real_vals]
    fig.add_trace(go.Scatter(
        x=anos_str, y=real_vals_plot,
        mode="lines+markers",
        line=dict(color=COLORS["success"], width=2.5),
        marker=dict(size=8, color=COLORS["success"],
                    symbol="diamond",
                    line=dict(width=2, color="#0e1117")),
        name="Produção real",
        line_shape="spline",
        connectgaps=False,
        hovertemplate="%{y:.3f} t/ha<extra>Real</extra>",
    ))

    # Eficiência (eixo secundário)
    fig.add_trace(go.Scatter(
        x=anos_str, y=eff_vals,
        mode="lines+markers",
        line=dict(color=COLORS["chart_purple"], width=2, dash="dot"),
        marker=dict(size=6, color=COLORS["chart_purple"]),
        name="Eficiência (%)",
        yaxis="y2",
        line_shape="spline",
        connectgaps=False,
        hovertemplate="%{y:.1f}%<extra>Eficiência</extra>",
    ))

    # Layout
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
        xaxis=dict(
            title="Safra",
            gridcolor="#1e2130",
            linecolor="#2a2e3e",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="Produtividade (t/ha)",
            gridcolor="#1e2130",
            linecolor="#2a2e3e",
            tickformat=".2f",
        ),
        yaxis2=dict(
            title="Eficiência (%)",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=".0f",
            ticksuffix="%",
            range=[0, 120],
            linecolor="#2a2e3e",
        ),
        legend=dict(
            bgcolor="rgba(19,22,31,0.9)",
            bordercolor="#2a2e3e",
            borderwidth=1,
            font=dict(size=11),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1e2130",
            bordercolor="#2a2e3e",
            font=dict(family="DM Mono, monospace", size=11),
        ),
        margin=dict(l=60, r=60, t=80, b=50),
        height=480,
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Cards de eficiência ───────────────────────────────────────────────
    st.markdown("#### Eficiência por safra")
    cards_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:0.75rem;">'
    for i, ano in enumerate(anos_plot):
        real = prod_real.get(ano, 0)
        p70  = resultados_anos[ano]["prod_ating_p70"]
        if real > 0 and p70 > 0:
            cards_html += efficiency_card(ano, real, p70)
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    # ── Tabela resumo ─────────────────────────────────────────────────────
    st.markdown("#### Resumo numérico")
    rows = []
    for ano in anos_plot:
        r = resultados_anos[ano]
        real = prod_real.get(ano, 0)
        p70  = r["prod_ating_p70"]
        eff  = f"{real/p70*100:.1f}%" if real > 0 and p70 > 0 else "—"
        rows.append({
            "Ano":      ano,
            "P10":      f"{r['prod_ating_p10']:.3f}",
            "P30":      f"{r['prod_ating_p30']:.3f}",
            "P70":      f"{r['prod_ating_p70']:.3f}",
            "P90":      f"{r['prod_ating_p90']:.3f}",
            "Real":     f"{real:.3f}" if real > 0 else "—",
            "Efic.":    eff,
        })

    df = pd.DataFrame(rows).set_index("Ano")
    st.dataframe(df, use_container_width=True)
