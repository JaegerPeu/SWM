"""Boletador de Wire — interface. Usada como aba "Wire" do Boletador de TED (app.py) e pelo app beta (app_wire_beta.py).
Uso: render_wire({"id": <id do banker>, "nome": <nome do banker>}) dentro de uma aba/coluna do app.
Autocontido: depende só de sheets_wire.py e email_wire.py (mesma pasta). Chaves de sessão e de widget começam com "w_"/"w" para não colidir com a TED."""
import streamlit as st
from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from sheets_wire import get_clientes, get_beneficiarios, registrar_wire, get_wires_abertas, solicitar_cancelamento_wire
from email_wire import enviar, enviar_cancelamento

TZ = ZoneInfo("America/Sao_Paulo")
CUTOFF_HOUR = 16

MOTIVOS = ["Same Name (mesma titularidade)", "Third Party - Others", "Third Party - Corporate Formation / Ongoing filing Fees",
           "Third Party - Related Parties"]
MOEDAS = ["USD"]   # só US$ por enquanto; incluir outras moedas aqui quando houver
AVISO = ("**Para executarmos o wire, todos os dados e documentos abaixo são obrigatórios.** Wires com informações incompletas ou "
         "divergentes podem ser recusados pelo banco ou atrasar a liquidação. Para beneficiários de terceiros, anexe o documento que "
         "comprove a operação (invoice, contrato ou similar). Confira nome do beneficiário, SWIFT/ABA e número da conta: erro nesses "
         "dados pode gerar devolução com tarifas.")
CSS = ("<style>.w-aviso{background:#eff6ff;border:1.5px solid #bfdbfe;border-radius:10px;padding:12px 16px;margin:8px 0 16px 0;"
       "color:#1e3a8a;font-size:14px}.w-card{background:#f8fafc;border:1.5px solid #cbd5e1;border-radius:10px;padding:10px 14px;margin:8px 0;"
       "color:#1e293b;font-size:13px}.w-aviso-cut{font-size:12px;color:#b45309;font-weight:600;margin-top:4px}</style>")


def parse_valor(s):
    s = s.strip().replace("US$", "").replace("$", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        # o último separador é o decimal (1,500.00 ou 1.500,00)
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        i = s.rfind(",")
        s = (s[:i].replace(",", "") + "." + s[i + 1:]) if len(s) - i - 1 <= 2 else s.replace(",", "")
    else:
        i = s.rfind(".")
        s = (s[:i].replace(".", "") + "." + s[i + 1:]) if (i != -1 and len(s) - i - 1 <= 2) else s.replace(".", "")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def fmt(v):
    return f"{v:,.2f}"          # padrão americano (US$): 1,500.00


def proximo_dia_util(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def prazo_cancelamento(ts, data_pagamento):
    """Mesma regra da TED. Pagamento no mesmo dia do pedido: 1h ou até as 16h (o que vier primeiro); pedido depois das 16h: até 12h do próximo
    dia útil. Pagamento em dia futuro: até 12h do próprio dia de pagamento."""
    dt = datetime.strptime(ts, "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
    dl = date.fromisoformat(data_pagamento) if data_pagamento else dt.date()
    if dl == dt.date():
        if dt.time() < dtime(CUTOFF_HOUR, 0):
            return min(dt + timedelta(hours=1), dt.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0))
        return datetime.combine(proximo_dia_util(dt.date()), dtime(12, 0), tzinfo=TZ)
    return datetime.combine(dl, dtime(12, 0), tzinfo=TZ)


def _novo_wire(banker):
    ss = st.session_state
    if ss.w_feito:
        f = ss.w_feito
        st.success(f"Solicitação de wire #{f['id']} registrada. A confirmação por e-mail chega em instantes, assim que a sincronização processar.")
        if f["mail"].get("mock"):
            st.info("Modo teste: e-mail NÃO enviado. Conteúdo abaixo.")
            st.code(f["mail"]["assunto"] + "\n\n" + f["mail"]["corpo"])
        if st.button("Nova solicitação de wire", type="primary", key="w_nova"):
            ss.w_feito = None
            ss.w_n += 1
            st.rerun()
        return

    st.markdown(f'<div class="w-aviso">{AVISO}</div>', unsafe_allow_html=True)
    k = ss.w_n     # muda a cada nova solicitação → limpa os campos

    clientes = get_clientes(banker["id"])
    if not clientes:
        st.warning("Nenhum cliente offshore liberado para o seu usuário.")
        return
    por_id = {c["id"]: c for c in clientes}
    cli_id = st.selectbox("Cliente", list(por_id), format_func=lambda i: por_id[i]["nome"], index=None, placeholder="Escolha o cliente", key=f"wcli{k}")
    if not cli_id:
        return
    cli = por_id[cli_id]
    contas_us = cli["contas"]
    conta_us = contas_us[0]["conta"] if len(contas_us) == 1 else st.selectbox(
        "Conta BTG US de origem", [c["conta"] for c in contas_us], key=f"wcus{k}",
        format_func=lambda c: next((f"{c} — {x['apelido']}" if x["apelido"] else c) for x in contas_us if x["conta"] == c))
    st.caption(f"Conta BTG US de origem: {conta_us}")

    tipo = st.radio("Tipo de transferência", ["Externa", "Interna (entre contas BTG US)"], horizontal=True, key=f"wtipo{k}")
    c1, c2, c3 = st.columns([1, 2, 2])
    moeda = c1.selectbox("Moeda", MOEDAS, key=f"wmoeda{k}")
    valor_txt = c2.text_input("Valor", placeholder="1,500.00", key=f"wvalor{k}")
    data_pag = c3.date_input("Data de pagamento", value=date.today(), min_value=date.today(), format="DD/MM/YYYY", key=f"wdata{k}")
    if data_pag.weekday() >= 5:
        st.caption("⚠️ Fim de semana: na prática será executado no próximo dia útil.")
    motivo = st.radio("Motivo do wire", MOTIVOS, key=f"wmotivo{k}")
    terceiro = not motivo.startswith("Same Name")

    st.subheader("Beneficiário")
    benef = None
    ok_benef = False
    if tipo.startswith("Interna"):
        nome = st.text_input("Nome do titular da conta de destino", key=f"win_nome{k}")
        conta = st.text_input("Conta BTG US de destino", key=f"win_conta{k}")
        benef = {"id": "", "beneficiario_nome": nome.strip(), "segundo_beneficiario": "", "conta": conta.strip(), "banco_nome": "BTG Pactual US",
                 "swift": "", "pais": "US", "precisa_intermediario": "NÃO", "intermediario_nome": "", "aba": ""}
        ok_benef = bool(nome.strip() and conta.strip())
    else:
        existentes = {b["id"]: b for b in get_beneficiarios(cli["id"])}

        def _rot(i):
            if i == "novo":
                return "➕ Novo beneficiário"
            b = existentes[i]
            mot = f" · {b['motivo_btg'].replace('Third Party - ', 'Terceiro: ')}" if b.get("motivo_btg") else ""
            return f"{b['beneficiario_nome']} — {b['banco_nome']} (conta final {b['conta'][-4:]}){mot}"

        esc = st.selectbox("Beneficiário", list(existentes) + ["novo"], key=f"wben{k}", index=None, placeholder="Escolha ou cadastre novo", format_func=_rot)
        if esc and esc != "novo":
            benef, ok_benef = dict(existentes[esc]), True
        elif esc == "novo":
            inter = st.radio("O banco do beneficiário é fora dos EUA (precisa de banco intermediário)?", ["Sim", "Não"], horizontal=True, key=f"wint{k}")
            a, b_ = st.columns(2)
            nome = a.text_input("Nome do beneficiário *", key=f"wbn{k}")
            seg = b_.text_input("Segundo beneficiário final (opcional)", key=f"wbs{k}")
            conta = a.text_input("Número da conta *", key=f"wbc{k}")
            banco = b_.text_input("Nome do banco do beneficiário *", key=f"wbb{k}")
            swift = a.text_input("SWIFT do banco do beneficiário *", key=f"wbw{k}")
            pais = b_.text_input("País do banco *", key=f"wbp{k}")
            if inter == "Sim":
                iname = a.text_input("Nome do banco intermediário *", key=f"wbi{k}")
                aba = b_.text_input("ABA do banco intermediário *", key=f"wba{k}")
            else:
                iname = ""
                aba = a.text_input("ABA do banco do beneficiário *", key=f"wba{k}")
            benef = {"id": "", "beneficiario_nome": nome.strip(), "segundo_beneficiario": seg.strip(), "conta": conta.strip(), "banco_nome": banco.strip(),
                     "swift": swift.strip().upper(), "pais": pais.strip(), "precisa_intermediario": "SIM" if inter == "Sim" else "NÃO",
                     "intermediario_nome": iname.strip(), "aba": aba.strip()}
            ok_benef = all([nome.strip(), conta.strip(), banco.strip(), swift.strip(), pais.strip(), aba.strip()]) and (inter == "Não" or bool(iname.strip()))

    ref = st.text_input("Referência adicional (opcional)", max_chars=128, key=f"wref{k}")
    anexos = st.file_uploader("Documentos de suporte" + (" *" if terceiro else " (opcional)"), accept_multiple_files=True, key=f"wanx{k}")

    valor = parse_valor(valor_txt)
    faltas = []
    if valor is None:
        faltas.append("valor válido")
    if not ok_benef:
        faltas.append("dados completos do beneficiário")
    if terceiro and not anexos:
        faltas.append("documento de suporte (obrigatório para terceiros)")
    if faltas:
        st.warning("Falta: " + "; ".join(faltas) + ".")

    if st.button("Enviar solicitação de wire", type="primary", disabled=bool(faltas), use_container_width=True, key=f"wenviar{k}"):
        d = {"banker_nome": banker["nome"], "cliente_id": cli["id"], "cliente_nome": cli["nome"], "conta_btg_origem": conta_us,
             "tipo_transferencia": tipo, "moeda": moeda, "valor": valor, "valor_fmt": fmt(valor), "motivo": motivo, "referencia": ref.strip(),
             "data_pagamento": data_pag.isoformat(), "data_br": data_pag.strftime("%d/%m/%Y"),
             "anexos": [a.name for a in anexos], "benef": benef, "beneficiario_novo": not benef.get("id") and not tipo.startswith("Interna")}
        with st.spinner("Enviando..."):
            sid = registrar_wire(d)
            mail = enviar(d, [(a.name, a.getvalue()) for a in anexos])
        ss.w_feito = {"id": sid, "mail": mail}
        st.rerun()


def _card_wire(w, banker):
    ss = st.session_state
    dp = w.get("data_pagamento") or ""
    dp_fmt = date.fromisoformat(dp).strftime("%d/%m/%Y") if dp else "—"
    st.markdown(f'<div class="w-card"><b>{w["cliente_nome"]} — {w["moeda"]} {fmt(w["valor"])}</b><br>{w["beneficiario_nome"]} · {w["motivo"]}'
                f'<br>Pagamento previsto: {dp_fmt}'
                f'<br><small>Solicitado em {w["timestamp"]} · por {w["banker_nome"]} · conta {w["conta_btg_origem"]}</small></div>', unsafe_allow_html=True)
    if w["cancelamento_solicitado"]:
        st.caption(f"🚫 Cancelamento solicitado por {w['banker_cancelamento']} em {w['cancelamento_solicitado']}")
        return
    if w["status"] != "pendente":
        return
    agora = datetime.now(TZ)
    prazo = prazo_cancelamento(w["timestamp"], dp)
    if agora >= prazo:
        st.caption("Prazo de cancelamento encerrado")
        return
    if ss.get("w_cancel_id") == w["id"]:
        a, b = st.columns(2)
        if a.button("Sim, cancelar", key=f"wy{w['id']}", type="primary", use_container_width=True):
            solicitar_cancelamento_wire(w["id"], banker["nome"])
            ss.w_cancel_mail = enviar_cancelamento({"banker_nome": banker["nome"], "cliente_nome": w["cliente_nome"], "moeda": w["moeda"],
                                                    "valor_fmt": fmt(w["valor"]), "id": w["id"], "hora_cancelamento": agora.strftime("%d/%m/%Y %H:%M:%S")})
            ss.w_cancel_id = None
            st.rerun()
        if b.button("Voltar", key=f"wn{w['id']}", use_container_width=True):
            ss.w_cancel_id = None
            st.rerun()
    else:
        st.caption(f"⏳ {int((prazo - agora).total_seconds() // 60)} min para solicitar cancelamento")
        if st.button("Solicitar cancelamento", key=f"wc{w['id']}", use_container_width=True):
            ss.w_cancel_id = w["id"]
            st.rerun()


def _board(banker):
    st.subheader("Wires em aberto — meus clientes")
    if st.session_state.get("w_cancel_mail", {}).get("mock"):
        st.info("Modo teste: e-mail de cancelamento NÃO enviado.")
        st.code(st.session_state.w_cancel_mail["assunto"] + "\n\n" + st.session_state.w_cancel_mail["corpo"])
    abertas = get_wires_abertas(banker["id"])
    cols = st.columns(3)
    for col, (rot, stt) in zip(cols, (("Pendente", "pendente"), ("Em Processo", "em processo"), ("Em Aprovação Cliente", "em aprovação cliente"))):
        grupo = [w for w in abertas if w["status"] == stt]
        with col:
            st.markdown(f"**{rot}** · {len(grupo)}")
            if not grupo:
                st.caption("Nenhum.")
            for w in grupo:
                _card_wire(w, banker)


def render_wire(banker):
    """banker = {"id": ..., "nome": ...}. Desenha as abas "Novo wire" e "Em aberto"."""
    st.session_state.setdefault("w_feito", None)
    st.session_state.setdefault("w_n", 0)
    st.markdown(CSS, unsafe_allow_html=True)
    aba_novo, aba_aberto = st.tabs(["Novo wire", "Wires em aberto"])
    with aba_aberto:        # antes do formulário: o formulário usa return/st.rerun em pontos intermediários
        _board(banker)
    with aba_novo:
        _novo_wire(banker)
