import streamlit as st
from sheets import login_banker, get_clientes, get_contas, registrar_solicitacao
from email_notif import enviar_email
from datetime import date

st.set_page_config(page_title="Boletador de TED — SWM", page_icon="💸", layout="centered")

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden }
.btg-box {
    background: #eff6ff; border: 1.5px solid #bfdbfe;
    border-radius: 10px; padding: 14px 18px; margin: 10px 0 16px 0;
}
.btg-label  { font-size: 11px; font-weight: 600; color: #3b82f6;
               text-transform: uppercase; letter-spacing: .07em }
.btg-numero { font-size: 26px; font-weight: 700; color: #1d4ed8; margin-top: 2px }
.btg-nome   { font-size: 14px; color: #334155; margin-top: 3px }
</style>
""", unsafe_allow_html=True)

BANCOS = [
    ("001","Banco do Brasil"),    ("237","Bradesco"),
    ("104","Caixa Econômica Federal"), ("745","Citibank"),
    ("212","Banco Original"),     ("336","C6 Bank"),
    ("077","Inter"),              ("341","Itaú"),
    ("323","Mercado Pago"),       ("260","Nubank"),
    ("208","BTG Pactual"),        ("290","PagBank"),
    ("623","Pan"),                ("380","PicPay"),
    ("633","Rendimento"),         ("422","Safra"),
    ("033","Santander"),          ("748","Sicredi"),
    ("756","Sicoob"),             ("197","Stone"),
    ("655","Votorantim (BV)"),    ("348","XP Investimentos"),
    ("___","Outro"),
]
BANCO_OPTS = [""] + [f"{nome}  ({cod})" for cod, nome in BANCOS]

# ── SESSION STATE ─────────────────────────────────────────────────────────
for k, v in [
    ("logado", False), ("banker_id", None), ("banker_nome", None),
    ("step", "cliente"), ("clientes", None),
    ("cliente_sel", None), ("conta_sel", None), ("conta_nova", False), ("sol", None), ("sol_mock", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

def fmt_money(val):
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def clear_nc():
    for k in ["nc_banco","nc_b_cod","nc_b_nome","nc_agencia","nc_tipo",
              "nc_conta","nc_digito","nc_titular","nc_cpf","radio_contas"]:
        st.session_state.pop(k, None)

def btg_box(conta_btg, nome):
    st.markdown(f"""
    <div class="btg-box">
        <div class="btg-label">Conta BTG de origem</div>
        <div class="btg-numero">{conta_btg}</div>
        <div class="btg-nome">{nome}</div>
    </div>
    """, unsafe_allow_html=True)

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

        titular  = st.text_input("Nome do titular",        key="nc_titular")
        cpf_cnpj = st.text_input("CPF / CNPJ do titular", key="nc_cpf", placeholder="000.000.000-00")

        if st.button("Usar esta conta →", key="btn_nc", use_container_width=True, type="primary"):
            erros = []
            if not banco_sel:             erros.append("banco")
            if not agencia.strip():       erros.append("agência")
            if not conta_n.strip():       erros.append("conta")
            if not digito.strip():        erros.append("dígito")
            if not titular.strip():       erros.append("titular")
            if not cpf_cnpj.strip():      erros.append("CPF/CNPJ")
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
                st.session_state.conta_sel = {
                    "banco_codigo":     b_cod,     "banco_nome":       b_nome,
                    "agencia":          agencia.strip(), "conta":       conta_n.strip(),
                    "digito":           digito.strip(),  "tipo":        tipo,
                    "titular":          titular.strip(), "cpf_cnpj_titular": cpf_cnpj.strip(),
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
    st.info(
        f"**Destino:** {c['banco_nome']}  ·  Ag. {c['agencia']}  ·  "
        f"Cc. {c['conta']}-{c['digito']} ({c['tipo']})  \n"
        f"Titular: {c['titular']}"
    )
    if conta_nova:
        st.warning("⚠️ Conta nova — será cadastrada pela equipe após execução.")

    st.subheader("3 · Dados da transferência")
    with st.form("transferencia"):
        col1, col2 = st.columns(2)
        valor    = col1.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        data_pag = col2.date_input("Data de pagamento", value=date.today(), min_value=date.today())
        finalidade = st.text_input("Finalidade (opcional)", placeholder="ex: Aplicação fundo XYZ")
        enviar = st.form_submit_button("Enviar solicitação ✉️", use_container_width=True, type="primary")

    if enviar:
        dados = {
            "banker_nome":      st.session_state.banker_nome,
            "cliente_nome":     cli["nome"],
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
        with st.spinner("Enviando..."):
            try:
                registrar_solicitacao(dados)
                resultado = enviar_email(dados)
                st.session_state.sol      = dados
                st.session_state.sol_mock = resultado if resultado and resultado.get("mock") else None
                st.session_state.step     = "sucesso"
                clear_nc()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao enviar: {e}")
