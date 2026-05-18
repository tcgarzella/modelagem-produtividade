"""
Sistema de Modelagem de Produtividade Agrícola
Interface Streamlit — integra NASA POWER + motor de cálculo
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from model_engine import (
    simular_janela, CULTURAS,
    calcular_cad, classificar_textura
)
from nasa_power import (
    buscar_serie_climatica, calcular_tmed_ref,
    anos_necessarios_para_janela, _gerar_serie_mock
)

# ─────────────────────────────────────────────
# PALETA E ESTILO
# ─────────────────────────────────────────────

DARK_BG      = "#0e1117"
PANEL_BG     = "#1a1d27"
GRID_COLOR   = "#2a2d3a"
TEXT_MAIN    = "#e8eaf0"
TEXT_SUB     = "#8b90a0"

C_ENVELOPE   = "rgba(59, 130, 246, 0.15)"   # azul translúcido — faixa atingível
C_ENVELOPE_L = "rgba(59, 130, 246, 0)"
C_ATING      = "#3b82f6"                     # azul — produtividade atingível
C_REAL       = "#22c55e"                     # verde — produtividade real
C_EFIC       = "#a78bfa"                     # lilás — eficiência agronômica
C_MELHOR     = "#38bdf8"                     # azul claro (referência)
C_PIOR       = "#f87171"                     # vermelho (referência)

st.set_page_config(
    page_title="Modelagem de Produtividade",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    .stApp {{ background-color: {DARK_BG}; }}
    .block-container {{ padding-top: 1.2rem; padding-bottom: 1rem; }}
    section[data-testid="stSidebar"] {{ background-color: {PANEL_BG}; }}
    .stMetric {{ background-color: {PANEL_BG}; border-radius: 8px; padding: 0.6rem 1rem; }}
    div[data-testid="metric-container"] {{
        background-color: {PANEL_BG};
        border-radius: 8px;
        padding: 0.6rem 1rem;
        border: 1px solid {GRID_COLOR};
    }}
    .efic-card {{
        text-align: center; padding: 14px 10px;
        border-radius: 8px;
        background-color: {PANEL_BG};
        border: 1px solid {GRID_COLOR};
        margin: 4px;
    }}
    .efic-val {{ font-size: 1.6rem; font-weight: 700; }}
    .efic-ano {{ font-size: 0.82rem; color: {TEXT_SUB}; margin-top: 2px; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Parâmetros")

    st.subheader("Cultura e local")
    cultura   = st.selectbox("Cultura", list(CULTURAS.keys()), index=2)
    latitude  = st.number_input("Latitude (°)",  value=-18.59, step=0.01, format="%.4f")
    longitude = st.number_input("Longitude (°)", value=-48.8891, step=0.01, format="%.4f",
                                help="Informe a longitude do ponto de interesse")

    st.subheader("Solo")
    argila = st.number_input("Argila (%)", min_value=1.0, max_value=80.0, value=13.8, step=0.1)
    z_cm   = st.number_input("Prof. radicular (cm)", min_value=10, max_value=200, value=30, step=5)
    cad    = calcular_cad(argila, z_cm)
    tex    = classificar_textura(argila)
    st.caption(f"CAD = **{cad:.0f} mm** — {tex}")

    st.subheader("Janela de plantio")
    ano_ref = date.today().year
    col1, col2 = st.columns(2)
    MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    with col1:
        mes_ini = st.selectbox("Início", range(1,13), index=9,
                               format_func=lambda m: MESES[m-1])
        dia_ini = st.number_input("Dia", 1, 31, 1, key="di")
    with col2:
        mes_fim = st.selectbox("Fim", range(1,13), index=10,
                               format_func=lambda m: MESES[m-1])
        dia_fim = st.number_input("Dia", 1, 31, 30, key="df")

    passo = st.radio("Passo (dias)", [5, 10], index=0, horizontal=True)

    if longitude is None:
        st.warning("⚠️ Informe a longitude antes de executar.")

    st.subheader("Produtividade real (opcional)")
    st.caption("Preencha para calcular eficiência agronômica")
    # TEMPORÁRIO — valores de validação do exemplo (remover após testes)
    _defaults = {2021: 3755, 2022: 4073, 2023: 4032, 2024: 3992, 2025: 3391}
    anos_hist = []
    for i in range(5):
        ano_i   = ano_ref - 5 + i
        default = _defaults.get(ano_i, 0)
        v = st.number_input(f"{ano_i} (kg/ha)", 0, 20000, default, 100, key=f"p{ano_i}")
        anos_hist.append({"ano": ano_i, "prod_real": v if v > 0 else None})

    st.subheader("Dados climáticos")
    usar_mock       = st.checkbox("Usar dados simulados (offline)", value=False)
    forcar_download = st.checkbox("Forçar nova busca (ignorar cache)", value=False)

    rodar = st.button("▶ Executar simulação", type="primary", use_container_width=True)


# ─────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────

def montar_datas_janela(ano, mes_ini, dia_ini, mes_fim, dia_fim):
    try:    d_ini = date(ano, mes_ini, dia_ini)
    except: d_ini = date(ano, mes_ini, 28)
    try:    d_fim = date(ano, mes_fim, dia_fim)
    except: d_fim = date(ano, mes_fim, 28)
    if d_fim < d_ini:
        d_fim = d_fim.replace(year=d_fim.year + 1)
    return d_ini, d_fim


def cor_efic(pct):
    if pct > 100:   return "#f59e0b"   # âmbar — acima do esperado
    elif pct >= 85: return "#22c55e"   # verde
    elif pct >= 70: return "#f59e0b"   # âmbar
    else:           return "#ef4444"   # vermelho


def _argilas_faixa(argila_central: float) -> list:
    """
    Gera vetor de teores de argila para estimar a faixa de incerteza da
    produtividade atingivel. Fatores 0.70 e 2.10 reproduzem o range
    P10-P90 observado entre talhoes de referencia (amplitude CAD ~20mm).
    """
    import numpy as np
    p10_arg = argila_central * 0.70
    p90_arg = argila_central * 2.10
    pontos  = np.linspace(p10_arg, p90_arg, 13)
    return [float(np.clip(v, 5.0, 75.0)) for v in pontos]


def executar_simulacao():
    import numpy as np

    ano_corrente = date.today().year
    ciclo        = CULTURAS[cultura]["ciclo"]
    anos_sim     = [r["ano"] for r in anos_hist]
    d_ini_ref    = date(ano_corrente, mes_ini, min(dia_ini, 28))
    anos_nasa    = anos_necessarios_para_janela(ano_corrente, d_ini_ref, ciclo, 5)
    anos_nasa    = sorted(set(anos_nasa + anos_sim + [a+1 for a in anos_sim]))

    with st.spinner("Buscando dados climáticos NASA POWER..."):
        if usar_mock:
            serie = _gerar_serie_mock(latitude, longitude, anos_nasa)
            st.info("⚠️ Dados sintéticos — modo offline ativo.")
        else:
            try:
                serie = buscar_serie_climatica(
                    lat=latitude, lon=longitude,
                    anos=anos_nasa, forcar_atualizacao=forcar_download,
                )
            except Exception as e:
                st.error(f"Erro NASA POWER: {e}")
                st.info("Ative 'Usar dados simulados' para continuar offline.")
                return None

    if not serie:
        st.error("Série climática vazia. Verifique coordenadas e conexão.")
        return None

    tmed_ref   = calcular_tmed_ref(serie)
    argilas_v  = _argilas_faixa(argila)
    resultados = []
    barra      = st.progress(0, text="Simulando...")

    for i, item in enumerate(anos_hist):
        ano       = item["ano"]
        prod_real = item["prod_real"]
        d_ini, d_fim = montar_datas_janela(ano, mes_ini, dia_ini, mes_fim, dia_fim)

        # Simulacao central — argila informada, P70 da janela de plantio
        res_central = simular_janela(
            cultura=cultura, ano=ano,
            data_inicio_janela=d_ini, data_fim_janela=d_fim,
            passo_dias=passo, serie_climatica=serie,
            latitude=latitude, argila_pct=argila,
            z_cm=z_cm, tmed_ref=tmed_ref,
        )
        p70_central = res_central.get("prod_ating_p70")

        # Faixa: combina variacao de data (janela) × variacao de argila
        # Coleta prod_atingivel_kgha de cada data simulada para cada argila
        vals_faixa = []

        # 1. Datas da janela com argila central (ja calculado — reutiliza)
        for r in res_central.get("resultados_detalhados", []):
            v = r.get("prod_atingivel_kgha", 0)
            if v > 0:
                vals_faixa.append(v)

        # 2. Argilas extremas (P10 e P90 do range textural) × todas as datas
        for arg_v in [argilas_v[0], argilas_v[-1]]:   # apenas extremos
            rv = simular_janela(
                cultura=cultura, ano=ano,
                data_inicio_janela=d_ini, data_fim_janela=d_fim,
                passo_dias=passo, serie_climatica=serie,
                latitude=latitude, argila_pct=arg_v,
                z_cm=z_cm, tmed_ref=tmed_ref,
            )
            for r in rv.get("resultados_detalhados", []):
                v = r.get("prod_atingivel_kgha", 0)
                if v > 0:
                    vals_faixa.append(v)

        if vals_faixa:
            p10_faixa = float(np.percentile(vals_faixa, 10))
            p90_faixa = float(np.percentile(vals_faixa, 90))
        else:
            p10_faixa = p70_central
            p90_faixa = p70_central

        efic = None
        if res_central.get("valido") and prod_real and p70_central and p70_central > 0:
            efic = prod_real / p70_central * 100

        resultados.append({
            "ano":        ano,
            "valido":     res_central.get("valido", False),
            "prod_p10":   p10_faixa,
            "prod_p70":   p70_central,
            "prod_p90":   p90_faixa,
            "prod_medio": p70_central,
            "prod_pct":   res_central.get("prod_ating_pct"),
            "deficit_mm": res_central.get("deficit_medio_mm"),
            "prod_real":  prod_real,
            "eficiencia": efic,
            "n_sim":      res_central.get("n_simulacoes", 0),
        })
        barra.progress((i+1)/len(anos_hist), text=f"Simulando {ano}...")

    barra.empty()
    return resultados, tmed_ref


# ─────────────────────────────────────────────
# GRÁFICO — estilo dark com envelope azul
# ─────────────────────────────────────────────

def construir_grafico(resultados, cultura):
    validos    = [r for r in resultados if r["valido"]]
    anos_v     = [r["ano"]        for r in validos]
    prod_p10   = [r["prod_p10"]   for r in validos]
    prod_p70   = [r["prod_p70"]   for r in validos]   # linha central
    prod_p90   = [r["prod_p90"]   for r in validos]
    prod_real  = [r["prod_real"]  for r in validos]
    eficiencia = [r["eficiencia"] for r in validos]

    tem_real = any(p is not None for p in prod_real)
    tem_efic = any(e is not None for e in eficiencia)

    fig = go.Figure()

    # ── Faixa atingível P10–P90 (variação textural) ──────────
    anos_env = [a for a, v in zip(anos_v, prod_p10) if v is not None]
    p10_env  = [v for v in prod_p10 if v is not None]
    p90_env  = [v90 for v10, v90 in zip(prod_p10, prod_p90) if v10 is not None]

    if anos_env:
        fig.add_trace(go.Scatter(
            x=anos_env + anos_env[::-1],
            y=p90_env + p10_env[::-1],
            fill="toself",
            fillcolor=C_ENVELOPE,
            line=dict(color="rgba(0,0,0,0)"),
            name="Faixa atingível",
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=anos_env, y=p90_env,
            mode="lines",
            line=dict(color=C_ATING, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=anos_env, y=p10_env,
            mode="lines",
            line=dict(color=C_ATING, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ))

    # ── Linha central P70 — curva suave (spline) ─────────────
    fig.add_trace(go.Scatter(
        x=anos_v, y=prod_p70,
        mode="lines+markers",
        name="Produtividade atingível (P70)",
        line=dict(color=C_ATING, width=2.5, shape="spline", smoothing=0.8),
        marker=dict(size=7, color=C_ATING,
                    line=dict(color=DARK_BG, width=1.5)),
        yaxis="y1",
        hovertemplate="<b>%{x}</b><br>Atingível P70: %{y:,.0f} kg/ha<extra></extra>",
    ))

    # ── Produtividade real ────────────────────────────────────
    if tem_real:
        anos_r = [a for a, p in zip(anos_v, prod_real) if p is not None]
        vals_r = [p for p in prod_real if p is not None]
        fig.add_trace(go.Scatter(
            x=anos_r, y=vals_r,
            mode="lines+markers",
            name="Produtividade obtida",
            line=dict(color=C_REAL, width=2.5, shape="spline", smoothing=0.8),
            marker=dict(size=8, color=C_REAL,
                        line=dict(color=DARK_BG, width=1.5)),
            yaxis="y1",
            hovertemplate="<b>%{x}</b><br>Obtida: %{y:,.0f} kg/ha<extra></extra>",
        ))

    # ── Eficiência agronômica (eixo secundário) ───────────────
    if tem_efic:
        anos_e = [a for a, e in zip(anos_v, eficiencia) if e is not None]
        vals_e = [e for e in eficiencia if e is not None]
        fig.add_trace(go.Scatter(
            x=anos_e, y=vals_e,
            mode="lines+markers+text",
            name="Eficiência agronômica (%)",
            line=dict(color=C_EFIC, width=2, dash="dot", shape="spline", smoothing=0.8),
            marker=dict(size=9, color=C_EFIC,
                        line=dict(color=DARK_BG, width=1.5)),
            text=[f"{v:.0f}%" for v in vals_e],
            textposition="top center",
            textfont=dict(size=11, color=C_EFIC, family="Arial"),
            yaxis="y2",
            hovertemplate="<b>%{x}</b><br>Eficiência: %{y:.1f}%<extra></extra>",
        ))

    # ── Layout dark ───────────────────────────────────────────
    todos_vals = [v for v in prod_p70 + (vals_r if tem_real else []) if v]
    y1_max = max(todos_vals) * 1.18 if todos_vals else 6000
    y1_min = 0

    efic_vals = [e for e in eficiencia if e is not None] if tem_efic else []
    y2_min = max(50, min(efic_vals) - 10) if efic_vals else 60
    y2_max = min(115, max(efic_vals) + 10) if efic_vals else 100

    axis_common = dict(
        gridcolor=GRID_COLOR,
        color=TEXT_SUB,
        tickfont=dict(color=TEXT_SUB, size=11),
        title_font=dict(color=TEXT_SUB, size=12),
        zerolinecolor=GRID_COLOR,
    )

    fig.update_layout(
        title=dict(
            text=f"Modelagem de Produtividade — {cultura}",
            font=dict(size=15, color=TEXT_MAIN, family="Arial"),
            x=0.01,
        ),
        paper_bgcolor=PANEL_BG,
        plot_bgcolor=PANEL_BG,
        height=500,
        margin=dict(l=70, r=70, t=55, b=90),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=PANEL_BG,
            bordercolor=GRID_COLOR,
            font=dict(color=TEXT_MAIN, size=12),
        ),
        xaxis=dict(
            title="Ano",
            tickmode="array",
            tickvals=anos_v,
            ticktext=[str(a) for a in anos_v],
            **axis_common,
        ),
        yaxis=dict(
            title="Produtividade (kg ha⁻¹)",
            range=[y1_min, y1_max],
            **axis_common,
        ),
        yaxis2=dict(
            title="Eficiência Agronômica (%)",
            overlaying="y", side="right",
            range=[y2_min, y2_max],
            tickformat=".0f",
            showgrid=False,
            **axis_common,
        ) if tem_efic else dict(visible=False),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.28,
            xanchor="left", x=0,
            font=dict(color=TEXT_MAIN, size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
    )

    return fig


# ─────────────────────────────────────────────
# TABELA
# ─────────────────────────────────────────────

def construir_tabela(resultados):
    rows = []
    for r in resultados:
        if not r["valido"]:
            rows.append({"Ano": r["ano"], "Status": "Dados insuficientes"})
            continue
        p10 = r.get("prod_p10")
        p90 = r.get("prod_p90")
        p70 = r.get("prod_p70") or r.get("prod_medio")
        faixa = (f"{p10:,.0f} — {p90:,.0f}"
                 if p10 is not None and p90 is not None else "—")
        row = {
            "Ano":                    r["ano"],
            "Prod. atingível P70 (kg/ha)": f"{p70:,.0f}" if p70 else "—",
            "Faixa P10–P90 (kg/ha)":  faixa,
            "% atingível":            f"{r['prod_pct']:.1f}%" if r.get("prod_pct") else "—",
            "Déficit (mm)":           f"{r['deficit_mm']:.0f}" if r.get("deficit_mm") is not None else "—",
            "Simulações":             r["n_sim"],
        }
        if r["prod_real"]:
            row["Prod. real (kg/ha)"] = f"{r['prod_real']:,.0f}"
        if r["eficiencia"] is not None:
            row["Eficiência (%)"] = f"{r['eficiencia']:.1f}%"
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# RENDERIZAÇÃO PRINCIPAL
# ─────────────────────────────────────────────

st.title("🌾 Modelagem de Produtividade Agrícola")
st.caption("Sistema de simulação de produtividade atingível por janela de plantio — dados NASA POWER")

if not rodar:
    st.info(
        "Configure os parâmetros no painel lateral e clique em **▶ Executar simulação**.\n\n"
        "O sistema simula a produtividade atingível para cada ano da janela histórica, "
        "considerando as variações climáticas dentro da janela de plantio definida."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cultura", cultura)
        st.metric("Ciclo (dias)", CULTURAS[cultura]["ciclo"])
    with col2:
        st.metric("CAD estimada", f"{calcular_cad(argila, z_cm):.0f} mm")
        st.metric("Textura", classificar_textura(argila))
    with col3:
        st.metric("Latitude", f"{latitude:.4f}°")
        st.metric("Passo de simulação", f"{passo} dias")

else:
    if longitude is None:
        st.error("⚠️ Longitude não informada. Preencha o campo no painel lateral antes de executar.")
        st.stop()

    resultado = executar_simulacao()

    if resultado:
        resultados, tmed_ref = resultado
        validos = [r for r in resultados if r["valido"]]

        # ── Métricas de topo ─────────────────────────────────
        if validos:
            media_prod   = sum(r["prod_medio"] for r in validos if r["prod_medio"]) / len(validos)
            media_deficit = sum(r["deficit_mm"] for r in validos if r["deficit_mm"] is not None) / len(validos)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Cultura", cultura)
            col2.metric("Prod. média atingível", f"{media_prod:,.0f} kg/ha")
            col3.metric("Déficit médio", f"{media_deficit:.0f} mm")
            col4.metric("Tmed referência", f"{tmed_ref:.1f}°C")

        st.divider()

        # ── Gráfico ───────────────────────────────────────────
        fig = construir_grafico(resultados, cultura)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ── Tabela ────────────────────────────────────────────
        st.subheader("Resultados por ano")
        df = construir_tabela(resultados)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Cards de eficiência ───────────────────────────────
        efics = [(r["ano"], r["eficiencia"])
                 for r in resultados if r.get("eficiencia") is not None]
        if efics:
            st.subheader("Eficiência agronômica")
            cols = st.columns(len(efics))
            for col, (ano, ef) in zip(cols, efics):
                cor = cor_efic(ef)
                col.markdown(
                    f"<div class='efic-card'>"
                    f"<div class='efic-val' style='color:{cor}'>{ef:.1f}%</div>"
                    f"<div class='efic-ano'>{ano}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── Parâmetros utilizados ─────────────────────────────
        with st.expander("Parâmetros da simulação"):
            p = CULTURAS[cultura]
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Cultura:** {cultura}")
            c1.write(f"**Tb inf/sup:** {p['Tb_inf']} / {p['Tb_sup']} °C")
            c1.write(f"**Ciclo:** {p['ciclo']} dias")
            c2.write(f"**Argila:** {argila}%")
            c2.write(f"**Prof. radicular:** {z_cm} cm")
            c2.write(f"**CAD:** {calcular_cad(argila, z_cm):.0f} mm")
            c3.write(f"**Latitude:** {latitude:.4f}°")
            c3.write(f"**Longitude:** {longitude:.4f}°")
            c3.write(f"**Tmed ref.:** {tmed_ref:.2f}°C")
