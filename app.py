import streamlit as st
from sheets import (
    login_banker, get_clientes, get_contas, registrar_solicitacao,
    get_solicitacoes_abertas, solicitar_cancelamento,
)
from email_notif import enviar_email, enviar_confirmacao_banker, enviar_email_cancelamento
from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
CUTOFF_HOUR = 16

st.set_page_config(page_title="Boletador de TED — SWM", page_icon="💸", layout="centered")

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden }
.btg-box, .dest-box {
    border-radius: 10px; padding: 14px 18px; margin: 10px 0 16px 0;
    display: flex; align-items: center; justify-content: space-between; min-height: 96px;
}
.btg-box  { background: #eff6ff; border: 1.5px solid #bfdbfe; }
.dest-box { background: #f8fafc; border: 1.5px solid #cbd5e1; }
.btg-label  { font-size: 11px; font-weight: 600; color: #3b82f6;
               text-transform: uppercase; letter-spacing: .07em }
.btg-numero { font-size: 26px; font-weight: 700; color: #1d4ed8; margin-top: 3px }
.btg-nome   { font-size: 14px; color: #334155; margin-top: 4px }
.dest-label   { font-size: 11px; font-weight: 600; color: #64748b;
                 text-transform: uppercase; letter-spacing: .07em }
.dest-banco   { font-size: 22px; font-weight: 700; color: #1e293b; margin-top: 3px }
.dest-detalhe { font-size: 14px; color: #475569; margin-top: 4px; line-height: 1.55 }
.box-content { display: flex; flex-direction: column; justify-content: center; }
.bank-logo   { height: 76px; width: auto; max-width: 110px; object-fit: contain;
                border-radius: 8px; flex-shrink: 0; margin-left: 16px; }
.sol-card {
    border-radius: 10px; padding: 10px 14px; margin: 8px 0;
    background: #f8fafc; border: 1.5px solid #cbd5e1;
}
.sol-cliente { font-size: 15px; font-weight: 700; color: #1e293b; }
.sol-detalhe { font-size: 13px; color: #475569; margin-top: 2px; }
.sol-data    { font-size: 12px; color: #64748b; margin-top: 4px; }
.sol-aviso   { font-size: 12px; color: #b45309; margin-top: 4px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

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
    ("sol_conf", None), ("cancel_pending_id", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

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

def calcular_prazo_cancelamento(data_solicitacao_str):
    dt = datetime.strptime(data_solicitacao_str, "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
    if dt.time() < dtime(CUTOFF_HOUR, 0):
        cutoff_hoje = dt.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0)
        return min(dt + timedelta(minutes=30), cutoff_hoje)
    prox_util = proximo_dia_util(dt.date())
    return datetime.combine(prox_util, dtime(12, 0), tzinfo=TZ)

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

    prazo = calcular_prazo_cancelamento(s["data"])
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

def cancelamento_expirado(s):
    # Depois de solicitar o cancelamento, o card some do board em 24h mesmo se
    # a operação ainda não tiver mudado o status — evita ficar pendurado pra
    # sempre esperando ação manual. Não apaga nada, só some da visão do board.
    if not s["cancelamento_solicitado"]:
        return False
    dt_pedido = datetime.strptime(s["cancelamento_solicitado"], "%d/%m/%Y %H:%M:%S").replace(tzinfo=TZ)
    return datetime.now(TZ) - dt_pedido > timedelta(hours=CANCELAMENTO_VISIVEL_HORAS)

def render_board():
    st.subheader("Solicitações em aberto — meus clientes")
    abertas = [s for s in get_solicitacoes_abertas(st.session_state.banker_id) if not cancelamento_expirado(s)]
    pendentes   = [s for s in abertas if s["status"] == "pendente"]
    em_processo = [s for s in abertas if s["status"] == "em processo"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Pendente** &nbsp;·&nbsp; {len(pendentes)}")
        if not pendentes:
            st.caption("Nenhuma solicitação pendente.")
        for s in pendentes:
            solicitacao_card(s)
    with col2:
        st.markdown(f"**Em Processo** &nbsp;·&nbsp; {len(em_processo)}")
        if not em_processo:
            st.caption("Nenhuma solicitação em processo.")
        for s in em_processo:
            solicitacao_card(s)

# ── LOGIN ─────────────────────────────────────────────────────────────────
if not st.session_state.logado:
    st.markdown("### SWM Gestão")
    st.title("Boletador de TED")
    st.write("")
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
c1, c2 = st.columns([5, 1])
c1.markdown(f"**Boletador de TED** &nbsp;·&nbsp; {st.session_state.banker_nome}")
if c2.button("Sair"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
st.divider()

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
        else:
            st.success("✅ Solicitação enviada! A equipe de operações foi notificada por e-mail.")
        if d["conta_nova"]:
            st.warning("⚠️ Conta nova — a equipe irá cadastrar após execução.")

        conf = st.session_state.sol_conf
        if conf and conf.get("enviado"):
            if conf.get("mock"):
                with st.expander("📧 Confirmação que seria enviada para você", expanded=False):
                    st.caption(f"Assunto: {conf['assunto']}")
                    st.code(conf["corpo"], language=None)
            else:
                st.info(f"📧 Confirmação de recebimento enviada para {d['banker_email']}.")
        elif conf and conf.get("motivo") == "sem_email":
            st.warning("⚠️ Seu e-mail não está cadastrado na aba Bankers — confirmação não enviada. Peça para cadastrarem.")
        elif conf and conf.get("motivo") == "erro_relay":
            st.warning("⚠️ Não consegui enviar a confirmação agora. A solicitação foi registrada normalmente.")

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

        with st.form("transferencia"):
            data_pag   = st.date_input("Data de pagamento", value=date.today(), min_value=date.today())
            finalidade = st.text_input("Finalidade (opcional)", placeholder="ex: Aplicação fundo XYZ")
            enviar = st.form_submit_button("Enviar solicitação ✉️", use_container_width=True, type="primary")

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

            with st.spinner("Enviando..."):
                try:
                    registrar_solicitacao(dados)
                    resultado = enviar_email(dados)
                    conf      = enviar_confirmacao_banker(dados)
                    st.session_state.sol      = dados
                    st.session_state.sol_mock = resultado if resultado and resultado.get("mock") else None
                    st.session_state.sol_conf = conf
                    st.session_state.step     = "sucesso"
                    clear_nc()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao enviar: {e}")
