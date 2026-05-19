"""
brand.py — Identidade visual Monitora YieldGap
CSS global, header, footer e utilitários de marca
"""

import streamlit as st
import base64
import os


# ── Paleta de cores ──────────────────────────────────────────────────────────
COLORS = {
    "primary":      "#788c00",   # verde oliva principal
    "primary_dark": "#647800",   # hover / sidebar
    "primary_light":"#8ca000",   # badges / destaque
    "accent":       "#bcd44a",   # texto highlight
    "bg_main":      "#0e1117",   # fundo Streamlit padrão
    "bg_panel":     "#13161f",   # cards / painéis
    "bg_input":     "#1e2130",   # campos de entrada
    "border":       "#2a2e3e",   # bordas sutis
    "text_primary": "#f0f0f0",   # texto principal
    "text_muted":   "#6b7280",   # texto secundário
    "success":      "#22c55e",   # linha real / positivo
    "warning":      "#f59e0b",   # âmbar
    "danger":       "#ef4444",   # vermelho
    "chart_blue":   "#3b82f6",   # P70 atingível
    "chart_purple": "#a78bfa",   # eficiência
}

GLOBAL_CSS = f"""
<style>
/* ── Fontes ─────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&family=DM+Mono:wght@400;500&display=swap');

/* ── Root / variáveis ───────────────────────────────────────────────────── */
:root {{
    --c-primary:       {COLORS['primary']};
    --c-primary-dark:  {COLORS['primary_dark']};
    --c-primary-light: {COLORS['primary_light']};
    --c-accent:        {COLORS['accent']};
    --c-bg:            {COLORS['bg_main']};
    --c-panel:         {COLORS['bg_panel']};
    --c-input:         {COLORS['bg_input']};
    --c-border:        {COLORS['border']};
    --c-text:          {COLORS['text_primary']};
    --c-muted:         {COLORS['text_muted']};
    --c-success:       {COLORS['success']};
    --c-warning:       {COLORS['warning']};
    --c-danger:        {COLORS['danger']};
}}

/* ── Fundo e tipografia global ──────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif !important;
    background-color: var(--c-bg) !important;
    color: var(--c-text) !important;
}}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: #0b0e15 !important;
    border-right: 1px solid var(--c-border) !important;
}}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {{
    font-family: 'Rajdhani', sans-serif !important;
    color: var(--c-primary-light) !important;
    letter-spacing: 0.06em;
}}
[data-testid="stSidebarContent"] .stSelectbox label,
[data-testid="stSidebarContent"] .stNumberInput label,
[data-testid="stSidebarContent"] .stSlider label,
[data-testid="stSidebarContent"] .stDateInput label {{
    font-size: 0.8rem !important;
    color: var(--c-muted) !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-weight: 500;
}}

/* ── Inputs (sidebar e main) ────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stDateInput"] input {{
    background: var(--c-input) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: 8px !important;
    color: var(--c-text) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {{
    border-color: var(--c-primary) !important;
    box-shadow: 0 0 0 2px rgba(120,140,0,0.15) !important;
}}

/* ── Botão primário ─────────────────────────────────────────────────────── */
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stButton"] > button {{
    background: linear-gradient(135deg, var(--c-primary-dark), var(--c-primary-light)) !important;
    color: #0e1117 !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.08em !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.25rem !important;
    transition: opacity 0.2s, transform 0.1s !important;
}}
[data-testid="stButton"] > button:hover {{
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
}}

/* ── Headings (main area) ───────────────────────────────────────────────── */
h1, h2, h3 {{
    font-family: 'Rajdhani', sans-serif !important;
    letter-spacing: 0.04em;
}}
h1 {{ color: var(--c-primary-light) !important; font-size: 1.8rem !important; }}
h2 {{ color: var(--c-text) !important; font-size: 1.3rem !important; }}
h3 {{ color: var(--c-muted) !important; font-size: 1.05rem !important; }}

/* ── Metric cards ───────────────────────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: var(--c-panel) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--c-muted) !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--c-accent) !important;
}}

/* ── Expander ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: var(--c-panel) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: 10px !important;
}}
[data-testid="stExpander"] summary {{
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: var(--c-muted) !important;
}}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {{
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    color: var(--c-muted) !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: var(--c-primary-light) !important;
    border-bottom-color: var(--c-primary-light) !important;
}}

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--c-bg); }}
::-webkit-scrollbar-thumb {{ background: var(--c-border); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--c-primary-dark); }}

/* ── Ocultar elementos padrão Streamlit ─────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none; }}

/* ── Divisor personalizado ──────────────────────────────────────────────── */
hr {{
    border: none !important;
    border-top: 1px solid var(--c-border) !important;
    margin: 1.5rem 0 !important;
}}

/* ── Folium map container ───────────────────────────────────────────────── */
.stFoliumChart {{
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--c-border);
}}
</style>
"""


def _get_logo_b64() -> str:
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def inject_brand():
    """Injeta CSS global e deve ser chamado como primeira instrução do app.py."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_header(show_user: bool = True):
    """Header fixo com logo, nome do produto e info do usuário logado."""
    b64 = _get_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{b64}" style="width:36px;height:36px;border-radius:6px;" />' if b64 else ""

    user_info = ""
    if show_user and st.session_state.get("authenticated"):
        email = st.session_state.get("user_email", "")
        user_info = f"""
        <div style="display:flex;align-items:center;gap:0.6rem;">
            <div style="width:8px;height:8px;background:#22c55e;border-radius:50%;"></div>
            <span style="font-family:'DM Sans',sans-serif;font-size:0.78rem;
                         color:#6b7280;max-width:180px;overflow:hidden;
                         text-overflow:ellipsis;white-space:nowrap;">{email}</span>
        </div>
        """

    st.markdown(f"""
    <div style="
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 0 1rem;
        border-bottom: 1px solid #2a2e3e;
        margin-bottom: 1.5rem;
    ">
        <div style="display:flex;align-items:center;gap:0.75rem;">
            {logo_html}
            <div>
                <div style="font-family:'Rajdhani',sans-serif;font-size:1.35rem;
                            font-weight:700;color:#f0f0f0;line-height:1;
                            letter-spacing:0.03em;">
                    Monitora <span style="color:#8ca000;">YieldGap</span>
                </div>
                <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;
                            color:#4b5563;letter-spacing:0.1em;
                            text-transform:uppercase;margin-top:1px;">
                    Modelagem de Produtividade Agrícola
                </div>
            </div>
        </div>
        {user_info}
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    """Logo compacto para o topo da sidebar."""
    b64 = _get_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{b64}" style="width:44px;height:44px;border-radius:8px;display:block;margin:0 auto 0.5rem;" />' if b64 else ""

    st.markdown(f"""
    <div style="text-align:center;padding:0.5rem 0 1rem;">
        {logo_html}
        <div style="font-family:'Rajdhani',sans-serif;font-size:1.1rem;
                    font-weight:700;color:#f0f0f0;letter-spacing:0.04em;">
            Monitora <span style="color:#8ca000;">YieldGap</span>
        </div>
        <div style="font-family:'DM Sans',sans-serif;font-size:0.65rem;
                    color:#4b5563;letter-spacing:0.08em;text-transform:uppercase;
                    margin-top:2px;">Parâmetros</div>
    </div>
    <hr style="border-color:#2a2e3e;margin:0 0 1rem;" />
    """, unsafe_allow_html=True)


def render_footer():
    """Rodapé minimalista."""
    st.markdown("""
    <div style="
        text-align: center;
        padding: 2rem 0 1rem;
        border-top: 1px solid #2a2e3e;
        margin-top: 2rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.72rem;
        color: #374151;
        letter-spacing: 0.04em;
    ">
        Monitora YieldGap · Modelagem de Produtividade Agrícola ·
        <span style="color:#4b5563;">Dados climáticos: NASA POWER</span>
    </div>
    """, unsafe_allow_html=True)


def efficiency_card(year: int, real: float, p70: float) -> str:
    """Gera HTML de card de eficiência para um ano."""
    if p70 <= 0:
        return ""
    eff = (real / p70) * 100
    if eff >= 85:
        color, bg, label = "#22c55e", "rgba(34,197,94,0.08)", "Boa"
    elif eff >= 70:
        color, bg, label = "#f59e0b", "rgba(245,158,11,0.08)", "Moderada"
    else:
        color, bg, label = "#ef4444", "rgba(239,68,68,0.08)", "Baixa"

    return f"""
    <div style="
        background: {bg};
        border: 1px solid {color}33;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    ">
        <div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:1.1rem;
                        font-weight:700;color:{color};">{year}</div>
            <div style="font-family:'DM Sans',sans-serif;font-size:0.72rem;
                        color:#6b7280;text-transform:uppercase;
                        letter-spacing:0.06em;">{label}</div>
        </div>
        <div style="font-family:'Rajdhani',sans-serif;font-size:1.6rem;
                    font-weight:700;color:{color};">{eff:.0f}%</div>
    </div>
    """
