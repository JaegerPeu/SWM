import smtplib
import io
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import openpyxl
import streamlit as st

DESTINATARIO = "middle@swmgestao.com.br"
RELAY_SUBJECT_PREFIX = "[TED-CONFIRM]"
RELAY_TO_EMAIL = "pedro.duarte@swmgestao.com.br"

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

def enviar_email_cancelamento(dados):
    assunto = f"[TED][CANCELAMENTO] {dados['cliente_nome']} — R$ {dados['valor_fmt']} — {dados['banker_nome']}"
    corpo = "\n".join([
        "SOLICITAÇÃO DE CANCELAMENTO DE TED",
        "═══════════════════════════════════",
        "",
        f"Banker:   {dados['banker_nome']}",
        f"Cliente:  {dados['cliente_nome']}",
        f"Valor:    R$ {dados['valor_fmt']}",
        f"Data de pagamento original: {dados['data_pagamento']}",
        f"ID da solicitação: {dados['id']}",
        "",
        f"Pedido de cancelamento feito às {dados['hora_cancelamento']}.",
    ])

    if st.secrets.get("MOCK_EMAIL", False):
        return {"mock": True, "assunto": assunto, "corpo": corpo}

    remetente = st.secrets["EMAIL_FROM"]
    senha     = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg["Subject"] = assunto
    msg["From"]    = remetente
    msg["To"]      = DESTINATARIO
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(remetente, senha)
        srv.send_message(msg)

    return {"mock": False}

def enviar_confirmacao_banker(dados):
    """NÃO É MAIS CHAMADA (04/09/2026) — desativada em Boletador-TED/app.py.
    A tabela que esta função montava foi reaproveitada em
    TED-Notion/ted_to_notion_novo.py::notificar_nova_ted, que agora manda um
    único e-mail (solicitante + time) em vez de duplicar com esta confirmação
    pessoal via relay. Mantida aqui só como referência do template/relay —
    remover de vez se não for reaproveitada em outro fluxo."""
    email_banker = (dados.get("banker_email") or "").strip()
    if not email_banker:
        return {"enviado": False, "motivo": "sem_email"}

    assunto = f"[TED] Recebemos sua solicitação — {dados['cliente_nome']} — R$ {dados['valor_fmt']}"

    aviso_html = ""
    if dados.get("aviso_prazo"):
        aviso_html = f"⚠️ {dados['aviso_prazo']}<br><br>"

    # Mesma tabela que já ia só pro middle (_montar) — pedido do usuário
    # (04/09) pro banker ver pra quem/onde a TED foi, não só o valor.
    # Estilo inline em cada <td> — Outlook/Word não respeita cascata vinda
    # de um <table>/<div> ancestral (mesmo gotcha já documentado no
    # ted_to_notion_novo.py).
    s = "font-family:Calibri, sans-serif; font-size:11pt; padding:4px 8px;"
    linhas_tabela = [
        ("Cliente", dados["cliente_nome"]),
        ("Origem", f"BTG Pactual · Ag. 0001 · Cc. {dados['conta_btg_origem']}"),
        ("Destino", f"{dados['banco_nome']} · Ag. {dados['agencia']} · "
                     f"Cc. {dados['conta_destino']}-{dados['digito']} ({dados['tipo']})"),
        ("Titular", f"{dados['titular']} — {dados['cpf_cnpj_titular']}"),
        ("Valor", f"R$ {dados['valor_fmt']}"),
        ("Data de pagamento", dados["data_br"]),
    ]
    if dados.get("finalidade"):
        linhas_tabela.append(("Finalidade", dados["finalidade"]))

    linhas_html = "".join(
        f'<tr><td style="{s}"><b>{rotulo}</b></td><td style="{s}">{valor}</td></tr>'
        for rotulo, valor in linhas_tabela
    )
    tabela_html = (
        f'<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">'
        f"{linhas_html}</table>"
    )

    conta_nova_html = ""
    if dados.get("conta_nova"):
        conta_nova_html = (
            f'<p style="{s}">⚠️ Conta nova — ainda em cadastro, sem histórico de TEDs anteriores.</p>'
        )

    corpo = (
        f"Olá, {dados['banker_nome']}!<br><br>"
        f"Recebemos sua solicitação de TED, detalhada abaixo:<br><br>"
        f"{tabela_html}<br>"
        f"{conta_nova_html}"
        f"{aviso_html}"
        f"A equipe de operações já foi notificada e vai processar a transferência.<br><br>"
        f"Este é um e-mail automático de confirmação de recebimento."
    )

    if st.secrets.get("MOCK_EMAIL", False):
        return {"enviado": True, "mock": True, "assunto": assunto, "corpo": corpo}

    # Relay: manda um e-mail "técnico" pro Outlook de quem opera o fluxo (RELAY_TO_EMAIL),
    # não pra caixa compartilhada DESTINATARIO — várias pessoas têm acesso a ela, e
    # apagar depois de processado só limpa a cópia de quem está com o Power Automate
    # conectado, poluindo a caixa dos outros. Com o payload em JSON puro no CORPO
    # (o assunto do gatilho pode vir truncado/depender de funções não disponíveis no
    # Power Automate; o corpo chega intacto, como texto puro). Um fluxo no Power
    # Automate ("Quando um novo e-mail chegar") filtra pelo assunto fixo, lê o corpo
    # e manda a confirmação de verdade pro banker via Outlook — evita precisar do
    # gatilho HTTP (Premium).
    payload = json.dumps({"to": email_banker, "subject": assunto, "body": corpo})

    remetente = st.secrets["EMAIL_FROM"]
    senha     = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg["Subject"] = RELAY_SUBJECT_PREFIX
    msg["From"]    = remetente
    msg["To"]      = RELAY_TO_EMAIL
    msg.attach(MIMEText(payload, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(remetente, senha)
            srv.send_message(msg)
        return {"enviado": True, "mock": False}
    except Exception as e:
        return {"enviado": False, "motivo": "erro_relay", "detalhe": str(e)}
