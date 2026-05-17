"""
Sistema de Modelagem de Produtividade Agrícola
Interface Streamlit — integra NASA POWER + motor de cálculo

Execução:
    streamlit run app.py
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
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Modelagem de Produtividade",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS mínimo para limpeza visual
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stMetric label { font-size: 0.85rem; color: #555; }
    div[data-testid="metric-container"] { background: #f8f9fa; border-radius: 6px; padding: 0.6rem 1rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR — PARÂMETROS DE ENTRADA
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Parâmetros")

    st.subheader("Cultura e local")
    cultura = st.selectbox("Cultura", list(CULTURAS.keys()), index=2)  # Soja default
    latitude  = st.number_input("Latitude (°)", value=-18.59, step=0.01, format="%.4f")
    longitude = st.number_input("Longitude (°)", value=-47.40, step=0.01, format="%.4f")

    st.subheader("Solo")
    argila = st.number_input("Argila (%)", min_value=1.0, max_value=80.0, value=13.8, step=0.1)
    z_cm   = st.number_input("Prof. radicular (cm)", min_value=10, max_value=200, value=30, step=5)

    cad = calcular_cad(argila, z_cm)
    tex = classificar_textura(argila)
    st.caption(f"CAD = **{cad:.0f} mm** — {tex}")

    st.subheader("Janela de plantio")
    ano_ref = date.today().year
    col1, col2 = st.columns(2)
    with col1:
        mes_ini = st.selectbox("Início (mês)", range(1, 13),
                               index=9, format_func=lambda m: date(2000, m, 1).strftime("%b"))
        dia_ini = st.number_input("Dia", min_value=1, max_value=31, value=1, key="dia_ini")
    with col2:
        mes_fim = st.selectbox("Fim (mês)", range(1, 13),
                               index=10, format_func=lambda m: date(2000, m, 1).strftime("%b"))
        dia_fim = st.number_input("Dia", min_value=1, max_value=31, value=30, key="dia_fim")

    passo = st.radio("Passo de simulação", [5, 10], index=0, horizontal=True)

    st.subheader("Produtividade real (opcional)")
    st.caption("Informe para calcular eficiência agronômica")

    anos_hist = []
    for i in range(5):
        ano_i = ano_ref - 5 + i
        v = st.number_input(f"{ano_i} (kg/ha)", min_value=0, max_value=20000,
                            value=0, step=100, key=f"prod_{ano_i}")
        anos_hist.append({"ano": ano_i, "prod_real": v if v > 0 else None})

    st.subheader("Dados climáticos")
    usar_mock = st.checkbox("Usar dados simulados (offline)", value=False,
                            help="Ativa série climática sintética para testes sem acesso à NASA POWER")
    forcar_download = st.checkbox("Forçar nova busca (ignorar cache)", value=False)

    rodar = st.button("▶ Executar simulação", type="primary", use_container_width=True)


# ─────────────────────────────────────────────
# LÓGICA PRINCIPAL
# ─────────────────────────────────────────────

def montar_datas_janela(ano_ref, mes_ini, dia_ini, mes_fim, dia_fim):
    """Constrói datas de referência para a janela de plantio."""
    try:
        d_ini = date(ano_ref, mes_ini, dia_ini)
    except ValueError:
        d_ini = date(ano_ref, mes_ini, 28)
    try:
        d_fim = date(ano_ref, mes_fim, dia_fim)
    except ValueError:
        d_fim = date(ano_ref, mes_fim, 28)
    if d_fim < d_ini:
        d_fim = d_fim.replace(year=d_fim.year + 1)
    return d_ini, d_fim


def cor_eficiencia(pct):
    """Mapeamento de cor para eficiência agronômica."""
    if pct >= 85:   return "#2ecc71"
    elif pct >= 70: return "#f39c12"
    else:            return "#e74c3c"


def executar_simulacao(
    cultura, latitude, longitude, argila, z_cm,
    mes_ini, dia_ini, mes_fim, dia_fim, passo,
    anos_hist, usar_mock, forcar_download
):
    ano_corrente = date.today().year
    anos_simular = [r["ano"] for r in anos_hist]
    ciclo = CULTURAS[cultura]["ciclo"]

    d_ini_ref = date(ano_corrente, mes_ini, min(dia_ini, 28))
    anos_nasa = anos_necessarios_para_janela(
        ano_corrente, d_ini_ref, ciclo, n_anos_historico=5
    )
    # Garante cobertura de todos os anos + o seguinte (ciclo pós-virada)
    anos_nasa = sorted(set(anos_nasa + anos_simular + [a + 1 for a in anos_simular]))

    # Busca série climática
    with st.spinner("Buscando dados climáticos NASA POWER..."):
        if usar_mock:
            serie = _gerar_serie_mock(latitude, longitude, anos_nasa)
            st.info("⚠️ Usando dados climáticos sintéticos (modo offline).")
        else:
            try:
                serie = buscar_serie_climatica(
                    lat=latitude, lon=longitude,
                    anos=anos_nasa,
                    forcar_atualizacao=forcar_download,
                )
            except Exception as e:
                st.error(f"Erro ao acessar NASA POWER: {e}")
                st.info("Tente ativar 'Usar dados simulados' para continuar offline.")
                return None

    if not serie:
        st.error("Série climática vazia. Verifique coordenadas e conexão.")
        return None

    tmed_ref = calcular_tmed_ref(serie)

    # Simula cada ano
    resultados_anos = []
    barra = st.progress(0, text="Simulando anos...")

    for i, item in enumerate(anos_hist):
        ano = item["ano"]
        prod_real = item["prod_real"]

        d_ini, d_fim = montar_datas_janela(ano, mes_ini, dia_ini, mes_fim, dia_fim)

        res = simular_janela(
            cultura=cultura, ano=ano,
            data_inicio_janela=d_ini,
            data_fim_janela=d_fim,
            passo_dias=passo,
            serie_climatica=serie,
            latitude=latitude,
            argila_pct=argila,
            z_cm=z_cm,
            tmed_ref=tmed_ref,
        )

        efic = None
        if res.get("valido") and prod_real and res["prod_ating_medio"] > 0:
            efic = prod_real / res["prod_ating_medio"] * 100

        resultados_anos.append({
            "ano": ano,
            "valido": res.get("valido", False),
            "prod_min": res.get("prod_ating_min"),
            "prod_max": res.get("prod_ating_max"),
            "prod_medio": res.get("prod_ating_medio"),
            "prod_pct": res.get("prod_ating_pct"),
            "deficit_mm": res.get("deficit_medio_mm"),
            "prod_real": prod_real,
            "eficiencia": efic,
            "n_sim": res.get("n_simulacoes", 0),
        })

        barra.progress((i + 1) / len(anos_hist), text=f"Simulando {ano}...")

    barra.empty()
    return resultados_anos, tmed_ref, calcular_cad(argila, z_cm)


# ─────────────────────────────────────────────
# VISUALIZAÇÃO
# ─────────────────────────────────────────────

def construir_grafico(resultados, cultura):
    """Monta o gráfico de linhas idêntico ao da planilha original."""

    anos_v     = [r["ano"]       for r in resultados if r["valido"]]
    prod_min   = [r["prod_min"]  for r in resultados if r["valido"]]
    prod_max   = [r["prod_max"]  for r in resultados if r["valido"]]
    prod_med   = [r["prod_medio"]for r in resultados if r["valido"]]
    prod_real  = [r["prod_real"] for r in resultados if r["valido"]]
    eficiencia = [r["eficiencia"]for r in resultados if r["valido"]]

    tem_real = any(p is not None for p in prod_real)
    tem_efic = any(e is not None for e in eficiencia)

    fig = go.Figure()

    # ── Faixa atingível (área sombreada) ─────────────────────
    fig.add_trace(go.Scatter(
        x=anos_v + anos_v[::-1],
        y=prod_max + prod_min[::-1],
        fill="toself",
        fillcolor="rgba(180,180,180,0.25)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Faixa atingível",
        hoverinfo="skip",
        showlegend=True,
    ))

    # ── Produtividade atingível (linha central) ───────────────
    fig.add_trace(go.Scatter(
        x=anos_v, y=prod_med,
        mode="lines+markers",
        name="Produtividade atingível",
        line=dict(color="#2980b9", width=2.5),
        marker=dict(size=6),
        yaxis="y1",
    ))

    # ── Produtividade real ────────────────────────────────────
    if tem_real:
        anos_r = [a for a, p in zip(anos_v, prod_real) if p is not None]
        vals_r = [p for p in prod_real if p is not None]
        fig.add_trace(go.Scatter(
            x=anos_r, y=vals_r,
            mode="lines+markers",
            name="Produtividade obtida",
            line=dict(color="#27ae60", width=2.5),
            marker=dict(size=7),
            yaxis="y1",
        ))

    # ── Eficiência agronômica (eixo secundário) ───────────────
    if tem_efic:
        anos_e = [a for a, e in zip(anos_v, eficiencia) if e is not None]
        vals_e = [e for e in eficiencia if e is not None]

        # Anotações de valor
        fig.add_trace(go.Scatter(
            x=anos_e, y=vals_e,
            mode="lines+markers+text",
            name="Eficiência agronômica (%)",
            line=dict(color="#8e44ad", width=2, dash="dot"),
            marker=dict(size=9, symbol="circle"),
            text=[f"{v:.0f}%" for v in vals_e],
            textposition="top center",
            textfont=dict(size=11, color="#8e44ad"),
            yaxis="y2",
        ))

    # ── Layout ────────────────────────────────────────────────
    y1_max = max(filter(None, prod_max + (prod_real if tem_real else [])), default=100)
    y1_max = y1_max * 1.15

    fig.update_layout(
        title=dict(
            text=f"Modelagem de Produtividade — {cultura}",
            font=dict(size=15),
            x=0.02,
        ),
        xaxis=dict(
            title="Ano",
            tickmode="array",
            tickvals=anos_v,
            ticktext=[str(a) for a in anos_v],
            gridcolor="#eee",
        ),
        yaxis=dict(
            title="Produtividade (kg ha⁻¹)",
            range=[0, y1_max],
            gridcolor="#eee",
        ),
        yaxis2=dict(
            title="Eficiência Agronômica (%)",
            overlaying="y",
            side="right",
            range=[60, 100],
            tickformat=".0f",
            showgrid=False,
        ) if tem_efic else {},
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.25,
            xanchor="left", x=0,
            font=dict(size=11),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=480,
        margin=dict(l=60, r=60, t=50, b=80),
        hovermode="x unified",
    )

    return fig


def construir_tabela(resultados):
    """Tabela de resultados por ano."""
    rows = []
    for r in resultados:
        if not r["valido"]:
            rows.append({"Ano": r["ano"], "Status": "Dados insuficientes"})
            continue
        row = {
            "Ano": r["ano"],
            "Prod. atingível (kg/ha)": f"{r['prod_medio']:,.0f}",
            "Faixa (kg/ha)": f"{r['prod_min']:,.0f} — {r['prod_max']:,.0f}",
            "% atingível": f"{r['prod_pct']:.1f}%",
            "Déficit (mm)": f"{r['deficit_mm']:.0f}",
            "Simulações": r["n_sim"],
        }
        if r["prod_real"]:
            row["Prod. real (kg/ha)"] = f"{r['prod_real']:,.0f}"
        if r["eficiencia"]:
            row["Eficiência (%)"] = f"{r['eficiencia']:.1f}%"
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# RENDERIZAÇÃO PRINCIPAL
# ─────────────────────────────────────────────

st.title("🌾 Modelagem de Produtividade Agrícola")
st.caption("Sistema de simulação de produtividade atingível por janela de plantio — dados NASA POWER")

if not rodar:
    # Estado inicial
    st.info(
        "Configure os parâmetros no painel lateral e clique em **▶ Executar simulação**.\n\n"
        "O sistema simula a produtividade atingível para cada ano da janela histórica, "
        "considerando as variações climáticas dentro da janela de plantio definida."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cultura selecionada", cultura)
        ciclo_c = CULTURAS[cultura]["ciclo"]
        st.metric("Ciclo (dias)", ciclo_c)
    with col2:
        st.metric("CAD estimada", f"{calcular_cad(argila, z_cm):.0f} mm")
        st.metric("Textura", classificar_textura(argila))
    with col3:
        st.metric("Latitude", f"{latitude:.4f}°")
        st.metric("Passo de simulação", f"{passo} dias")

else:
    # Executa simulação
    resultado = executar_simulacao(
        cultura=cultura,
        latitude=latitude, longitude=longitude,
        argila=argila, z_cm=z_cm,
        mes_ini=mes_ini, dia_ini=dia_ini,
        mes_fim=mes_fim, dia_fim=dia_fim,
        passo=passo,
        anos_hist=anos_hist,
        usar_mock=usar_mock,
        forcar_download=forcar_download,
    )

    if resultado:
        resultados, tmed_ref, cad_calc = resultado

        # ── Métricas de topo ─────────────────────────────────
        anos_validos = [r for r in resultados if r["valido"]]
        if anos_validos:
            ultimo = anos_validos[-1]
            media_prod = sum(r["prod_medio"] for r in anos_validos) / len(anos_validos)
            media_deficit = sum(r["deficit_mm"] for r in anos_validos) / len(anos_validos)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Cultura", cultura)
            col2.metric("Prod. média atingível", f"{media_prod:,.0f} kg/ha")
            col3.metric("Déficit médio", f"{media_deficit:.0f} mm")
            col4.metric("Tmed referência", f"{tmed_ref:.1f}°C")

        st.divider()

        # ── Gráfico principal ─────────────────────────────────
        fig = construir_grafico(resultados, cultura)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ── Tabela de resultados ──────────────────────────────
        st.subheader("Resultados por ano")
        df = construir_tabela(resultados)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Eficiência agronômica — cards ─────────────────────
        efics = [(r["ano"], r["eficiencia"]) for r in resultados if r.get("eficiencia")]
        if efics:
            st.subheader("Eficiência agronômica")
            cols = st.columns(len(efics))
            for col, (ano, ef) in zip(cols, efics):
                cor = cor_eficiencia(ef)
                col.markdown(
                    f"<div style='text-align:center; padding:10px; "
                    f"border-left:4px solid {cor}; background:#fafafa; border-radius:4px'>"
                    f"<b style='font-size:1.2rem; color:{cor}'>{ef:.1f}%</b><br>"
                    f"<span style='color:#666; font-size:0.85rem'>{ano}</span></div>",
                    unsafe_allow_html=True
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
            c2.write(f"**CAD:** {cad_calc:.0f} mm")
            c3.write(f"**Latitude:** {latitude:.4f}°")
            c3.write(f"**Longitude:** {longitude:.4f}°")
            c3.write(f"**Tmed ref.:** {tmed_ref:.2f}°C")
