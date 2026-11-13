import streamlit as st
from sheets import (
    login_banker, get_clientes, get_contas, registrar_solicitacao,
    get_solicitacoes_abertas, solicitar_cancelamento,
)
from email_notif import enviar_email, enviar_email_cancelamento
try:
    from wire_ui import render_wire   # aba "Wire" (wire BTG US, clientes offshore) — código em wire_ui.py/sheets_wire.py/email_wire.py
except Exception as _erro_wire:       # se o módulo do wire falhar ao carregar, a TED continua abrindo normalmente
    _tipo_erro_wire = type(_erro_wire).__name__

    def render_wire(_banker):
        st.error(f"Wire indisponível no momento ({_tipo_erro_wire}). A TED continua funcionando normalmente.")
from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
CUTOFF_HOUR = 16

# ══ AVISO NO TOPO DA TELA DE TEDs ═════════════════════════════════════════
# Hoje: SEM aviso (AVISO_TED = None). Para LIGAR um aviso: descomente o bloco "AVISO_TED = {...}" abaixo,
# ajuste o texto e comente a linha "AVISO_TED = None".  Para DESLIGAR: faça o contrário.
# tipo: "info" (azul) | "warn" (amarelo) | "error" (vermelho)
# "email_indisponivel": True faz a tela de sucesso deixar de prometer e-mail de confirmação (use só se for esse o caso).
# AVISO_TED = {
#     "tipo":   "warn",
#     "titulo": "Atenção — e-mails de TED indisponíveis",
#     "email_indisponivel": True,
#     "texto":  ("As TEDs continuam chegando normalmente no nosso pipeline e serão processadas por nós. "
#                "Porém, devido ao problema global da Microsoft, NÃO serão enviados os e-mails de "
#                "confirmação nem de comprovante da TED por enquanto."),
# }
AVISO_TED = None   # ← sem aviso no momento
EMAIL_CONFIRMACAO_INDISPONIVEL = bool(AVISO_TED and AVISO_TED.get("email_indisponivel"))

# Ícone da aba do navegador: emblema "S" da SWM MFO (PNG embutido). Se a imagem falhar, a página abre sem ícone.
FAVICON_B64 = "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"
try:
    import base64 as _b64, io as _io
    from PIL import Image as _Image
    _icone = _Image.open(_io.BytesIO(_b64.b64decode(FAVICON_B64)))
except Exception:
    _icone = None

st.set_page_config(page_title="TED & Wire — SWM MFO", page_icon=_icone, layout="wide")

_TEMA_CLARO  = ("--bg:#F3F4F6; --surface:#FFFFFF; --surface2:#F7F8FA; --line:#E1E4E8; --line2:#CFD4DA; --text:#102134; --muted:#404751; "
                "--subtle:#5F6B7A; --accent:#896F3D; --pbg:#102134; --pfg:#FFFFFF; --phover:#1A293F; --sandl:#F4F1EB; --aline:#E3DCCB; "
                "--infobg:#EFF6FF; --infoline:#3E5A7A; --errbg:#FEF2F2; --errline:#B91C1C; --sand:#C8BEAA; color-scheme:light;")
_TEMA_ESCURO = ("--bg:#0D1620; --surface:#142132; --surface2:#1A2B40; --line:#263A52; --line2:#3A5473; --text:#E8ECF1; --muted:#B7C2CF; "
                "--subtle:#93A3B6; --accent:#D2B06E; --pbg:#C8BEAA; --pfg:#102134; --phover:#DDD4C3; --sandl:#1F2A38; --aline:#3A4A5E; "
                "--infobg:#14283D; --infoline:#6F93BD; --errbg:#2E1A1E; --errline:#E07A7A; --sand:#C8BEAA; color-scheme:dark;")

# Tema: por padrão segue o modo claro/escuro do sistema (prefers-color-scheme); o seletor "Tema" do cabeçalho força um dos dois.
# Todas as cores de texto são definidas aqui (não herdadas do tema do Streamlit) para o texto ficar legível em qualquer combinação.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&family=Rubik:wght@400;500;600&display=swap');
:root { __CLARO__ }
@media (prefers-color-scheme: dark) { :root { __ESCURO__ } }
html, body, .stApp, [data-testid="stAppViewContainer"], .stMarkdown, .stTextInput, .stSelectbox, .stButton, label, p, li, span, input, textarea { font-family: 'Montserrat', system-ui, sans-serif; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--bg); color: var(--text); }
#MainMenu, footer, header { visibility: hidden }
.stApp::before { content:""; position:fixed; top:0; left:0; right:0; height:3px; z-index:1000; background:linear-gradient(to right, var(--accent) 0 72px, var(--pbg) 72px); }
.block-container { max-width: 1080px; padding-top: 1.6rem; padding-bottom: 3rem; }
h1, h2, h3, h4, [data-testid="stHeading"], [data-testid="stHeading"] * { font-family: 'Rubik', sans-serif !important; color: var(--text) !important; font-weight: 500 !important; letter-spacing: 0; }
h3, [data-testid="stHeading"] h3 { font-size: 20px !important; margin-top: 4px; }
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] em { color: var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--subtle) !important; opacity: 1 !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { font-weight: 600; font-size: 12px; color: var(--muted) !important; }
[data-testid="stRadio"] label p, [data-testid="stCheckbox"] label p, [data-testid="stCheckbox"] p { color: var(--text); }
[data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"] { background: var(--surface) !important; border: 1px dashed var(--line2) !important; }
[data-testid="stFileUploader"] *, [data-testid="stFileUploaderDropzone"] * { color: var(--muted) !important; }
.stButton > button, .stFormSubmitButton > button { font-family:'Rubik',sans-serif; font-weight:500; border-radius:6px; border:1px solid var(--text); background:var(--surface); color:var(--text); padding:.55rem 1.2rem; }
.stButton > button p, .stFormSubmitButton > button p { color: var(--text); }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--accent); background:var(--surface2); }
button[kind="primary"], button[kind="primaryFormSubmit"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] { background:var(--pbg) !important; color:var(--pfg) !important; border:1px solid var(--pbg) !important; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover, button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background:var(--phover) !important; border-color:var(--phover) !important; }
button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primaryFormSubmit"] p { color:var(--pfg) !important; }
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] { border-radius:6px !important; border-color:var(--line2) !important; background:var(--surface) !important; }
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within { border-color:var(--text) !important; box-shadow:0 0 0 3px rgba(128,128,128,.18); }
input, textarea { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; background: transparent !important; caret-color: var(--text); }
input::placeholder, textarea::placeholder { color: var(--subtle) !important; -webkit-text-fill-color: var(--subtle) !important; opacity: 1; }
div[data-baseweb="select"] span, div[data-baseweb="select"] div { color: var(--text); }
div[data-baseweb="select"] svg, div[data-baseweb="input"] svg { fill: var(--muted); color: var(--muted); }
div[data-baseweb="popover"] > div, div[data-baseweb="popover"] ul, div[data-baseweb="menu"] { background: var(--surface) !important; border: 1px solid var(--line2); }
div[data-baseweb="popover"] li, div[data-baseweb="popover"] li * { color: var(--text) !important; background: transparent !important; }
div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] li[aria-selected="true"] { background: var(--surface2) !important; }
div[data-baseweb="calendar"], div[data-baseweb="calendar"] * { background: var(--surface) !important; color: var(--text) !important; }
div[data-baseweb="calendar"] button[aria-selected="true"], div[data-baseweb="calendar"] [aria-selected="true"] { background: var(--pbg) !important; color: var(--pfg) !important; }
div[data-testid="stForm"] { border-color: var(--line); }
.stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-family:'Rubik',sans-serif; font-weight:500; color:var(--muted) !important; padding:8px 16px; background: transparent !important; }
.stTabs [data-baseweb="tab"] p { color: var(--muted); }
.stTabs [aria-selected="true"], .stTabs [aria-selected="true"] p { color:var(--text) !important; }
.stTabs [data-baseweb="tab-highlight"] { background:var(--accent); height:2px; }
.stTabs [data-baseweb="tab-border"] { background:transparent; }
.st-key-menu_principal div[role="radiogroup"] { display:inline-flex; gap:0; border:1px solid var(--line2); border-radius:8px; padding:3px; background:var(--surface); }
.st-key-menu_principal label { margin:0; padding:7px 28px; border-radius:6px; cursor:pointer; }
.st-key-menu_principal label > div:first-child { display:none; }
.st-key-menu_principal label p { font-family:'Rubik',sans-serif; font-weight:500; font-size:13px; margin:0; color:var(--muted); }
.st-key-menu_principal label:has(input:checked) { background:var(--pbg); }
.st-key-menu_principal label:has(input:checked) p { color:var(--pfg); }
div[data-testid="stAlert"] { border-radius:6px; background:var(--surface) !important; border:1px solid var(--line2); border-left:4px solid var(--accent); }
div[data-testid="stAlert"] *, div[data-testid="stAlert"] p { color: var(--text) !important; }
.topo-user { display:flex; align-items:center; gap:18px; }
.topo-logo { height:46px; width:auto; }
.logo-escuro { display:none; }
@media (prefers-color-scheme: dark) { .logo-claro { display:none; } .logo-escuro { display:inline; } }
.topo-nome { font-size:13px; color:var(--muted); border-left:1px solid var(--line2); padding-left:18px; line-height:1.3; }
.topo-nome b { color:var(--text); font-family:'Rubik',sans-serif; font-weight:500; display:block; }
.eyebrow { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:600; }
.login-h1 { font-family:'Rubik',sans-serif; font-weight:500; font-size:28px; color:var(--text); margin:6px 0 6px 0; line-height:1.25; }
.login-sub { color:var(--muted); font-size:13px; margin:0; }
.aviso { display:flex; gap:14px; background:var(--sandl); border:1px solid var(--aline); border-left:4px solid var(--accent); border-radius:6px; padding:14px 18px; margin:14px 0 20px 0; }
.aviso .ic { flex:0 0 22px; height:22px; border-radius:50%; border:1.5px solid var(--accent); color:var(--accent); font:600 13px 'Rubik',sans-serif; display:flex; align-items:center; justify-content:center; margin-top:1px; }
.aviso strong { display:block; font:500 14px 'Rubik',sans-serif; color:var(--text); margin-bottom:2px; }
.aviso span { font-size:13px; color:var(--muted); }
.aviso-info { background:var(--infobg); border-color:var(--line2); border-left-color:var(--infoline); }
.aviso-error { background:var(--errbg); border-color:var(--line2); border-left-color:var(--errline); }
.nota { font-size:12px; color:var(--muted); background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:10px 12px; margin:4px 0 14px 0; }
.nota b { color:var(--text); }
.btg-box, .dest-box { border-radius:8px; padding:14px 18px; margin:10px 0 16px 0; display:flex; align-items:center; justify-content:space-between; min-height:96px; background:var(--surface); border:1px solid var(--line); }
.btg-box  { border-left:3px solid var(--accent); }
.dest-box { border-left:3px solid var(--text); }
.btg-label, .dest-label { font-size:11px; font-weight:600; color:var(--subtle); text-transform:uppercase; letter-spacing:.1em; }
.btg-numero { font:500 24px 'Rubik',sans-serif; color:var(--text); margin-top:3px; }
.btg-nome { font-size:14px; color:var(--muted); margin-top:4px; }
.dest-banco { font:500 20px 'Rubik',sans-serif; color:var(--text); margin-top:3px; }
.dest-detalhe { font-size:13px; color:var(--muted); margin-top:4px; line-height:1.55; }
.box-content { display:flex; flex-direction:column; justify-content:center; }
.bank-logo { height:64px; width:auto; max-width:100px; object-fit:contain; border-radius:6px; flex-shrink:0; margin-left:16px; background:#fff; padding:4px; }
.col-h { font:600 12px 'Rubik',sans-serif; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); display:flex; justify-content:space-between; padding-bottom:10px; border-bottom:2px solid var(--text); margin-bottom:12px; }
.col-h.c2 { border-bottom-color:var(--accent); }
.col-h.c3 { border-bottom-color:var(--subtle); }
.col-h span { background:var(--pbg); color:var(--pfg); border-radius:10px; padding:0 8px; font-size:11px; line-height:18px; }
.sol-card { border-radius:8px; padding:14px 16px; margin:8px 0; background:var(--surface); border:1px solid var(--line); }
.sol-cliente { font:500 15px 'Rubik',sans-serif; color:var(--text); }
.sol-detalhe { font-size:13px; color:var(--muted); margin-top:2px; }
.sol-data    { font-size:12px; color:var(--subtle); margin-top:4px; }
.sol-aviso   { font-size:12px; color:var(--accent); margin-top:6px; font-weight:600; }
.w-aviso { background:var(--sandl) !important; border:1px solid var(--aline) !important; border-left:4px solid var(--accent) !important; border-radius:6px !important; color:var(--muted) !important; font-size:13px !important; }
.w-aviso b, .w-aviso strong { color:var(--text) !important; }
.w-card { background:var(--surface) !important; border:1px solid var(--line) !important; border-radius:8px !important; color:var(--text) !important; }
.w-aviso-cut { color:var(--accent) !important; }
</style>
""".replace("__CLARO__", _TEMA_CLARO).replace("__ESCURO__", _TEMA_ESCURO), unsafe_allow_html=True)

BANCOS = [
    ("001", "Banco do Brasil"),
    ("033", "Santander"),
    ("077", "Inter"),
    ("104", "Caixa Econômica Federal"),
    ("140", "NuInvest"),
    ("197", "Stone"),
    ("208", "BTG Pactual"),
    ("212", "Banco Original"),
    ("237", "Bradesco"),
    ("260", "Nubank"),
    ("290", "PagBank"),
    ("310", "Vortx"),
    ("323", "Mercado Pago"),
    ("336", "C6 Bank"),
    ("341", "Itaú"),
    ("348", "XP Investimentos"),
    ("380", "PicPay"),
    ("422", "Safra"),
    ("623", "Pan"),
    ("633", "Rendimento"),
    ("655", "Votorantim (BV)"),
    ("707", "Daycoval"),
    ("745", "Citibank"),
    ("748", "Sicredi"),
    ("756", "Sicoob"),
    ("___", "Outro"),
]
BANCO_OPTS = [""] + [f"{nome}  ({cod})" for cod, nome in BANCOS]

LOGOS = {
    "SWM": "swmgestao.com.br",
    "001": "bb.com.br",
    "033": "santander.com.br",
    "104": "caixa.gov.br",
    "140": "nubank.com.br",
    "197": "stone.com.br",
    "208": "btgpactual.com.br",
    "212": "original.com.br",
    "237": "bradesco.com.br",
    "260": "nubank.com.br",
    "290": "pagbank.com.br",
    "310": "vortx.com.br",
    "323": "mercadopago.com.br",
    "336": "c6bank.com.br",
    "341": "itau.com.br",
    "348": "xpi.com.br",
    "380": "picpay.com",
    "422": "safra.com.br",
    "623": "bancopan.com.br",
    "633": "rendimento.com.br",
    "655": "bv.com.br",
    "707": "daycoval.com.br",
    "745": "citibank.com.br",
    "748": "sicredi.com.br",
    "756": "sicoob.com.br",
    "077": "inter.co",
    "084": "sisprime.com.br",
    "102": "xpi.com.br",
    "136": "unicred.com.br",
    "301": "bpp.com.br",
    "318": "bancobmg.com.br",
    "508": "avenue.us",
    "712": "ouribank.com.br",
}

def _logo_img(codigo):
    token = st.secrets.get("LOGO_TOKEN", "")
    s     = str(codigo).strip()
    val   = LOGOS.get(s) or LOGOS.get(s.zfill(3), "")
    if not val:
        return ""
    url = val if val.startswith("http") else f"https://img.logo.dev/{val}?token={token}&retina=true"
    return f'<img src="{url}" class="bank-logo" onerror="this.style.display=\'none\'">'

# ── SESSION STATE ─────────────────────────────────────────────────────────
for k, v in [
    ("logado", False), ("banker_id", None), ("banker_nome", None), ("banker_email", ""),
    ("step", "cliente"), ("clientes", None),
    ("cliente_sel", None), ("conta_sel", None), ("conta_nova", False), ("sol", None), ("sol_mock", None),
    ("sol_conf", None), ("cancel_pending_id", None), ("sol_pendente", None), ("erro_envio", None),
    ("sol_email_falhou", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

LOGO_SWM_B64 = "PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA4NDEuODkgNDM4LjgxIj4gPGRlZnM+IDxzdHlsZT4gLmNscy0xIHsgZmlsbDogIzEwMjEzNDsgfSA8L3N0eWxlPiA8L2RlZnM+IDxnPiA8cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0yMTMuNTgsMjk0LjI4Yy0yMS42MiwwLTQxLjY2LTkuMzItNTAuMTktMjguMDNsLTExLjIzLDEwLjA1YzkuMTEsMjAuMDQsMzMuNCwzMS43OSw2MC4zNiwzMS43OSwzNS40OSwwLDU4LjcyLTIxLjI1LDU4LjcyLTQ5Ljk1LDAtMjMuNS0xNS4xOC0zOC45OS00MS42My00NC44NWwtMjIuNzEtNS4wN2MtMjAuNTYtNC41NS0zMC43LTE0LjctMzAuNy0zMi4wNiwwLTIwLjAxLDE0LjY3LTM1LjI1LDM5LjQ3LTM1LjI1LDE4LjcsMCwzNi4wNyw4LjI5LDQzLjgxLDI1LjM4bDExLjQ4LTEwLjE0Yy04Ljg0LTE4LjIyLTMwLjczLTI5LjEyLTU0LjY1LTI5LjEyLTMzLjY0LDAtNTYuNiwyMS44OS01Ni42LDQ5Ljk1LS4wNiwyMy40MSwxMy41NCwzOC4yNiw0MS4wNSw0NC42NmwyMi40MSw1LjM0YzIyLjIsNS4zNCwzMS41MiwxNS45MSwzMS41MiwzMS43OSwwLDIwLjU2LTE0Ljk0LDM1LjQ5LTQxLjExLDM1LjQ5Ii8+IDxwb2x5Z29uIGNsYXNzPSJjbHMtMSIgcG9pbnRzPSI3MDEuOTQgMjQ5LjcxIDYzMS40NCAxMjkuNTMgNjE2Ljc0IDEyOS41MyA2MTYuNzQgMzA1Ljc2IDYzMS45OCAzMDUuNzYgNjMxLjk4IDE1OS4xNyA2OTYuODcgMjY5LjQ4IDcwNS45NSAyNjkuNDggNzcwLjgzIDE1OS4xNyA3NzAuODMgMzA1Ljc2IDc4Ni4wNCAzMDUuNzYgNzg2LjA0IDEyOS41MyA3NzIuMTcgMTI5LjUzIDcwMS45NCAyNDkuNzEiLz4gPHBhdGggY2xhc3M9ImNscy0xIiBkPSJNNTA4LjUzLDI4NS40MmwtNTUuNTMtMTU1Ljg4aC0xNi44MmwyMC4wMSw1Ni4wOC00MC4wNSwxMDAuNjgtNDYuMzMtMTMwLjU2aDBDMzM3LjMsNjYuNCwyMzguNTMsMjAuMzMsMTQ5LjE5LDUyLjgzLDU5Ljg2LDg1LjMzLDEzLjc4LDE4NC4xLDQ2LjI5LDI3My40M2MzMi41LDg5LjM0LDEzMS4yNywxMzUuNDEsMjIwLjYsMTAyLjkxLDI5LjI5LTEwLjY2LDU1LjE1LTI5LjA3LDc0Ljc5LTUzLjI3aC04LjA1Yy01OS44Nyw2OS4zOS0xNjQuNjUsNzcuMS0yMzQuMDMsMTcuMjMtNjkuMzktNTkuODctNzcuMS0xNjQuNjUtMTcuMjMtMjM0LjAzLDU5Ljg3LTY5LjM5LDE2NC42NS03Ny4xLDIzNC4wMy0xNy4yMyw1LjMyLDQuNTksMTAuMzUsOS41MiwxNS4wNSwxNC43NSw3LjE0LDcuNjUsMTIuNjMsMjUuODQsMTIuNjMsMjUuODRoMGwxNy44Miw1MC4yOCw0NC42LDEyNS44NWgxNi41NWw0MC4zMi0xMDEuNzIsMzYuNDQsMTAxLjcyaDE2LjU1bDYyLjQ5LTE3Ni4xMWgtMTYuM2wtNTQuMDIsMTU1Ljc2Wk0zNDQuNTcsMTI5LjQ3Ii8+IDwvZz4gPGc+IDxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTY2Ny4wNSwzODUuODFsLS4wNy0zOS4wOC0xOS4zOSwzMi41N2gtMy41M2wtMTkuMzktMzIuMzR2MzguODVoLTcuMzZ2LTUzLjY0aDYuMjhsMjIuMzcsMzcuNywyMi4wNy0zNy43aDYuMjlsLjA3LDUzLjY0aC03LjM2WiIvPiA8cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik02OTguMTUsMzM4LjgzdjE4LjdoMjYuOXY2LjU5aC0yNi45djIxLjY5aC03LjY2di01My42NGgzNy44NnY2LjY3aC0zMC4xOVoiLz4gPHBhdGggY2xhc3M9ImNscy0xIiBkPSJNNzM0LjE1LDM1OC45OWMwLTE1LjcxLDEyLjExLTI3LjQzLDI4LjU4LTI3LjQzczI4LjQzLDExLjY1LDI4LjQzLDI3LjQzLTEyLjExLDI3LjQzLTI4LjQzLDI3LjQzLTI4LjU4LTExLjcyLTI4LjU4LTI3LjQzWk03ODMuNSwzNTguOTljMC0xMS44OC04Ljg5LTIwLjYxLTIwLjc3LTIwLjYxcy0yMC45Miw4Ljc0LTIwLjkyLDIwLjYxLDguODksMjAuNjEsMjAuOTIsMjAuNjEsMjAuNzctOC43NCwyMC43Ny0yMC42MVoiLz4gPC9nPiA8L3N2Zz4="   # logo oficial SWM MFO (SVG azul) embutido — o app é um arquivo só

LOGO_SWM_BRANCO_B64 = "PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA4NDEuODkgNDM4LjgxIj4gPGRlZnM+IDxzdHlsZT4gLmNscy0xIHsgZmlsbDogI2ZmZmZmZjsgfSA8L3N0eWxlPiA8L2RlZnM+IDxnPiA8cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0yMTMuNTgsMjk0LjI4Yy0yMS42MiwwLTQxLjY2LTkuMzItNTAuMTktMjguMDNsLTExLjIzLDEwLjA1YzkuMTEsMjAuMDQsMzMuNCwzMS43OSw2MC4zNiwzMS43OSwzNS40OSwwLDU4LjcyLTIxLjI1LDU4LjcyLTQ5Ljk1LDAtMjMuNS0xNS4xOC0zOC45OS00MS42My00NC44NWwtMjIuNzEtNS4wN2MtMjAuNTYtNC41NS0zMC43LTE0LjctMzAuNy0zMi4wNiwwLTIwLjAxLDE0LjY3LTM1LjI1LDM5LjQ3LTM1LjI1LDE4LjcsMCwzNi4wNyw4LjI5LDQzLjgxLDI1LjM4bDExLjQ4LTEwLjE0Yy04Ljg0LTE4LjIyLTMwLjczLTI5LjEyLTU0LjY1LTI5LjEyLTMzLjY0LDAtNTYuNiwyMS44OS01Ni42LDQ5Ljk1LS4wNiwyMy40MSwxMy41NCwzOC4yNiw0MS4wNSw0NC42NmwyMi40MSw1LjM0YzIyLjIsNS4zNCwzMS41MiwxNS45MSwzMS41MiwzMS43OSwwLDIwLjU2LTE0Ljk0LDM1LjQ5LTQxLjExLDM1LjQ5Ii8+IDxwb2x5Z29uIGNsYXNzPSJjbHMtMSIgcG9pbnRzPSI3MDEuOTQgMjQ5LjcxIDYzMS40NCAxMjkuNTMgNjE2Ljc0IDEyOS41MyA2MTYuNzQgMzA1Ljc2IDYzMS45OCAzMDUuNzYgNjMxLjk4IDE1OS4xNyA2OTYuODcgMjY5LjQ4IDcwNS45NSAyNjkuNDggNzcwLjgzIDE1OS4xNyA3NzAuODMgMzA1Ljc2IDc4Ni4wNCAzMDUuNzYgNzg2LjA0IDEyOS41MyA3NzIuMTcgMTI5LjUzIDcwMS45NCAyNDkuNzEiLz4gPHBhdGggY2xhc3M9ImNscy0xIiBkPSJNNTA4LjUzLDI4NS40MmwtNTUuNTMtMTU1Ljg4aC0xNi44MmwyMC4wMSw1Ni4wOC00MC4wNSwxMDAuNjgtNDYuMzMtMTMwLjU2aDBDMzM3LjMsNjYuNCwyMzguNTMsMjAuMzMsMTQ5LjE5LDUyLjgzLDU5Ljg2LDg1LjMzLDEzLjc4LDE4NC4xLDQ2LjI5LDI3My40M2MzMi41LDg5LjM0LDEzMS4yNywxMzUuNDEsMjIwLjYsMTAyLjkxLDI5LjI5LTEwLjY2LDU1LjE1LTI5LjA3LDc0Ljc5LTUzLjI3aC04LjA1Yy01OS44Nyw2OS4zOS0xNjQuNjUsNzcuMS0yMzQuMDMsMTcuMjMtNjkuMzktNTkuODctNzcuMS0xNjQuNjUtMTcuMjMtMjM0LjAzLDU5Ljg3LTY5LjM5LDE2NC42NS03Ny4xLDIzNC4wMy0xNy4yMyw1LjMyLDQuNTksMTAuMzUsOS41MiwxNS4wNSwxNC43NSw3LjE0LDcuNjUsMTIuNjMsMjUuODQsMTIuNjMsMjUuODRoMGwxNy44Miw1MC4yOCw0NC42LDEyNS44NWgxNi41NWw0MC4zMi0xMDEuNzIsMzYuNDQsMTAxLjcyaDE2LjU1bDYyLjQ5LTE3Ni4xMWgtMTYuM2wtNTQuMDIsMTU1Ljc2Wk0zNDQuNTcsMTI5LjQ3Ii8+IDwvZz4gPGc+IDxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTY2Ny4wNSwzODUuODFsLS4wNy0zOS4wOC0xOS4zOSwzMi41N2gtMy41M2wtMTkuMzktMzIuMzR2MzguODVoLTcuMzZ2LTUzLjY0aDYuMjhsMjIuMzcsMzcuNywyMi4wNy0zNy43aDYuMjlsLjA3LDUzLjY0aC03LjM2WiIvPiA8cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik02OTguMTUsMzM4LjgzdjE4LjdoMjYuOXY2LjU5aC0yNi45djIxLjY5aC03LjY2di01My42NGgzNy44NnY2LjY3aC0zMC4xOVoiLz4gPHBhdGggY2xhc3M9ImNscy0xIiBkPSJNNzM0LjE1LDM1OC45OWMwLTE1LjcxLDEyLjExLTI3LjQzLDI4LjU4LTI3LjQzczI4LjQzLDExLjY1LDI4LjQzLDI3LjQzLTEyLjExLDI3LjQzLTI4LjQzLDI3LjQzLTI4LjU4LTExLjcyLTI4LjU4LTI3LjQzWk03ODMuNSwzNTguOTljMC0xMS44OC04Ljg5LTIwLjYxLTIwLjc3LTIwLjYxcy0yMC45Miw4Ljc0LTIwLjkyLDIwLjYxLDguODksMjAuNjEsMjAuOTIsMjAuNjEsMjAuNzctOC43NCwyMC43Ny0yMC42MVoiLz4gPC9nPiA8L3N2Zz4="   # mesma logo em branco, para fundo azul

def _logo_swm(classe="topo-logo", branco=False):
    b64 = LOGO_SWM_BRANCO_B64 if branco else LOGO_SWM_B64
    return f'<img class="{classe}" alt="SWM MFO" src="data:image/svg+xml;base64,{b64}">'

def _logo_topo():
    """Logo do cabeçalho: azul no tema claro, branco no escuro (troca por CSS: sistema ou seletor Tema)."""
    return (f'<span class="logo-claro">{_logo_swm()}</span><span class="logo-escuro">{_logo_swm(branco=True)}</span>')

def fmt_money(val):
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_valor(s):
    s = s.strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        # formato BR: . = milhar, , = decimal
        s = s.replace(".", "").replace(",", ".")
    else:
        dot = s.rfind(".")
        if dot != -1 and len(s) - dot - 1 <= 2:
            # ponto em posição decimal (ex: 1500.50) — preserva como decimal
            inteiro = s[:dot].replace(".", "")
            s = inteiro + "." + s[dot + 1:]
        else:
            # ponto em posição de milhar (ex: 1.500) — remove
            s = s.replace(".", "")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None

def proximo_dia_util(d):
    """d: date ou datetime. Pula sábado/domingo — não considera feriados."""
    prox = d + timedelta(days=1)
    while prox.weekday() >= 5:  # 5=sábado, 6=domingo
        prox += timedelta(days=1)
    return prox

def calcular_prazo_cancelamento(data_solicitacao_str, data_pagamento_str):
    # Regra (definida 03/08/2026): se a liquidação é no mesmo dia da solicitação,
    # janela curta (1h ou até as 16h, o que vier primeiro; depois das 16h vira
    # 12h do próximo dia útil). Se a liquidação é num dia futuro (qualquer
    # distância), o prazo é sempre 12h do próprio dia de liquidação — mais simples
    # que calcular "dia anterior" e não precisa de ajuste de fim de semana, porque
    # já é uma data futura fixa.
    dt = datetime.strptime(data_solicitacao_str, "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
    dl = datetime.strptime(data_pagamento_str, "%Y-%m-%d").date()

    if dl == dt.date():
        if dt.time() < dtime(CUTOFF_HOUR, 0):
            cutoff_hoje = dt.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0)
            return min(dt + timedelta(hours=1), cutoff_hoje)
        prox_util = proximo_dia_util(dt.date())
        return datetime.combine(prox_util, dtime(12, 0), tzinfo=TZ)

    return datetime.combine(dl, dtime(12, 0), tzinfo=TZ)

def clear_nc():
    for k in ["nc_banco","nc_b_cod","nc_b_nome","nc_agencia","nc_tipo",
              "nc_conta","nc_digito","nc_titular","nc_cpf","nc_titularidade","radio_contas"]:
        st.session_state.pop(k, None)

def btg_box(conta_btg, nome):
    logo = _logo_img("SWM")
    st.markdown(f"""
    <div class="btg-box">
        <div class="box-content">
            <div class="btg-label">Conta BTG de origem</div>
            <div class="btg-numero">{conta_btg}</div>
            <div class="btg-nome">{nome}</div>
        </div>
        {logo}
    </div>
    """, unsafe_allow_html=True)

def dest_box(c):
    logo = _logo_img(c.get("banco_codigo", ""))
    st.markdown(f"""
    <div class="dest-box">
        <div class="box-content">
            <div class="dest-label">Conta de destino</div>
            <div class="dest-banco">{c['banco_nome']}</div>
            <div class="dest-detalhe">
                Ag. {c['agencia']} &nbsp;·&nbsp; Cc. {c['conta']}-{c['digito']} ({c['tipo']})<br>
                Titular: {c['titular']}
            </div>
        </div>
        {logo}
    </div>
    """, unsafe_allow_html=True)

def solicitacao_card(s):
    sid = s["id"]
    dt_solicitacao = datetime.strptime(s["data"], "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
    dt_pagamento    = datetime.strptime(s["data_pagamento"], "%Y-%m-%d").date()
    pagamento_fmt   = dt_pagamento.strftime("%d/%m/%Y")

    # Aviso só faz sentido quando o pagamento foi pedido pro MESMO dia da
    # solicitação e o pedido veio depois do corte — se já foi agendado pra
    # uma data futura, a data escolhida já reflete isso, sem ambiguidade.
    aviso_prazo = ""
    if dt_pagamento == dt_solicitacao.date() and dt_solicitacao.time() >= dtime(CUTOFF_HOUR, 0):
        prox_dia = proximo_dia_util(dt_solicitacao.date()).strftime("%d/%m")
        aviso_prazo = (
            f'<div class="sol-aviso">⚠️ Solicitado após as {CUTOFF_HOUR}h — '
            f'na prática será executado no próximo dia útil ({prox_dia})</div>'
        )

    # Montado como string única, sem linha em branco no meio — um placeholder
    # vazio (aviso_prazo == "") deixaria uma linha só com espaços dentro do
    # bloco HTML, e o parser de markdown do Streamlit interpreta isso como
    # fim do bloco, fazendo o resto vazar como texto puro em vez de HTML.
    partes_card = [
        f'<div class="sol-cliente">{s["cliente_nome"]} — R$ {fmt_money(s["valor"])}</div>',
        f'<div class="sol-detalhe">{s["banco_nome"]} · {s["titular"]}</div>',
        f'<div class="sol-data">Solicitado em: {s["data"]}</div>',
        f'<div class="sol-data">Pagamento previsto: {pagamento_fmt}</div>',
    ]
    if aviso_prazo:
        partes_card.append(aviso_prazo)
    partes_card.append(f'<div class="sol-data">Pedido por: {s["banker_nome"]}</div>')

    st.markdown(f'<div class="sol-card">{"".join(partes_card)}</div>', unsafe_allow_html=True)

    if s["cancelamento_solicitado"]:
        st.caption(
            f"🚫 Cancelamento solicitado por {s['banker_solicitacao_cancelamento']} "
            f"em {s['cancelamento_solicitado']}"
        )
        return

    # Cancelamento só cabe com a TED ainda "pendente" — uma vez que passou
    # pra "em processo" ou "em aprovação cliente", a operação já está em
    # curso e cancelar deixa de ser uma decisão que o banker toma sozinho.
    if s["status"] != "pendente":
        return

    prazo = calcular_prazo_cancelamento(s["data"], s["data_pagamento"])
    agora = datetime.now(TZ)

    if agora >= prazo:
        st.caption("Prazo de cancelamento encerrado")
        return

    if st.session_state.get("cancel_pending_id") == sid:
        c1, c2 = st.columns(2)
        if c1.button("Sim, cancelar", key=f"yes_{sid}", type="primary", use_container_width=True):
            solicitar_cancelamento(sid, st.session_state.banker_nome)
            enviar_email_cancelamento({
                "banker_nome":       st.session_state.banker_nome,
                "cliente_nome":      s["cliente_nome"],
                "valor_fmt":         fmt_money(s["valor"]),
                "data_pagamento":    s["data_pagamento"],
                "id":                sid,
                "hora_cancelamento": datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"),
            })
            st.session_state.cancel_pending_id = None
            st.rerun()
        if c2.button("Voltar", key=f"no_{sid}", use_container_width=True):
            st.session_state.cancel_pending_id = None
            st.rerun()
    else:
        restante_min = int((prazo - agora).total_seconds() // 60)
        st.caption(f"⏳ {restante_min} min pra solicitar cancelamento")
        if st.button("Solicitar cancelamento", key=f"cancel_{sid}", use_container_width=True):
            st.session_state.cancel_pending_id = sid
            st.rerun()

CANCELAMENTO_VISIVEL_HORAS = 24

def _parse_cancelamento_solicitado(v):
    """O Sheets às vezes detecta "26/08/2026 14:30:00" (escrito como texto
    por solicitar_cancelamento) como célula de Data de verdade — quando isso
    acontece, get_all_records(UNFORMATTED_VALUE) devolve um número serial
    (dias desde 30/12/1899), não a string esperada. Achado real 26/08:
    quebrava o board inteiro (ValueError) na janela entre pedir o
    cancelamento e o ted_to_notion aplicar o status "cancelada"."""
    if isinstance(v, (int, float)):
        return datetime(1899, 12, 30) + timedelta(days=float(v))
    return datetime.strptime(str(v), "%d/%m/%Y %H:%M:%S")


def cancelamento_expirado(s):
    # Depois de solicitar o cancelamento, o card some do board em 24h mesmo se
    # a operação ainda não tiver mudado o status — evita ficar pendurado pra
    # sempre esperando ação manual. Não apaga nada, só some da visão do board.
    if not s["cancelamento_solicitado"]:
        return False
    try:
        dt_pedido = _parse_cancelamento_solicitado(s["cancelamento_solicitado"]).replace(tzinfo=TZ)
    except (ValueError, TypeError):
        return False  # não deu pra interpretar -> mais seguro manter o card visível que derrubar o board
    return datetime.now(TZ) - dt_pedido > timedelta(hours=CANCELAMENTO_VISIVEL_HORAS)

def render_board():
    st.subheader("Solicitações em aberto — meus clientes")
    abertas = [s for s in get_solicitacoes_abertas(st.session_state.banker_id) if not cancelamento_expirado(s)]
    pendentes        = [s for s in abertas if s["status"] == "pendente"]
    em_processo       = [s for s in abertas if s["status"] == "em processo"]
    em_aprov_cliente  = [s for s in abertas if s["status"] == "em aprovação cliente"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="col-h">Pendente <span>{len(pendentes)}</span></div>', unsafe_allow_html=True)
        if not pendentes:
            st.caption("Nenhuma solicitação pendente.")
        for s in pendentes:
            solicitacao_card(s)
    with col2:
        st.markdown(f'<div class="col-h c2">Em processo <span>{len(em_processo)}</span></div>', unsafe_allow_html=True)
        if not em_processo:
            st.caption("Nenhuma solicitação em processo.")
        for s in em_processo:
            solicitacao_card(s)
    with col3:
        st.markdown(f'<div class="col-h c3">Em aprovação do cliente <span>{len(em_aprov_cliente)}</span></div>', unsafe_allow_html=True)
        if not em_aprov_cliente:
            st.caption("Nenhuma solicitação em aprovação do cliente.")
        for s in em_aprov_cliente:
            solicitacao_card(s)

# ── LOGIN ─────────────────────────────────────────────────────────────────
if not st.session_state.logado:
    # Login dividido (mockup): painel azul fixo à esquerda + formulário à direita.
    st.markdown("""
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background:var(--surface); }
.block-container { max-width:100% !important; padding:0 !important; }
.lg-panel { position:fixed; left:0; top:0; bottom:0; width:52vw; background:#102134; color:#fff; padding:56px; display:flex; flex-direction:column; justify-content:space-between; z-index:1001; }
.lg-panel img { height:96px; width:auto; align-self:flex-start; }
.lg-panel::after { content:""; position:absolute; left:56px; right:56px; bottom:112px; height:1px; background:#896F3D; }
.lg-h { font-family:'Rubik',sans-serif; font-weight:400; font-size:30px; line-height:1.25; max-width:420px; color:#fff !important; }
.lg-p { color:#C8BEAA !important; font-size:13px; margin:14px 0 0 0; max-width:400px; }
.lg-foot { color:#9fb0c4 !important; font-size:11px; letter-spacing:.04em; }
div[data-testid="stColumn"]:nth-of-type(2), div[data-testid="column"]:nth-of-type(2) { padding:20vh 8vw 0 6vw; }
div[data-testid="stForm"] { border:none; padding:0; background:transparent; }
@media (max-width: 860px) { .lg-panel { display:none; } div[data-testid="stColumn"]:nth-of-type(2), div[data-testid="column"]:nth-of-type(2) { padding:8vh 6vw 0 6vw; } }
</style>
""", unsafe_allow_html=True)
    st.markdown(
        '<div class="lg-panel">' + _logo_swm("", branco=True) +
        '<div><div class="lg-h">Solicitação de TED e Wire</div>'
        '<div class="lg-p">Plataforma interna da gestão para bankers e RI com controle e rastreabilidade.</div></div>'
        '<div class="lg-foot">SWM MFO · Acesso restrito a colaboradores autorizados</div></div>',
        unsafe_allow_html=True,
    )
    _esq, _dir = st.columns([52, 48])
    with _dir:
        st.markdown(
            '<div class="eyebrow">Acesso restrito</div>'
            '<div class="login-h1">Entrar</div>'
            '<div class="login-sub" style="margin-bottom:22px">Use seu usuário e senha da plataforma.</div>',
            unsafe_allow_html=True,
        )
        with st.form("login"):
            usuario = st.text_input("Usuário")
            senha   = st.text_input("Senha", type="password")
            entrar  = st.form_submit_button("Entrar", use_container_width=True, type="primary")
        if entrar:
            if not usuario or not senha:
                st.error("Preencha usuário e senha.")
            else:
                res = login_banker(usuario.strip(), senha.strip())
                if res["ok"]:
                    st.session_state.logado      = True
                    st.session_state.banker_id   = res["id"]
                    st.session_state.banker_nome = res["nome"]
                    st.session_state.banker_email = res.get("email", "")
                    st.rerun()
                else:
                    st.error(res["erro"])
    st.stop()

# ── HEADER ────────────────────────────────────────────────────────────────
c1, ctema, c2 = st.columns([5, 1.3, 1])
c1.markdown(f'<div class="topo-user">{_logo_topo()}<div class="topo-nome"><b>{st.session_state.banker_nome}</b>TED &amp; Wire</div></div>', unsafe_allow_html=True)
import sheets as _sheets_mod
c1.caption("versão 21/10 · filtro offshore: " + ("ativo" if getattr(_sheets_mod, "FILTRO_OFF_ATIVO", False) else "INATIVO (sheets.py desatualizado)"))
_tema = ctema.selectbox("Tema", ["Automático", "Claro", "Escuro"], key="tema", label_visibility="collapsed")
if _tema == "Claro":
    st.markdown("<style>:root{" + _TEMA_CLARO + "} .logo-escuro{display:none !important} .logo-claro{display:inline !important}</style>", unsafe_allow_html=True)
elif _tema == "Escuro":
    st.markdown("<style>:root{" + _TEMA_ESCURO + "} .logo-claro{display:none !important} .logo-escuro{display:inline !important}</style>", unsafe_allow_html=True)
if c2.button("Sair"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
st.write("")

# Menu principal: TEDs | Wires. É um seletor (não st.tabs) de propósito: com abas o Streamlit executa as duas ao mesmo tempo, e o wire leria a
# planilha a cada clique da TED (estourou a cota de leitura do Google em 21/10). Escolhida "Wires", só o wire roda.
modo = st.radio("Menu", ["TED", "Wire"], horizontal=True, label_visibility="collapsed", key="menu_principal")
if modo == "Wire":
    try:
        render_wire({"id": st.session_state.banker_id, "nome": st.session_state.banker_nome})
    except Exception as e:
        st.error(f"Wire indisponível no momento ({type(e).__name__}). A TED continua funcionando normalmente.")
    st.stop()

if AVISO_TED:   # configurado no topo do arquivo (AVISO_TED)
    import html as _html
    _tipo_aviso = AVISO_TED.get("tipo") if AVISO_TED.get("tipo") in ("info", "error") else "warn"
    st.markdown(
        f'<div class="aviso aviso-{_tipo_aviso}"><div class="ic">!</div><div>'
        f'<strong>{_html.escape(AVISO_TED["titulo"])}</strong><span>{_html.escape(AVISO_TED["texto"])}</span></div></div>',
        unsafe_allow_html=True,
    )

tab1, tab2 = st.tabs(["Nova solicitação", "Minhas solicitações"])

# NOTA: o bloco "with tab2" vem antes do "with tab1" no código-fonte de propósito.
# O wizard (tab1) usa st.stop() em pontos intermediários do fluxo, e st.stop()
# interrompe a execução do script inteiro — qualquer coisa escrita depois dele
# no arquivo não roda naquele ciclo. Escrevendo tab2 primeiro, o board sempre
# termina de renderizar antes de qualquer st.stop() do wizard poder cortá-lo.
# A ordem visual das abas na tela é definida pelos labels em st.tabs([...]),
# não pela ordem dos blocos "with" aqui embaixo.
with tab2:
    render_board()

with tab1:
    step = st.session_state.step

    # ── SUCESSO ───────────────────────────────────────────────────────────────
    if step == "sucesso":
        d = st.session_state.sol
        mock = st.session_state.sol_mock
        if mock:
            st.success("✅ Solicitação registrada! (modo teste — email não enviado)")
            with st.expander("📧 Email que seria enviado", expanded=True):
                st.caption(f"Assunto: {mock['assunto']}")
                st.code(mock["corpo"], language=None)
        elif st.session_state.sol_email_falhou:
            # Linha já gravada na planilha: a sync TED→Notion avisa o time sozinha.
            # Só o e-mail automático deste app falhou — não voltar ao formulário.
            st.success("✅ Solicitação registrada.")
            st.warning("⚠️ O e-mail automático para a equipe de operações não saiu. Avise o time de Middle.")
        else:
            st.success("✅ Solicitação enviada! A equipe de operações foi notificada por e-mail.")
        if EMAIL_CONFIRMACAO_INDISPONIVEL:
            st.info("O e-mail de confirmação e o comprovante estão temporariamente indisponíveis. "
                    "A solicitação foi registrada e será processada pela equipe. Não refaça a solicitação.")
        else:
            st.info("Caso o e-mail de confirmação não chegue em até 5 minutos, entre em contato com o time de Middle. "
                    "Não refaça a solicitação.")
        if d["conta_nova"]:
            st.warning("⚠️ Conta nova — a equipe irá cadastrar após execução.")

        # Confirmação com tabela pro solicitante + time agora sai do lado do
        # ted_to_notion_novo.py (notificar_nova_ted), assim que a sync processar
        # esta solicitação — não é mais síncrona com o submit, por isso sem
        # feedback de status aqui (ver comentário em "enviando" acima).
        if not EMAIL_CONFIRMACAO_INDISPONIVEL:
            st.info("📧 A confirmação por e-mail (pra você e pro seu time) chega em instantes, assim que a sincronização processar.")

        st.markdown("**Resumo da solicitação**")
        for label, val in [
            ("Cliente",            d["cliente_nome"]),
            ("Conta BTG (origem)", d["conta_btg_origem"]),
            ("Banco destino",      d["banco_nome"]),
            ("Agência",            d["agencia"]),
            ("Conta",              f"{d['conta_destino']}-{d['digito']} ({d['tipo']})"),
            ("Titular",            d["titular"]),
            ("CPF/CNPJ",           d["cpf_cnpj_titular"]),
            ("Valor",              f"R$ {fmt_money(float(d['valor']))}"),
            ("Data pagamento",     d["data_br"]),
        ]:
            l, r = st.columns([1, 2])
            l.caption(label)
            r.write(f"**{val}**")
        st.write("")
        if st.button("Nova operação", use_container_width=True, type="primary"):
            st.session_state.step        = "cliente"
            st.session_state.cliente_sel = None
            st.session_state.conta_sel   = None
            st.session_state.conta_nova  = False
            st.session_state.sol         = None
            st.session_state.sol_mock    = None
            st.session_state.sol_conf    = None
            st.session_state.sol_pendente = None
            st.session_state.sol_email_falhou = None
            st.session_state.pop("valor_ted", None)
            clear_nc()
            st.rerun()

    # ── STEP 1: CLIENTE ───────────────────────────────────────────────────────
    elif step == "cliente":
        st.subheader("1 · Selecione o cliente")
        if st.session_state.clientes is None:
            with st.spinner("Carregando clientes..."):
                st.session_state.clientes = get_clientes(st.session_state.banker_id)

        clientes = st.session_state.clientes
        if not clientes:
            st.warning("Nenhum cliente cadastrado para o seu usuário. Fale com o administrador.")
            st.stop()

        opts = ["Selecione..."] + [f"{c['nome']}  —  {c['conta_btg']}" for c in clientes]
        sel  = st.selectbox("", opts, label_visibility="collapsed")

        if sel != "Selecione...":
            cli = clientes[opts.index(sel) - 1]
            btg_box(cli["conta_btg"], cli["nome"])
            if st.button("Próxima etapa →", use_container_width=True, type="primary"):
                st.session_state.cliente_sel = cli
                st.session_state.step        = "destino"
                st.rerun()

    # ── STEP 2: DESTINO ───────────────────────────────────────────────────────
    elif step == "destino":
        cli = st.session_state.cliente_sel
        if st.button("← Trocar cliente"):
            st.session_state.step        = "cliente"
            st.session_state.cliente_sel = None
            clear_nc()
            st.rerun()

        btg_box(cli["conta_btg"], cli["nome"])
        st.subheader("2 · Conta de destino")

        contas  = get_contas(cli["id"])
        escolha = None

        if contas:
            opts_c  = [
                f"{c['banco_nome']}  ·  Ag. {c['agencia']}  ·  Cc. {c['conta']}-{c['digito']}  ·  {c['titular']}"
                for c in contas
            ] + ["+ Informar nova conta"]
            escolha = st.radio("", opts_c, key="radio_contas", label_visibility="collapsed")

            if escolha != "+ Informar nova conta":
                idx = opts_c.index(escolha)
                dest_box(contas[idx])
                if st.button("Usar esta conta →", use_container_width=True, type="primary"):
                    st.session_state.conta_sel  = contas[idx]
                    st.session_state.conta_nova = False
                    st.session_state.step       = "transferencia"
                    st.rerun()
        else:
            st.info("Nenhuma conta cadastrada para este cliente. Preencha os dados abaixo.")

        # Formulário nova conta
        if not contas or escolha == "+ Informar nova conta":
            st.markdown("---")
            st.markdown("**Dados da nova conta**")
            banco_sel = st.selectbox("Banco", BANCO_OPTS, key="nc_banco")

            if banco_sel and not banco_sel.startswith("Outro"):
                parts   = banco_sel.rsplit("(", 1)
                preview_cod  = parts[1].rstrip(")").strip()
                preview_nome = parts[0].strip()
                logo = _logo_img(preview_cod)
                if logo:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0 12px;">'
                        f'{logo}<span style="font-weight:600;color:inherit;">{preview_nome}</span></div>',
                        unsafe_allow_html=True
                    )

            b_cod_custom, b_nome_custom = "", ""
            if banco_sel and banco_sel.startswith("Outro"):
                c1, c2 = st.columns(2)
                b_cod_custom  = c1.text_input("Código do banco", key="nc_b_cod",  placeholder="ex: 341")
                b_nome_custom = c2.text_input("Nome do banco",   key="nc_b_nome", placeholder="ex: Itaú")

            c1, c2 = st.columns(2)
            agencia = c1.text_input("Agência",        key="nc_agencia", placeholder="ex: 0001")
            tipo    = c2.selectbox("Tipo de conta",   ["Corrente", "Poupança"], key="nc_tipo")

            c1, c2 = st.columns([3, 1])
            conta_n = c1.text_input("Conta",  key="nc_conta",  placeholder="ex: 12345")
            digito  = c2.text_input("Dígito", key="nc_digito", placeholder="0", max_chars=2)

            titularidade = st.radio(
                "Titularidade", ["Mesma titularidade", "Terceiro"],
                key="nc_titularidade", horizontal=True
            )

            titular, cpf_cnpj = "", ""
            if titularidade == "Terceiro":
                titular  = st.text_input("Nome do titular",        key="nc_titular")
                cpf_cnpj = st.text_input("CPF / CNPJ do titular", key="nc_cpf", placeholder="000.000.000-00")

            if st.button("Usar esta conta →", key="btn_nc", use_container_width=True, type="primary"):
                erros = []
                if not banco_sel:             erros.append("banco")
                if not agencia.strip():       erros.append("agência")
                if not conta_n.strip():       erros.append("conta")
                if not digito.strip():        erros.append("dígito")
                if titularidade == "Terceiro":
                    if not titular.strip():   erros.append("titular")
                    if not cpf_cnpj.strip():  erros.append("CPF/CNPJ")
                if banco_sel.startswith("Outro"):
                    if not b_cod_custom.strip():  erros.append("código do banco")
                    if not b_nome_custom.strip(): erros.append("nome do banco")
                if erros:
                    st.error(f"Preencha: {', '.join(erros)}.")
                else:
                    if banco_sel.startswith("Outro"):
                        b_cod, b_nome = b_cod_custom.strip(), b_nome_custom.strip()
                    else:
                        parts  = banco_sel.rsplit("(", 1)
                        b_nome = parts[0].strip()
                        b_cod  = parts[1].rstrip(")").strip()
                    titular_val  = titular.strip()  if titularidade == "Terceiro" else "Mesma titularidade"
                    cpf_cnpj_val = cpf_cnpj.strip() if titularidade == "Terceiro" else "—"
                    st.session_state.conta_sel = {
                        "banco_codigo":     b_cod,           "banco_nome":       b_nome,
                        "agencia":          agencia.strip(),  "conta":            conta_n.strip(),
                        "digito":           digito.strip(),   "tipo":             tipo,
                        "titular":          titular_val,      "cpf_cnpj_titular": cpf_cnpj_val,
                    }
                    st.session_state.conta_nova = True
                    st.session_state.step       = "transferencia"
                    st.rerun()

    # ── STEP 3: TRANSFERÊNCIA ─────────────────────────────────────────────────
    elif step == "transferencia":
        cli        = st.session_state.cliente_sel
        c          = st.session_state.conta_sel
        conta_nova = st.session_state.conta_nova

        if st.button("← Trocar conta destino"):
            st.session_state.step       = "destino"
            st.session_state.conta_sel  = None
            st.session_state.conta_nova = False
            st.rerun()

        btg_box(cli["conta_btg"], cli["nome"])
        dest_box(c)
        if conta_nova:
            st.warning("⚠️ Conta nova — será cadastrada pela equipe após execução.")

        st.subheader("3 · Dados da transferência")
        st.markdown(
            f'<div class="nota"><b>Horário de corte: {CUTOFF_HOUR}h.</b> '
            'Solicitações após esse horário podem ser processadas no próximo dia útil.</div>',
            unsafe_allow_html=True,
        )

        # auto-formata ao sair do campo
        if "valor_ted" in st.session_state:
            _raw = st.session_state["valor_ted"]
            _parsed = parse_valor(_raw)
            if _parsed is not None:
                _fmt = fmt_money(_parsed)
                if _raw != _fmt:
                    st.session_state["valor_ted"] = _fmt

        col1, col2 = st.columns(2)
        valor_str = col1.text_input("Valor (R$)", placeholder="ex: 1.500,00", key="valor_ted")
        if valor_str.strip() and parse_valor(valor_str) is None:
            col1.caption("⚠️ Formato inválido")

        erro_envio = st.session_state.pop("erro_envio", None)
        if erro_envio:
            st.error(f"Erro ao enviar: {erro_envio}")

        with st.form("transferencia"):
            data_pag   = st.date_input("Data de pagamento", value=date.today(), min_value=date.today())
            finalidade = st.text_input("Finalidade (opcional)", placeholder="ex: Aplicação fundo XYZ")
            enviar = st.form_submit_button("Enviar solicitação ✉️", use_container_width=True, type="primary")

        # Proteção contra duplo-clique (01/09/2026): em vez de tentar travar o próprio
        # botão (tentativa anterior — ficava preso em "Enviando..." sem nunca chegar
        # na tela de confirmação, e ainda dependia de uma checagem de duplicata de
        # 2min no Sheets pra cobrir o resto), o clique só valida os dados e muda de
        # etapa pra "enviando" — a chamada lenta (Sheets/email) roda só nessa etapa
        # seguinte. Como o botão some da tela assim que a etapa muda, não existe mais
        # nada pra clicar de novo — mais simples e mais robusto que travar o widget.
        if enviar:
            valor = parse_valor(st.session_state.get("valor_ted", ""))
            if valor is None:
                st.error("Valor inválido. Use o formato: 1.500,00")
                st.stop()
            dados = {
                "banker_nome":      st.session_state.banker_nome,
                "banker_email":     st.session_state.banker_email,
                "cliente_nome":     cli["nome"],
                "cliente_id":       cli["id"],
                "conta_btg_origem": cli["conta_btg"],
                "banco_codigo":     c["banco_codigo"],
                "banco_nome":       c["banco_nome"],
                "agencia":          c["agencia"],
                "conta_destino":    c["conta"],
                "digito":           c["digito"],
                "tipo":             c["tipo"],
                "titular":          c["titular"],
                "cpf_cnpj_titular": c["cpf_cnpj_titular"],
                "valor":            str(valor),
                "data_pagamento":   data_pag.strftime("%Y-%m-%d"),
                "conta_nova":       conta_nova,
                "valor_fmt":        fmt_money(valor),
                "data_br":          data_pag.strftime("%d/%m/%Y"),
                "finalidade":       finalidade,
            }

            # Mesmo aviso do card do board: só faz sentido quando o pagamento foi
            # pedido pro MESMO dia da solicitação e o pedido veio depois do corte.
            agora = datetime.now(TZ)
            if data_pag == agora.date() and agora.time() >= dtime(CUTOFF_HOUR, 0):
                prox_util = proximo_dia_util(agora.date())
                dados["aviso_prazo"] = (
                    f"Como sua solicitação foi feita depois das {CUTOFF_HOUR}h, "
                    f"na prática ela será executada no próximo dia útil ({prox_util.strftime('%d/%m')})."
                )
            else:
                dados["aviso_prazo"] = ""

            st.session_state.sol_pendente = dados
            st.session_state.step         = "enviando"
            st.rerun()

    # ── STEP 3.5: ENVIANDO (transição, sem botão na tela) ──────────────────────
    elif step == "enviando":
        dados = st.session_state.sol_pendente
        with st.spinner("Enviando..."):
            # Fix 26/10/2026: se o e-mail falhava (senha do Gmail trocada), o app voltava
            # ao formulário com a linha JÁ gravada na planilha; cada novo clique gravava
            # outra linha e a sync TED→Notion mandava um aviso por linha. Agora só a
            # gravação (sem linha criada ainda) pode voltar ao formulário; depois dela
            # o fluxo segue sempre para "sucesso", mesmo com o e-mail falhando.
            registrou = False
            try:
                registrar_solicitacao(dados)
                registrou = True
            except Exception as e:
                st.session_state.step       = "transferencia"
                st.session_state.erro_envio = str(e)
            if registrou:
                resultado = None
                st.session_state.sol_email_falhou = None
                try:
                    resultado = enviar_email(dados)
                except Exception as e:
                    st.session_state.sol_email_falhou = str(e)
                # enviar_confirmacao_banker removida daqui (04/09/2026) — a confirmação
                # com tabela pro solicitante virou parte do e-mail único de time
                # (notificar_nova_ted, TED-Notion/ted_to_notion_novo.py), disparado
                # quando este e-mail cai na pasta monitorada e a sync roda. Evita o
                # duplo aviso que existia quando o solicitante também tinha acesso à
                # própria conta como advisor.
                st.session_state.sol          = dados
                st.session_state.sol_mock     = resultado if resultado and resultado.get("mock") else None
                st.session_state.sol_conf     = None
                st.session_state.step         = "sucesso"
                st.session_state.sol_pendente = None
                clear_nc()
        st.rerun()
