import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gc():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_ss():
    return get_gc().open_by_key(st.secrets["SHEET_ID"])

def login_banker(usuario, senha):
    try:
        rows = get_ss().worksheet("Bankers").get_all_records()
        for r in rows:
            if (str(r["login"]).strip().lower() == usuario.lower() and
                str(r["senha"]).strip() == senha):
                return {
                    "ok": True,
                    "id": str(r["id"]),
                    "nome": str(r["nome"]),
                    "email": str(r.get("email", "")).strip(),
                }
        return {"ok": False, "erro": "Usuário ou senha inválidos."}
    except Exception as e:
        return {"ok": False, "erro": f"Erro ao acessar base: {e}"}

def get_clientes(banker_id):
    rows = get_ss().worksheet("Clientes").get_all_records()
    seen = set()
    clientes = []
    for r in rows:
        if str(r["banker_id"]).strip() != str(banker_id).strip():
            continue
        cid = str(r["id"])
        if cid in seen:
            continue
        seen.add(cid)
        clientes.append({
            "id": cid,
            "nome": str(r["nome"]),
            "conta_btg": str(r["conta_btg"]),
        })
    return sorted(clientes, key=lambda x: x["nome"])

def get_contas(cliente_id):
    rows = get_ss().worksheet("ContasTED").get_all_records()
    return [
        {
            "id":               str(r["id"]),
            "banco_codigo":     str(r["banco_codigo"]),
            "banco_nome":       str(r["banco_nome"]),
            "agencia":          str(r["agencia"]),
            "conta":            str(r["conta"]),
            "digito":           str(r["digito"]),
            "tipo":             str(r["tipo"]),
            "titular":          str(r["titular"]),
            "cpf_cnpj_titular": str(r["cpf_cnpj_titular"]),
        }
        for r in rows
        if str(r["cliente_id"]).strip() == str(cliente_id).strip()
    ]

def registrar_solicitacao(dados):
    ws = get_ss().worksheet("Solicitacoes")
    rows = ws.get_all_records()
    novo_id = max((int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()), default=0) + 1
    ws.append_row([
        datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"),
        dados["banker_nome"],
        dados["cliente_nome"],
        dados["conta_btg_origem"],
        dados["banco_codigo"],
        dados["banco_nome"],
        dados["agencia"],
        dados["conta_destino"],
        dados["digito"],
        dados["tipo"],
        dados["titular"],
        dados["cpf_cnpj_titular"],
        float(dados["valor"]),
        dados["data_pagamento"],
        "SIM" if dados["conta_nova"] else "NÃO",
        "pendente",
        novo_id,
    ])
    if dados["conta_nova"]:
        _cadastrar_conta_nova(dados)

def _cadastrar_conta_nova(dados):
    ws = get_ss().worksheet("ContasTED")
    rows = ws.get_all_records()
    novo_id = max((int(r["id"]) for r in rows if str(r["id"]).isdigit()), default=0) + 1
    ws.append_row([
        str(novo_id),
        dados["cliente_id"],
        dados["banco_codigo"],
        dados["banco_nome"],
        dados["agencia"],
        dados["conta_destino"],
        dados["digito"],
        dados["tipo"],
        dados["titular"],
        dados["cpf_cnpj_titular"],
    ])

STATUS_ABERTOS = {"pendente", "em processo"}

def get_solicitacoes_abertas(banker_nome):
    rows = get_ss().worksheet("Solicitacoes").get_all_records()
    abertas = []
    for r in rows:
        if str(r.get("banker_nome", "")).strip() != banker_nome.strip():
            continue
        status = str(r.get("status", "")).strip().lower()
        if status not in STATUS_ABERTOS:
            continue
        abertas.append({
            "id":                     str(r["id"]),
            "cliente_nome":           str(r["cliente_nome"]),
            "banco_nome":             str(r["banco_nome"]),
            "titular":                str(r["titular"]),
            "valor":                  float(r["valor"]),
            "data_pagamento":         str(r["data_pagamento"]),
            "data":                   str(r["data"]),
            "status":                 status,
            "cancelamento_solicitado": str(r.get("cancelamento_solicitado", "")).strip(),
        })
    return abertas

def solicitar_cancelamento(sol_id):
    ws = get_ss().worksheet("Solicitacoes")
    valores = ws.get_all_values()
    header, linhas = valores[0], valores[1:]
    try:
        col_id   = header.index("id")
        col_canc = header.index("cancelamento_solicitado")
    except ValueError as e:
        raise RuntimeError(
            f"Coluna não encontrada em 'Solicitacoes': {e}. "
            "Confira se o header 'cancelamento_solicitado' foi criado corretamente na planilha."
        )
    for i, linha in enumerate(linhas):
        if len(linha) > col_id and linha[col_id].strip() == str(sol_id):
            ws.update_cell(i + 2, col_canc + 1, datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"))
            return True
    return False
