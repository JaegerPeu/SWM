import smtplib
from email.mime.text import MIMEText
import streamlit as st

DESTINATARIO = "middle@swmgestao.com.br"

def enviar_email(dados):
    linhas = [
        "SOLICITAÇÃO DE TED",
        "══════════════════",
        "",
        f"Banker:             {dados['banker_nome']}",
        f"Cliente:            {dados['cliente_nome']}",
        f"Conta BTG (origem): {dados['conta_btg_origem']}",
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

    prefixo  = "[TED][CONTA NOVA] " if dados["conta_nova"] else "[TED] "
    assunto  = f"{prefixo}{dados['cliente_nome']} — R$ {dados['valor_fmt']} — {dados['banker_nome']}"
    corpo    = "\n".join(linhas)

    remetente = st.secrets["EMAIL_FROM"]
    senha     = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = assunto
    msg["From"]    = remetente
    msg["To"]      = DESTINATARIO

    with smtplib.SMTP("smtp.office365.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(remetente, senha)
        srv.send_message(msg)
