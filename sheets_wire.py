"""Boletador de Wire (BETA) — acesso à planilha. Autocontido: não importa nada do Boletador-TED.
Lê (somente leitura) Bankers/Times/TimeBankers/ClienteTimes/Clientes da mesma planilha do Boletador de TED (login e acesso por time).
Clientes do wire = aba Clientes com tipo = OFF; contas BTG US de origem = aba ContasOffshore (por cliente_id).
Escreve só nas abas próprias SolicitacoesWire e BeneficiariosWire; cria as abas próprias que faltarem na 1ª leitura/gravação."""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

COLS_SOL = ["timestamp", "id", "status", "banker_nome", "cliente_id", "cliente_nome", "conta_btg_origem", "tipo_transferencia",
            "moeda", "valor", "motivo", "beneficiario_id", "beneficiario_nome", "referencia", "anexos", "beneficiario_novo",
            "cancelamento_solicitado", "banker_cancelamento", "data_pagamento"]
COLS_CONTAS = ["cliente_id", "conta_btg_us", "apelido", "ativa", "cliente_nome"]
COLS_BEN = ["id", "cliente_id", "beneficiario_nome", "segundo_beneficiario", "conta", "banco_nome", "swift", "pais",
            "precisa_intermediario", "intermediario_nome", "aba", "motivo_btg", "id_btg"]


@st.cache_resource
def get_gc():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES))


@st.cache_resource(ttl=300)
def get_ss():
    return get_gc().open_by_key(st.secrets["SHEET_ID"])


def _aba(nome, colunas):
    ss = get_ss()
    try:
        return ss.worksheet(nome)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=nome, rows=500, cols=len(colunas))
        ws.append_row(colunas)
        return ws


def login_banker(usuario, senha):
    try:
        for r in get_ss().worksheet("Bankers").get_all_records():
            if str(r["login"]).strip().lower() == usuario.lower() and str(r["senha"]).strip() == senha:
                return {"ok": True, "id": str(r["id"]), "nome": str(r["nome"]), "email": str(r.get("email", "")).strip()}
        return {"ok": False, "erro": "Usuário ou senha inválidos."}
    except Exception as e:
        return {"ok": False, "erro": f"Erro ao acessar base: {e}"}


def _acesso(banker_id):
    """(ve_tudo, ids de Clientes liberados) — mesma regra do Boletador de TED: time Gestora vê todos; demais, só clientes dos times do banker."""
    banker_id = str(banker_id).strip()
    times = get_ss().worksheet("Times").get_all_records()
    gestora = next((str(t["id"]) for t in times if str(t["nome"]).strip().upper() == "GESTORA"), None)
    meus = {str(r["time_id"]) for r in get_ss().worksheet("TimeBankers").get_all_records() if str(r["banker_id"]).strip() == banker_id}
    if gestora and gestora in meus:
        return True, set()
    ids = {str(r["cliente_id"]) for r in get_ss().worksheet("ClienteTimes").get_all_records() if str(r["time_id"]) in meus} if meus else set()
    return False, ids


@st.cache_data(ttl=15)
def get_clientes(banker_id):
    """Clientes do WIRE = linhas da aba Clientes com tipo = OFF. Quem tem conta onshore e offshore tem duas linhas (uma ON, uma OFF), com ids diferentes.
    Acesso do banker pelo ClienteTimes/TimeBankers, igual à TED. Contas BTG US de cada cliente: aba ContasOffshore (por cliente_id);
    se o cliente não tiver linha lá, vale a conta_btg da própria linha em Clientes."""
    ve_tudo, ids = _acesso(banker_id)
    contas = {}
    for r in _aba("ContasOffshore", COLS_CONTAS).get_all_records():
        conta = str(r.get("conta_btg_us", "")).strip()
        if conta and str(r.get("ativa", "SIM")).strip().upper() != "NÃO":
            contas.setdefault(str(r.get("cliente_id", "")).strip(), []).append({"conta": conta, "apelido": str(r.get("apelido", "")).strip()})
    out = []
    for r in get_ss().worksheet("Clientes").get_all_records():
        cid = str(r["id"]).strip()
        if str(r.get("tipo", "")).strip().upper() != "OFF":
            continue
        if not ve_tudo and cid not in ids:
            continue
        cs = contas.get(cid) or ([{"conta": str(r.get("conta_btg", "")).strip(), "apelido": ""}] if str(r.get("conta_btg", "")).strip() else [])
        if cs:
            out.append({"id": cid, "nome": str(r["nome"]).strip(), "contas": cs})
    return sorted(out, key=lambda x: x["nome"])


@st.cache_data(ttl=15)
def get_beneficiarios(cliente_id):
    rows = _aba("BeneficiariosWire", COLS_BEN).get_all_records()
    return [{k: str(r.get(k, "")) for k in COLS_BEN} for r in rows if str(r.get("cliente_id", "")).strip() == str(cliente_id).strip()]


def _novo_id(ws):
    return max((int(r["id"]) for r in ws.get_all_records() if str(r.get("id", "")).isdigit()), default=0) + 1


def registrar_wire(d):
    """d: dict com os campos da solicitação; d['benef'] = dict do beneficiário (com 'id' se já cadastrado, sem se novo)."""
    wb = _aba("BeneficiariosWire", COLS_BEN)
    b = d["benef"]
    novo = not b.get("id")
    if novo:
        b["id"] = str(_novo_id(wb))
        wb.append_row([b["id"], d["cliente_id"], b["beneficiario_nome"], b.get("segundo_beneficiario", ""), b["conta"], b["banco_nome"],
                       b["swift"], b["pais"], b["precisa_intermediario"], b.get("intermediario_nome", ""), b.get("aba", "")])
        get_beneficiarios.clear()
    ws = _aba("SolicitacoesWire", COLS_SOL)
    sid = _novo_id(ws)
    ws.append_row([datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"), sid, "pendente", d["banker_nome"], d["cliente_id"], d["cliente_nome"],
                   d["conta_btg_origem"], d["tipo_transferencia"], d["moeda"], float(d["valor"]), d["motivo"], b["id"],
                   b["beneficiario_nome"], d.get("referencia", ""), ", ".join(d.get("anexos", [])), "SIM" if novo else "NÃO", "", "",
                   d.get("data_pagamento", "")])
    get_wires_abertas.clear()
    return sid


STATUS_ABERTOS = {"pendente", "em processo", "em aprovação cliente"}


def _dp(v):
    """data_pagamento (AAAA-MM-DD); se o Sheets converteu em data de verdade, get_all_records devolve o serial."""
    if isinstance(v, (int, float)) and v:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date().isoformat()
    return str(v).strip()


def _ts(v):
    """O Sheets às vezes converte "dd/mm/aaaa hh:mm:ss" escrito por update_cell em data de verdade; get_all_records devolve o serial."""
    if isinstance(v, (int, float)) and v:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).strftime("%d/%m/%Y %H:%M:%S")
    return str(v)


@st.cache_data(ttl=15)
def get_wires_abertas(banker_id):
    """Wires abertos dos clientes liberados ao banker (acesso pelo cliente_id gravado em cada linha)."""
    ids = {c["id"] for c in get_clientes(banker_id)}
    rows = _aba("SolicitacoesWire", COLS_SOL).get_all_records(value_render_option="UNFORMATTED_VALUE")
    out = []
    for r in rows:
        if str(r.get("cliente_id", "")).strip() not in ids or str(r.get("status", "")).strip().lower() not in STATUS_ABERTOS:
            continue
        out.append({k: r.get(k, "") for k in COLS_SOL} | {"status": str(r.get("status", "")).strip().lower(), "id": str(r["id"]),
                                                          "timestamp": _ts(r["timestamp"]), "valor": float(r["valor"]), "data_pagamento": _dp(r.get("data_pagamento", "")),
                                                          "cancelamento_solicitado": _ts(r.get("cancelamento_solicitado", "")) if r.get("cancelamento_solicitado", "") != "" else ""})
    return out


def solicitar_cancelamento_wire(sol_id, banker_nome):
    ws = _aba("SolicitacoesWire", COLS_SOL)
    vals = ws.get_all_values()
    h = vals[0]
    ci, cc, cq = h.index("id"), h.index("cancelamento_solicitado"), h.index("banker_cancelamento")
    for i, linha in enumerate(vals[1:], start=2):
        if len(linha) > ci and linha[ci].strip() == str(sol_id):
            ws.update_cell(i, cc + 1, datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"))
            ws.update_cell(i, cq + 1, banker_nome)
            get_wires_abertas.clear()
            return True
    return False
