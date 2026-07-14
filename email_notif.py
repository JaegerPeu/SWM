import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import openpyxl
import streamlit as st

DESTINATARIO = "middle@swmgestao.com.br"

def _montar(dados):
    linhas = [
        "SOLICITAÇÃO DE TED",
        "══════════════════",
        "",
        f"Banker:   {dados['banker_nome']}",
        f"Cliente:  {dados['cliente_nome']}",
        "",
        "ORIGEM",
        "──────",
        "Banco:    208 — BTG Pactual",
        "Agência:  0001",
        f"Conta:    {dados['conta_btg_origem']}",
        "Tipo:     Corrente",
        f"Titular:  {dados['cliente_nome']}",
        "",
        "DESTINO",
        "───────",
        f"Banco:    {dados['banco_codigo']} — {dados['banco_nome']}",
        f"Agência:  {dados['agencia']}",
        f"Conta:    {dados['conta_destino']}-{dados['digito']}",
        f"Tipo:     {dados['tipo']}",
        f"Titular:  {dados['titular']}",
        f"CPF/CNPJ: {dados['cpf_cnpj_titular']}",
        "",
        "TRANSFERÊNCIA",
        "─────────────",
        f"Valor:          R$ {dados['valor_fmt']}",
        f"Data pagamento: {dados['data_br']}",
    ]
    if dados.get("finalidade"):
        linhas.append(f"Finalidade:     {dados['finalidade']}")
    if dados["conta_nova"]:
        linhas.insert(0, "")
        linhas.insert(0, "⚠️  CONTA NOVA — cadastrar em ContasTED após execução")

    prefixo = "[TED][CONTA NOVA] " if dados["conta_nova"] else "[TED] "
    assunto = f"{prefixo}{dados['cliente_nome']} — R$ {dados['valor_fmt']} — {dados['banker_nome']}"
    return assunto, "\n".join(linhas)

def _gerar_excel(dados):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TED"
    ws.append(["conta_btg", "numero_banco", "agencia", "conta_destino", "data_ted", "valor_ted"])
    ws.append([
        dados["conta_btg_origem"],
        dados["banco_codigo"],
        dados["agencia"],
        f"{dados['conta_destino']}-{dados['digito']}",
        dados["data_br"],
        float(dados["valor"]),
    ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

def enviar_email(dados):
    assunto, corpo = _montar(dados)

    if st.secrets.get("MOCK_EMAIL", False):
        return {"mock": True, "assunto": assunto, "corpo": corpo}

    remetente = st.secrets["EMAIL_FROM"]
    senha     = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg["Subject"] = assunto
    msg["From"]    = remetente
    msg["To"]      = DESTINATARIO
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    excel_bytes = _gerar_excel(dados)
    nome_arquivo = f"TED_{dados['cliente_nome'].replace(' ', '_')}_{dados['data_pagamento']}.xlsx"
    part = MIMEBase("application", "octet-stream")
    part.set_payload(excel_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{nome_arquivo}"')
    msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(remetente, senha)
        srv.send_message(msg)

    return {"mock": False}

def enviar_confirmacao_banker(dados):
    email_banker = (dados.get("banker_email") or "").strip()
    if not email_banker:
        return {"enviado": False, "motivo": "sem_email"}

    assunto = f"[TED] Recebemos sua solicitação — {dados['cliente_nome']} — R$ {dados['valor_fmt']}"
    corpo = (
        f"Olá, {dados['banker_nome']}!\n\n"
        f"Recebemos sua solicitação de TED para o cliente {dados['cliente_nome']}, "
        f"no valor de R$ {dados['valor_fmt']}, com pagamento previsto para {dados['data_br']}.\n\n"
        f"A equipe de operações já foi notificada e vai processar a transferência.\n\n"
        f"Este é um e-mail automático de confirmação de recebimento."
    )

    if st.secrets.get("MOCK_EMAIL", False):
        return {"enviado": True, "mock": True, "assunto": assunto, "corpo": corpo}

    remetente = st.secrets["EMAIL_FROM"]
    senha     = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg["Subject"] = assunto
    msg["From"]    = remetente
    msg["To"]      = email_banker
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(remetente, senha)
        srv.send_message(msg)

    return {"enviado": True, "mock": False}
