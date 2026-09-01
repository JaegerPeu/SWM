import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
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

@st.cache_resource(ttl=300)
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

@st.cache_data(ttl=15)
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

@st.cache_data(ttl=15)
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

def _e_duplicata_recente(ws, dados, janela_min=2):
    """Guarda contra duplo-clique/reenvio (01/09/2026): se a mesma solicitação
    exata (banker + cliente + conta destino + valor + data de pagamento) já foi
    registrada nos últimos `janela_min` minutos, é o mesmo clique replicado (app
    travou, usuário clicou "Enviar" de novo) — não uma 2ª TED de verdade.
    UNFORMATTED_VALUE obrigatório pro campo "valor" (mesmo bug de decimal BR já
    documentado em get_solicitacoes_abertas) — leitura própria, separada da usada
    pra calcular novo_id, porque UNFORMATTED_VALUE devolve "id" como float e
    quebraria o `.isdigit()` de lá."""
    rows = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    agora = datetime.now(TZ)
    for r in rows:
        if (str(r.get("banker_nome", "")) == dados["banker_nome"]
                and str(r.get("cliente_nome", "")) == dados["cliente_nome"]
                and str(r.get("conta_destino", "")) == dados["conta_destino"]
                and str(r.get("digito", "")) == dados["digito"]
                and float(r.get("valor", 0) or 0) == float(dados["valor"])
                and str(r.get("data_pagamento", "")) == dados["data_pagamento"]):
            try:
                dt_r = datetime.strptime(str(r["timestamp"]), "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
            except (ValueError, TypeError):
                continue
            if agora - dt_r < timedelta(minutes=janela_min):
                return True
    return False

def registrar_solicitacao(dados):
    ws = get_ss().worksheet("Solicitacoes")
    if _e_duplicata_recente(ws, dados):
        return  # já tem uma solicitação idêntica registrada agora há pouco — não duplica
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
    get_solicitacoes_abertas.clear()

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
    get_contas.clear()

STATUS_ABERTOS = {"pendente", "em processo", "em aprovação cliente"}

@st.cache_data(ttl=15)
def get_solicitacoes_abertas(banker_id):
    # Escopo por cliente liberado no login (mesma regra do get_clientes), não por
    # quem criou a solicitação — um banker pode ver TEDs abertas de colegas pro
    # mesmo cliente. conta_btg é único por cliente e já é gravado em cada linha
    # de Solicitacoes, então serve de chave de acesso sem precisar de coluna nova.
    contas_permitidas = {c["conta_btg"] for c in get_clientes(banker_id)}
    # UNFORMATTED_VALUE obrigatório aqui: o default (FORMATTED_VALUE) devolve "valor"
    # como o Sheets exibe (vírgula decimal pt-BR, ex "15.504,15") e a numericise
    # automática do gspread interpreta o ponto como milhar, virando 1550415 — mesmo
    # bug já corrigido em TED-Notion/ted_to_notion.py, nunca replicado aqui (11/08/2026).
    rows = get_ss().worksheet("Solicitacoes").get_all_records(value_render_option="UNFORMATTED_VALUE")
    abertas = []
    for r in rows:
        if str(r.get("conta_btg_origem", "")).strip() not in contas_permitidas:
            continue
        status = str(r.get("status", "")).strip().lower()
        if status not in STATUS_ABERTOS:
            continue
        abertas.append({
            "id":                     str(r["id"]),
            "banker_nome":            str(r.get("banker_nome", "")),
            "cliente_nome":           str(r["cliente_nome"]),
            "banco_nome":             str(r["banco_nome"]),
            "titular":                str(r["titular"]),
            "valor":                  float(r["valor"]),
            "data_pagamento":         str(r["data_pagamento"]),
            "data":                   str(r["timestamp"]),
            "status":                 status,
            "cancelamento_solicitado":            str(r.get("cancelamento_solicitado", "")).strip(),
            "banker_solicitacao_cancelamento":    str(r.get("banker_solicitacao_cancelamento", "")).strip(),
        })
    return abertas

def solicitar_cancelamento(sol_id, banker_nome):
    ws = get_ss().worksheet("Solicitacoes")
    valores = ws.get_all_values()
    header, linhas = valores[0], valores[1:]
    try:
        col_id   = header.index("id")
        col_canc = header.index("cancelamento_solicitado")
        col_quem = header.index("banker_solicitacao_cancelamento")
    except ValueError as e:
        raise RuntimeError(
            f"Coluna não encontrada em 'Solicitacoes': {e}. "
            "Confira se os headers 'cancelamento_solicitado' e 'banker_solicitacao_cancelamento' "
            "foram criados corretamente na planilha."
        )
    for i, linha in enumerate(linhas):
        if len(linha) > col_id and linha[col_id].strip() == str(sol_id):
            linha_num = i + 2
            ws.update_cell(linha_num, col_canc + 1, datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"))
            ws.update_cell(linha_num, col_quem + 1, banker_nome)
            get_solicitacoes_abertas.clear()
            return True
    return False
