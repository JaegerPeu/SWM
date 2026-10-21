"""Boletador de Wire (BETA) — e-mail de notificação. Autocontido.
Segredos (st.secrets): EMAIL_FROM, EMAIL_PASSWORD; BETA_DESTINO (padrão middle@swmgestao.com.br); MOCK_EMAIL (true = não envia, só mostra; padrão false, igual à TED)."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import streamlit as st

DESTINO_PADRAO = "middle@swmgestao.com.br"


def _montar(d):
    b = d["benef"]
    L = ["SOLICITAÇÃO DE WIRE", "═══════════════════════", "",
         f"Banker:   {d['banker_nome']}", f"Cliente:  {d['cliente_nome']}", f"Conta BTG US (origem): {d['conta_btg_origem']}", "",
         "OPERAÇÃO", "────────",
         f"Tipo:     {d['tipo_transferencia']}", f"Valor:    {d['moeda']} {d['valor_fmt']}", f"Data pagamento: {d.get('data_br') or '—'}", f"Motivo:   {d['motivo']}",
         f"Referência: {d.get('referencia') or '—'}", f"Anexos:   {', '.join(d.get('anexos', [])) or 'nenhum'}", "",
         "BENEFICIÁRIO" + ("  (NOVO — cadastrar no BTG)" if d.get("beneficiario_novo") else ""), "────────────",
         f"Nome:     {b['beneficiario_nome']}"]
    if b.get("segundo_beneficiario"):
        L.append(f"2º beneficiário: {b['segundo_beneficiario']}")
    L += [f"Conta:    {b['conta']}", f"Banco:    {b['banco_nome']}", f"SWIFT:    {b['swift']}", f"País:     {b['pais']}"]
    if b["precisa_intermediario"] == "SIM":
        L += [f"Banco intermediário: {b.get('intermediario_nome', '')}"]
    L.append(f"ABA:      {b.get('aba') or '—'}")
    assunto = f"[WIRE]{'[BENEF. NOVO]' if d.get('beneficiario_novo') else ''} {d['cliente_nome']} — {d['moeda']} {d['valor_fmt']} — {d['banker_nome']}"
    return assunto, "\n".join(L)


def enviar(d, arquivos):
    """arquivos: lista de (nome, bytes). Retorna dict; com MOCK_EMAIL só devolve o texto."""
    assunto, corpo = _montar(d)
    if st.secrets.get("MOCK_EMAIL", False):
        return {"mock": True, "assunto": assunto, "corpo": corpo}
    de, senha = st.secrets["EMAIL_FROM"], st.secrets["EMAIL_PASSWORD"]
    para = st.secrets.get("BETA_DESTINO", DESTINO_PADRAO)
    m = MIMEMultipart()
    m["From"], m["To"], m["Subject"] = de, para, assunto
    m.attach(MIMEText(corpo, "plain", "utf-8"))
    for nome, dados in arquivos:
        p = MIMEBase("application", "octet-stream"); p.set_payload(dados); encoders.encode_base64(p)
        p.add_header("Content-Disposition", "attachment", filename=nome); m.attach(p)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(de, senha); s.sendmail(de, [para], m.as_string())
    return {"mock": False, "assunto": assunto}


def enviar_cancelamento(d):
    """d: banker_nome, cliente_nome, moeda, valor_fmt, id, hora_cancelamento."""
    assunto = f"[WIRE][CANCELAMENTO] {d['cliente_nome']} — {d['moeda']} {d['valor_fmt']} — {d['banker_nome']}"
    corpo = (f"PEDIDO DE CANCELAMENTO DE WIRE\n\nBanker:  {d['banker_nome']}\nCliente: {d['cliente_nome']}\n"
             f"Valor:   {d['moeda']} {d['valor_fmt']}\nSolicitação #{d['id']}\nPedido em: {d['hora_cancelamento']}")
    if st.secrets.get("MOCK_EMAIL", False):
        return {"mock": True, "assunto": assunto, "corpo": corpo}
    de, senha = st.secrets["EMAIL_FROM"], st.secrets["EMAIL_PASSWORD"]
    para = st.secrets.get("BETA_DESTINO", DESTINO_PADRAO)
    m = MIMEMultipart()
    m["From"], m["To"], m["Subject"] = de, para, assunto
    m.attach(MIMEText(corpo, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(de, senha)
        srv.sendmail(de, [para], m.as_string())
    return {"mock": False, "assunto": assunto}
