import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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
                return {"ok": True, "id": str(r["id"]), "nome": str(r["nome"])}
        return {"ok": False, "erro": "Usuário ou senha inválidos."}
    except Exception as e:
        return {"ok": False, "erro": f"Erro ao acessar base: {e}"}

def get_clientes(banker_id):
    rows = get_ss().worksheet("Clientes").get_all_records()
    clientes = [
        {"id": str(r["id"]), "nome": str(r["nome"]), "conta_btg": str(r["conta_btg"])}
        for r in rows
        if str(r["banker_id"]).strip() == str(banker_id).strip()
    ]
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
    get_ss().worksheet("Solicitacoes").append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
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
    ])
