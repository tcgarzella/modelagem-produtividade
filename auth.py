"""
auth.py — Módulo de autenticação Supabase para Monitora YieldGap
Gerencia login, cadastro, recuperação de senha e sessão via st.session_state
"""

import streamlit as st
from supabase import create_client, Client
import re


# ── Cliente Supabase ────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase_client() -> Client:
    url  = st.secrets["SUPABASE_URL"]
    key  = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _init_session():
    defaults = {
        "authenticated": False,
        "user_email": None,
        "user_id": None,
        "auth_view": "login",   # login | register | reset
        "auth_error": None,
        "auth_success": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Ações de autenticação ───────────────────────────────────────────────────

def login(email: str, password: str) -> bool:
    supabase = get_supabase_client()
    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["authenticated"] = True
        st.session_state["user_email"]    = resp.user.email
        st.session_state["user_id"]       = resp.user.id
        st.session_state["auth_error"]    = None
        return True
    except Exception as e:
        msg = str(e)
        if "Invalid login" in msg or "invalid_credentials" in msg:
            st.session_state["auth_error"] = "E-mail ou senha incorretos."
        elif "Email not confirmed" in msg:
            st.session_state["auth_error"] = "Confirme seu e-mail antes de fazer login."
        else:
            st.session_state["auth_error"] = f"Erro ao autenticar: {msg}"
        return False


def register(email: str, password: str, password2: str) -> bool:
    if not _valid_email(email):
        st.session_state["auth_error"] = "E-mail inválido."
        return False
    if len(password) < 8:
        st.session_state["auth_error"] = "Senha deve ter pelo menos 8 caracteres."
        return False
    if password != password2:
        st.session_state["auth_error"] = "As senhas não coincidem."
        return False

    supabase = get_supabase_client()
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.session_state["auth_error"]   = None
        st.session_state["auth_success"] = (
            "Cadastro realizado! Verifique seu e-mail para confirmar a conta."
        )
        st.session_state["auth_view"]    = "login"
        return True
    except Exception as e:
        msg = str(e)
        if "already registered" in msg or "User already registered" in msg:
            st.session_state["auth_error"] = "Este e-mail já está cadastrado."
        else:
            st.session_state["auth_error"] = f"Erro no cadastro: {msg}"
        return False


def reset_password(email: str) -> bool:
    if not _valid_email(email):
        st.session_state["auth_error"] = "E-mail inválido."
        return False
    supabase = get_supabase_client()
    try:
        supabase.auth.reset_password_email(email)
        st.session_state["auth_error"]   = None
        st.session_state["auth_success"] = (
            "E-mail de recuperação enviado. Verifique sua caixa de entrada."
        )
        st.session_state["auth_view"] = "login"
        return True
    except Exception as e:
        st.session_state["auth_error"] = f"Erro: {str(e)}"
        return False


def logout():
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for k in ["authenticated", "user_email", "user_id", "auth_error", "auth_success"]:
        st.session_state[k] = None if k != "authenticated" else False
    st.session_state["auth_view"] = "login"


# ── CSS da tela de autenticação ─────────────────────────────────────────────

AUTH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=DM+Sans:wght@300;400;500&display=swap');

/* Reset container */
.auth-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 80vh;
    padding: 2rem 1rem;
}

.auth-card {
    background: #13161f;
    border: 1px solid #2a2e3e;
    border-radius: 16px;
    padding: 2.5rem 2.5rem 2rem;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(120,140,0,0.08);
    position: relative;
    overflow: hidden;
}

.auth-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #647800, #8ca000, #647800);
}

.auth-logo {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    justify-content: center;
}

.auth-logo img {
    width: 48px;
    height: 48px;
    border-radius: 8px;
}

.auth-brand {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    color: #f0f0f0;
    letter-spacing: 0.02em;
    line-height: 1;
}

.auth-brand span {
    color: #8ca000;
}

.auth-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    color: #6b7280;
    text-align: center;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 2rem;
}

.auth-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #d1d5db;
    margin-bottom: 1.5rem;
    text-align: center;
    letter-spacing: 0.04em;
}

/* Override Streamlit inputs dentro do card */
.auth-card .stTextInput > div > div > input {
    background: #1e2130 !important;
    border: 1px solid #2a2e3e !important;
    border-radius: 8px !important;
    color: #f0f0f0 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 0.8rem !important;
    transition: border-color 0.2s;
}
.auth-card .stTextInput > div > div > input:focus {
    border-color: #788c00 !important;
    box-shadow: 0 0 0 2px rgba(120,140,0,0.15) !important;
}

.auth-card .stButton > button {
    background: linear-gradient(135deg, #647800, #8ca000) !important;
    color: #0e1117 !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.06em !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.65rem 1.5rem !important;
    width: 100% !important;
    transition: opacity 0.2s, transform 0.1s !important;
}
.auth-card .stButton > button:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
}

.auth-link-row {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    margin-top: 1.25rem;
}

.auth-divider {
    border: none;
    border-top: 1px solid #2a2e3e;
    margin: 1.5rem 0;
}

.auth-error {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
    color: #fca5a5;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    margin-bottom: 1rem;
}

.auth-success {
    background: rgba(120,140,0,0.12);
    border: 1px solid rgba(120,140,0,0.3);
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
    color: #bcd44a;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    margin-bottom: 1rem;
}
</style>
"""


# ── Renderização da tela de auth ────────────────────────────────────────────

def _logo_b64() -> str:
    """Converte o logo para base64 para embed inline."""
    import base64, os
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def render_auth_page():
    """Renderiza a tela de login/cadastro/reset. Retorna True se autenticado."""
    _init_session()

    if st.session_state["authenticated"]:
        return True

    st.markdown(AUTH_CSS, unsafe_allow_html=True)

    # Logo header
    b64 = _logo_b64()
    logo_html = f'<img src="data:image/png;base64,{b64}" />' if b64 else ""
    st.markdown(f"""
    <div style="text-align:center; margin-bottom: 2rem;">
        <div class="auth-logo" style="justify-content:center">
            {logo_html}
            <div>
                <div class="auth-brand">Monitora <span>YieldGap</span></div>
            </div>
        </div>
        <div class="auth-subtitle">Modelagem de Produtividade Agrícola</div>
    </div>
    """, unsafe_allow_html=True)

    view = st.session_state["auth_view"]

    # Mensagens de feedback
    if st.session_state.get("auth_error"):
        st.markdown(f'<div class="auth-error">⚠ {st.session_state["auth_error"]}</div>',
                    unsafe_allow_html=True)
    if st.session_state.get("auth_success"):
        st.markdown(f'<div class="auth-success">✓ {st.session_state["auth_success"]}</div>',
                    unsafe_allow_html=True)
        st.session_state["auth_success"] = None

    # ── LOGIN ────────────────────────────────────────────────────────────────
    if view == "login":
        st.markdown('<div class="auth-title">Acesse sua conta</div>', unsafe_allow_html=True)
        email    = st.text_input("E-mail", key="login_email", placeholder="seu@email.com")
        password = st.text_input("Senha", type="password", key="login_password",
                                 placeholder="••••••••")
        if st.button("Entrar", key="btn_login"):
            st.session_state["auth_error"] = None
            if email and password:
                login(email, password)
                st.rerun()
            else:
                st.session_state["auth_error"] = "Preencha e-mail e senha."
                st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Criar conta", key="goto_register"):
                st.session_state["auth_view"]    = "register"
                st.session_state["auth_error"]   = None
                st.session_state["auth_success"] = None
                st.rerun()
        with col2:
            if st.button("Esqueci a senha", key="goto_reset"):
                st.session_state["auth_view"]    = "reset"
                st.session_state["auth_error"]   = None
                st.session_state["auth_success"] = None
                st.rerun()

    # ── CADASTRO ─────────────────────────────────────────────────────────────
    elif view == "register":
        st.markdown('<div class="auth-title">Criar nova conta</div>', unsafe_allow_html=True)
        email  = st.text_input("E-mail", key="reg_email", placeholder="seu@email.com")
        p1     = st.text_input("Senha", type="password", key="reg_p1",
                               placeholder="mínimo 8 caracteres")
        p2     = st.text_input("Confirmar senha", type="password", key="reg_p2",
                               placeholder="repita a senha")
        if st.button("Cadastrar", key="btn_register"):
            st.session_state["auth_error"] = None
            register(email, p1, p2)
            st.rerun()

        if st.button("← Voltar ao login", key="goto_login_from_reg"):
            st.session_state["auth_view"]  = "login"
            st.session_state["auth_error"] = None
            st.rerun()

    # ── RESET DE SENHA ────────────────────────────────────────────────────────
    elif view == "reset":
        st.markdown('<div class="auth-title">Recuperar senha</div>', unsafe_allow_html=True)
        email = st.text_input("E-mail cadastrado", key="reset_email",
                              placeholder="seu@email.com")
        if st.button("Enviar link de recuperação", key="btn_reset"):
            st.session_state["auth_error"] = None
            reset_password(email)
            st.rerun()

        if st.button("← Voltar ao login", key="goto_login_from_reset"):
            st.session_state["auth_view"]  = "login"
            st.session_state["auth_error"] = None
            st.rerun()

    return False
