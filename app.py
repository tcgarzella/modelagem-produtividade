"""
app.py — Monitora YieldGap
Interface principal com autenticação Supabase, mapa nativo e identidade visual.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

# ── Módulos do projeto ───────────────────────────────────────────────────────
from model_engine import simular_janela, CULTURAS

# Fator de conversão kg/ha → unidade de exibição por cultura
_SC_KG = {
    "Soja": 60, "Milho": 60, "Feijão": 60, "Trigo": 60,
    "Arroz": 50, "Algodão": 15, "Cana": 1000,
}
_SC_LABEL = {
    "Soja": "sc/ha", "Milho": "sc/ha", "Feijão": "sc/ha", "Trigo": "sc/ha",
    "Arroz": "sc/ha", "Algodão": "@/ha", "Cana": "t/ha",
}


def _eficiencia_pct(real_kg: float, p50_kg: float):
    """Eficiência agronômica (%) = real / P50 * 100, limitada a 100% na exibição.

    Nota: o valor bruto pode superar 100% quando a produção real supera o P50
    modelado — isso é um sinal de possível incerteza no P50 daquela safra
    (dado climático, cache ou calibração), não uma eficiência real acima do
    teto atingível. Por decisão de produto, exibimos limitado a 100% para não
    exigir explicação desse artefato ao cliente. Se precisar investigar uma
    safra específica, calcule real/p50_kg*100 sem o min() para ver o valor bruto.
    """
    if p50_kg <= 0 or real_kg <= 0:
        return None
    return min(real_kg / p50_kg * 100, 100.0)
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

def _construir_grafico(resultados_anos: dict, prod_real: dict, anos: list, cultura: str, unidade: str = "kg/ha", f_genetico: float = 1.33):
    """Gráfico Plotly com faixa P10-P90, P50, real e eficiência."""

    anos_plot = sorted(resultados_anos.keys())
    # Conversão de unidade para exibição
    _fator  = _SC_KG.get(cultura, 60) if unidade == "sc/ha" else 1
    _un_lbl = _SC_LABEL.get(cultura, "sc/ha") if unidade == "sc/ha" else "kg/ha"
    def _c(v): return v / _fator if v is not None and v > 0 else v

    p10_vals  = [_c(resultados_anos[a]["prod_ating_p10"]) for a in anos_plot]
    p50_vals  = [_c(resultados_anos[a]["prod_ating_p50"]) for a in anos_plot]
    p90_vals  = [_c(resultados_anos[a]["prod_ating_p90"]) for a in anos_plot]
    anos_str  = [f"{str(a)[2:]}/{str(a+1)[2:]}" for a in anos_plot]

    eff_vals = []
    for a in anos_plot:
        p50_kg = resultados_anos[a]["prod_ating_p50"]   # sempre em kg/ha
        real   = prod_real.get(a, 0)                    # sempre em kg/ha
        eff_vals.append(_eficiencia_pct(real, p50_kg))

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
        hovertemplate=f"%{{y:.1f}} {_un_lbl}<extra>P50 atingível</extra>",
    ))

    # Real
    real_vals_plot = [_c(prod_real.get(a, 0)) if prod_real.get(a, 0) > 0 else None
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
        hovertemplate=f"%{{y:.1f}} {_un_lbl}<extra>Real</extra>",
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
        yaxis=dict(title=f"Produtividade ({_un_lbl})", gridcolor="#1e2130",
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
            real   = prod_real.get(ano, 0)
            p50_kg = resultados_anos[ano]["prod_ating_p50"]   # kg/ha bruto
            eff = _eficiencia_pct(real, p50_kg)
            if eff is not None:
                label = "✅ Boa" if eff >= 85 else ("⚠️ Moderada" if eff >= 70 else "🔴 Baixa")
                with cols[i]:
                    st.metric(
                        label=f"{str(ano)[2:]}/{str(ano+1)[2:]} — {label}",
                        value=f"{eff:.1f}%",
                        delta=f"Real: {_c(real):.1f} {_un_lbl}",
                    )

    # Tabela resumo
    st.markdown("#### Resumo numérico")
    rows = []
    for ano in anos_plot:
        r    = resultados_anos[ano]
        real = prod_real.get(ano, 0)
        p50  = r["prod_ating_p50"]
        eff_v = _eficiencia_pct(real, p50)
        eff  = f"{eff_v:.1f}%" if eff_v is not None else "—"
        rows.append({
            "Safra":               f"{str(ano)[2:]}/{str(ano+1)[2:]}",
            f"P10 ({_un_lbl})":    f"{_c(r['prod_ating_p10']):.1f}",
            f"P50 ({_un_lbl})":    f"{_c(r['prod_ating_p50']):.1f}",
            f"P90 ({_un_lbl})":    f"{_c(r['prod_ating_p90']):.1f}",
            f"Real ({_un_lbl})":   f"{_c(real):.1f}" if real > 0 else "—",
            "Efic.": eff,
        })
    df = pd.DataFrame(rows).set_index("Safra")
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
# Defaults — sobrescritos pelo expander no sidebar
unidade    = "kg/ha"
f_genetico = 1.33

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
    with st.expander("⚙️ Parâmetros avançados", expanded=False):
        unidade = st.radio(
            "Unidade de produtividade",
            ["kg/ha", "sc/ha"],
            index=0,
            horizontal=True,
            help="Soja / Milho / Feijão / Trigo = 60 kg/sc · Arroz = 50 kg/sc · Cana = t/ha · Algodão = @/ha (15 kg)",
        )
        _fg_default = CULTURAS[cultura].get("f_genetico", 1.33)
        f_genetico = st.number_input(
            "Fator genético (f_genetico)",
            min_value=0.50,
            max_value=2.00,
            value=_fg_default,
            step=0.01,
            format="%.2f",
            help="Multiplica o teto atingível. Padrão carregado por cultura. f < 1 rebaixa o potencial; f > 1 eleva.",
        )
        if abs(f_genetico - 1.0) > 0.001:
            sentido = "rebaixado" if f_genetico < 1.0 else "elevado"
            st.caption(
                f"⚠️ Teto {sentido} em {abs(1-f_genetico)*100:.0f}% pelo fator genético "
                f"(padrão da cultura: {_fg_default:.2f})."
            )

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

tab_loc, tab_sim, tab_clima = st.tabs(["📍 Localização", "📊 Simulação", "🌦 Clima"])


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
    _fator   = _SC_KG.get(cultura, 60) if unidade == 'sc/ha' else 1
    _un_lbl  = _SC_LABEL.get(cultura, 'sc/ha') if unidade == 'sc/ha' else 'kg/ha'
    _max_inp = round(20000.0 / _fator, 2)

    st.markdown(f'#### Produção Real ({_un_lbl})')
    st.markdown(
        f'<div style="font-family:\'DM Sans\',sans-serif;font-size:0.78rem;'
        f'color:#6b7280;margin-bottom:0.75rem;">'
        f'Insira em <b>{_un_lbl}</b>, com até 2 casas decimais (aceita ponto ou vírgula). '
        f'Deixe 0 para omitir a safra.</div>',
        unsafe_allow_html=True,
    )

    def _parse_ptbr_number(txt: str):
        """Converte texto em float aceitando ',' ou '.' como separador decimal.
        Se ambos aparecerem, assume convenção BR ('.' milhar, ',' decimal).
        Retorna None se o texto não for um número válido."""
        if txt is None:
            return None
        txt = txt.strip()
        if txt == "":
            return 0.0
        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return None

    anos = list(range(int(ano_ini), int(ano_fim) + 1))
    n_cols = min(len(anos), 5)
    cols_real = st.columns(n_cols)
    prod_real = {}
    for i, ano in enumerate(anos):
        with cols_real[i % n_cols]:
            txt_inp = st.text_input(
                f"{str(ano)[2:]}/{str(ano+1)[2:]}",
                value="0,00",
                key=f'real_{ano}',
                help=(
                    f"Produção real em {_un_lbl}, 0 a {_max_inp:.2f}. "
                    f"Aceita ponto ou vírgula, até 2 casas decimais."
                ),
            )
            v_inp = _parse_ptbr_number(txt_inp)
            if v_inp is None:
                st.error("Valor inválido — use número com até 2 casas decimais (ex: 72,80 ou 72.80).")
                v_inp = 0.0
            elif v_inp < 0 or v_inp > _max_inp:
                st.error(f"Fora do intervalo permitido (0–{_max_inp:.2f} {_un_lbl}).")
                v_inp = 0.0
            v_inp = round(v_inp, 2)
            prod_real[ano] = v_inp * _fator if v_inp > 0 else 0.0

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
                        f_genetico=f_genetico,
                    )
                    resultados_anos[ano] = res

                st.session_state["resultados_anos"] = resultados_anos
                st.session_state["prod_real_saved"] = prod_real
                st.session_state["anos_sim"]        = anos_lista
                st.session_state["cultura_sim"]     = cultura
                st.session_state["unidade_sim"]     = unidade
                st.session_state["f_genetico_sim"]  = f_genetico

            except Exception as e:
                st.error(f"Erro na simulação: {e}")
                st.stop()

    # ── Resultados ────────────────────────────────────────────────────────
    if "resultados_anos" in st.session_state:
        resultados_anos  = st.session_state["resultados_anos"]
        prod_real_saved  = st.session_state.get("prod_real_saved", {})
        anos_sim         = st.session_state.get("anos_sim", anos)
        cultura_sim      = st.session_state.get("cultura_sim", cultura)
        unidade_sim      = st.session_state.get("unidade_sim", unidade)
        f_genetico_sim   = st.session_state.get("f_genetico_sim", f_genetico)

        _construir_grafico(resultados_anos, prod_real_saved, anos_sim, cultura_sim, unidade=unidade_sim, f_genetico=f_genetico_sim)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — DIAGNÓSTICO CLIMÁTICO
# ════════════════════════════════════════════════════════════════════════════
with tab_clima:

    lat_c = st.session_state.get("coord_lat")
    lon_c = st.session_state.get("coord_lon")

    if lat_c is None or lon_c is None:
        st.info("📍 Defina a localização na aba **Localização** antes de consultar o clima.")
        st.stop()

    st.markdown("#### Diagnóstico climático — dados NASA POWER")
    st.markdown(
        "<div style=\"font-family:'DM Sans',sans-serif;font-size:0.82rem;"
        "color:#6b7280;margin-bottom:1rem;\">"
        "Temperatura média e precipitação mensal por ano. "
        "Útil para identificar lacunas, anomalias ou anos com dados inconsistentes.</div>",
        unsafe_allow_html=True,
    )

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        ano_cli_ini = st.number_input("Ano inicial", 2015, 2030, 2019, key="cli_ini")
    with col_a2:
        ano_cli_fim = st.number_input("Ano final",   2015, 2030, 2025, key="cli_fim")

    if st.button("🔍 Buscar dados climáticos", key="btn_clima"):
        with st.spinner("Buscando série climática..."):
            try:
                anos_c = list(range(int(ano_cli_ini), int(ano_cli_fim) + 1))
                serie_c = buscar_serie_climatica(lat_c, lon_c, anos_c)
                st.session_state["serie_clima_diag"] = serie_c
                st.session_state["anos_clima_diag"]  = anos_c
            except Exception as e:
                st.error(f"Erro ao buscar dados: {e}")
                st.stop()

    if "serie_clima_diag" in st.session_state:
        import numpy as np
        from datetime import date as _date

        serie_c = st.session_state["serie_clima_diag"]
        anos_c  = st.session_state["anos_clima_diag"]
        MESES   = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

        # Agregar por ano/mês
        from collections import defaultdict
        agg = defaultdict(lambda: defaultdict(list))
        for d in serie_c:
            dt = d["data"]
            agg[dt.year][dt.month].append({
                "tmed": (float(d["Tmax"]) + float(d["Tmin"])) / 2,
                "p":    float(d.get("P", 0)),
                "tmax": float(d["Tmax"]),
                "tmin": float(d["Tmin"]),
            })

        # Tabela de Tmed mensal
        st.markdown("##### Temperatura média mensal (°C)")
        rows_t = []
        for ano in anos_c:
            row = {"Ano": str(ano)}
            n_dias = 0
            for m in range(1, 13):
                vals = agg[ano][m]
                n_dias += len(vals)
                row[MESES[m-1]] = f"{np.mean([v['tmed'] for v in vals]):.1f}" if vals else "—"
            row["N dias"] = n_dias
            rows_t.append(row)
        df_t = pd.DataFrame(rows_t).set_index("Ano")

        # Destacar anos com N dias < 340 (série incompleta)
        def _style_ndays(val):
            try:
                v = int(val)
                if v < 340: return "color: #ef4444; font-weight: bold"
                if v < 365: return "color: #f59e0b"
            except: pass
            return ""

        st.dataframe(
            df_t.style.map(_style_ndays, subset=["N dias"]),
            use_container_width=True,
        )

        # Tabela de precipitação mensal
        st.markdown("##### Precipitação mensal (mm)")
        rows_p = []
        for ano in anos_c:
            row = {"Ano": str(ano)}
            total = 0
            for m in range(1, 13):
                vals = agg[ano][m]
                soma = sum(v["p"] for v in vals)
                total += soma
                row[MESES[m-1]] = f"{soma:.0f}" if vals else "—"
            row["Total"] = f"{total:.0f}"
            rows_p.append(row)
        df_p = pd.DataFrame(rows_p).set_index("Ano")

        # Destacar totais anuais anômalos (< 800mm ou > 2500mm)
        def _style_total(val):
            try:
                v = float(val)
                if v < 800:  return "color: #ef4444; font-weight: bold"
                if v > 2500: return "color: #f59e0b; font-weight: bold"
            except: pass
            return ""

        st.dataframe(
            df_p.style.map(_style_total, subset=["Total"]),
            use_container_width=True,
        )

        # Gráfico de precipitação anual total
        st.markdown("##### Precipitação anual total e temperatura média anual")
        totais_p   = []
        tmed_anual = []
        for ano in anos_c:
            todos = [v for m in agg[ano].values() for v in m]
            totais_p.append(sum(v["p"] for v in todos))
            tmed_anual.append(np.mean([v["tmed"] for v in todos]) if todos else None)

        fig_c = go.Figure()
        fig_c.add_trace(go.Bar(
            x=[str(a) for a in anos_c],
            y=totais_p,
            name="Precipitação total (mm)",
            marker_color="rgba(59,130,246,0.7)",
            yaxis="y1",
        ))
        fig_c.add_trace(go.Scatter(
            x=[str(a) for a in anos_c],
            y=tmed_anual,
            mode="lines+markers",
            name="Tmed anual (°C)",
            line=dict(color="#f59e0b", width=2),
            marker=dict(size=7),
            yaxis="y2",
        ))
        fig_c.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#13161f",
            font=dict(family="DM Sans, sans-serif", color="#d1d5db", size=12),
            xaxis=dict(title="Ano", gridcolor="#1e2130", type="category"),
            yaxis=dict(title="Precipitação (mm)", gridcolor="#1e2130"),
            yaxis2=dict(title="Tmed (°C)", overlaying="y", side="right",
                        showgrid=False, range=[15, 35]),
            legend=dict(bgcolor="rgba(19,22,31,0.9)", bordercolor="#2a2e3e",
                        borderwidth=1, font=dict(size=11),
                        orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=60, r=60, t=60, b=60),
            height=380,
            bargap=0.3,
        )
        st.plotly_chart(fig_c, use_container_width=True)

        # Diagnóstico de consistência
        st.markdown("##### Diagnóstico de consistência")
        problemas = []
        for ano in anos_c:
            todos = [v for m in agg[ano].values() for v in m]
            n = len(todos)
            if n < 340:
                problemas.append(f"⚠️ **{ano}**: apenas {n} dias na série — ano incompleto, simular com cautela.")
            prec_total = sum(v["p"] for v in todos)
            if prec_total < 800:
                problemas.append(f"🔴 **{ano}**: precipitação total {prec_total:.0f} mm — valor muito baixo para o Cerrado.")
            if prec_total > 2500:
                problemas.append(f"🟡 **{ano}**: precipitação total {prec_total:.0f} mm — valor elevado, verificar consistência.")
            tmeds = [v["tmed"] for v in todos]
            if tmeds and (min(tmeds) < 10 or max(tmeds) > 40):
                problemas.append(f"🔴 **{ano}**: temperatura fora do range esperado ({min(tmeds):.1f}–{max(tmeds):.1f}°C).")

        if problemas:
            for p in problemas:
                st.markdown(p)
        else:
            st.success("✅ Série climática sem anomalias detectadas nos critérios avaliados.")


render_footer()
