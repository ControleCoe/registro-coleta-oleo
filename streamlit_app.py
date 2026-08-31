import html
import json
from pathlib import Path
import runpy
from datetime import datetime
from urllib import request
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo
import streamlit as st
from loader_utils import transition_loader_html

st.set_page_config(
    page_title="Controle de Amostras de Óleo",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
STOCK_SHEETS_ENDPOINT = "https://script.google.com/macros/s/AKfycbzUtD0MyAr_iZ5IybtZ41mZQtiiiUBoTvUWIzEgisjgrpxeDGMDaw1q26PRTwh6E0Eixw/exec"
KIT_CONTRACT_MATERIAL = "KIT CONTRATO"


@st.cache_data(ttl=120, show_spinner=False)
def carregar_saldo_kit_contrato():
    try:
        with request.urlopen(STOCK_SHEETS_ENDPOINT, timeout=8) as response:
            registros = json.loads(response.read().decode("utf-8"))
        saldo = 0
        for registro in registros if isinstance(registros, list) else []:
            material = str(registro.get("material", "")).strip().upper()
            if material != KIT_CONTRACT_MATERIAL:
                continue
            quantidade = float(registro.get("quantity", 0) or 0)
            saldo += quantidade if registro.get("type") == "Entrada" else -quantidade
        return max(0, int(round(saldo))), ""
    except Exception:
        return 0, "Não foi possível atualizar o saldo agora."


def salvar_saldo_kit_contrato(quantidade_desejada, quantidade_atual, localidade):
    diferenca = int(quantidade_desejada) - int(quantidade_atual)
    if diferenca < 0:
        return False, "O saldo só diminui quando uma solicitação de retorno é confirmada."
    if diferenca == 0:
        return True, "A quantidade já está atualizada."
    agora = datetime.now(ZoneInfo("America/Manaus"))
    movimento = {
        "id": str(uuid4()),
        "type": "Entrada",
        "material": KIT_CONTRACT_MATERIAL,
        "measure": "",
        "quantity": diferenca,
        "responsible": localidade or "LOCALIDADE",
        "date": agora.strftime("%Y-%m-%d"),
        "time": agora.strftime("%H:%M:%S"),
        "origin": "kit-contract",
        "notes": f"[HORA:{agora.strftime('%H:%M:%S')}] Ajuste do KIT CONTRATO para {quantidade_desejada}",
    }
    requisicao = request.Request(
        STOCK_SHEETS_ENDPOINT,
        data=json.dumps(movimento).encode("utf-8"),
        headers={"Content-Type": "text/plain;charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(requisicao, timeout=15) as response:
            resposta = response.read().decode("utf-8")
        if resposta:
            resultado = json.loads(resposta)
            if isinstance(resultado, dict) and resultado.get("ok") is False:
                raise RuntimeError(resultado.get("error") or "Falha ao salvar")
        carregar_saldo_kit_contrato.clear()
        return True, "Quantidade salva com sucesso."
    except Exception:
        return False, "Não foi possível salvar. Tente novamente."

query_locality = st.query_params.get("localidade", "")
if isinstance(query_locality, list):
    query_locality = query_locality[0] if query_locality else ""
detected_locality = str(query_locality or "").strip()
if detected_locality:
    st.session_state["localidade_acesso"] = detected_locality.upper()

if "modulo_atual" not in st.session_state:
    st.session_state["modulo_atual"] = "inicio"

if "mostrar_loader_navegacao" not in st.session_state:
    st.session_state["mostrar_loader_navegacao"] = False

if "mensagem_loader_navegacao" not in st.session_state:
    st.session_state["mensagem_loader_navegacao"] = "Carregando..."

def abrir_modulo(nome):
    st.session_state["modulo_atual"] = nome
    st.session_state["mostrar_loader_navegacao"] = True
    st.session_state["mensagem_loader_navegacao"] = (
        "Carregando Registro de Coleta..."
        if nome == "coleta"
        else "Carregando Retorno da Amostra..."
    )

def voltar_inicio():
    st.session_state["modulo_atual"] = "inicio"
    st.session_state["mostrar_loader_navegacao"] = True
    st.session_state["mensagem_loader_navegacao"] = "Voltando ao início..."

st.markdown("""
<style>
.stApp{
    background:linear-gradient(135deg,#cfe6c0 0%,#e5f4dc 48%,#c8e5ba 100%);
    color:#16391f;
}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{display:none}
.block-container{max-width:1180px;padding-top:1.2rem;padding-bottom:2rem}

.soft-shell{
    background:rgba(255,255,255,.48);
    border:1px solid rgba(255,255,255,.65);
    border-radius:34px;
    padding:16px;
    box-shadow:0 20px 50px rgba(60,110,50,.14);
}

.hero{
    background:linear-gradient(135deg,#f3ffed 0%,#ebf9e5 52%,#e4f5dd 100%);
    border:1px solid rgba(47,143,70,.12);
    border-radius:28px;
    min-height:500px;
    padding:28px 34px 34px;
    box-shadow:0 16px 35px rgba(54,102,46,.10);
}

.topbar{display:flex;align-items:center;}
.brand{
    font-size:1.25rem;
    font-weight:800;
    color:#1f6531;
}
.brand span{color:#2f8f46}

.access-toolbar{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:1rem;
    margin:0 0 1rem;
    padding:.75rem 1rem;
    background:rgba(255,255,255,.78);
    border:1px solid rgba(47,143,70,.18);
    border-radius:18px;
    box-shadow:0 10px 24px rgba(54,102,46,.10);
}
.access-locality{color:#416348;font-size:.95rem;}
.access-locality strong{color:#17652f;}
.central-exit-link{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:42px;
    padding:.65rem 1.15rem;
    border-radius:999px;
    background:#17743a;
    color:#fff!important;
    text-decoration:none!important;
    font-weight:800;
}
.central-exit-link:hover{background:#105d2e;color:#fff!important;}
.access-actions{display:flex;align-items:center;gap:.7rem}
.kit-contract-link{
    display:inline-grid;
    grid-template-columns:auto 44px;
    align-items:stretch;
    min-height:42px;
    border:2px solid #17743a;
    border-radius:12px;
    overflow:hidden;
    background:#fff;
    color:#17652f!important;
    text-decoration:none!important;
    font-weight:900;
    letter-spacing:.03em;
}
.kit-contract-link span{display:flex;align-items:center;padding:.55rem .85rem}
.kit-contract-link strong{display:grid;place-items:center;border-left:2px solid #17743a;background:#e8f7e2;font-size:1.1rem}
.kit-contract-card{
    margin:-.35rem 0 1rem;
    padding:1rem 1.1rem;
    border:1px solid rgba(47,143,70,.18);
    border-radius:18px;
    background:rgba(255,255,255,.88);
    box-shadow:0 10px 24px rgba(54,102,46,.10);
}
.kit-contract-card h3{margin:0;color:#17652f}
.kit-contract-card p{margin:.25rem 0 0;color:#56705b}
.kit-contract-close{display:inline-block;margin-top:.4rem;color:#17652f!important;font-weight:700;text-decoration:none!important}


.hero-grid{
    display:grid;
    grid-template-columns:1.15fr .85fr;
    gap:2rem;
    align-items:center;
    min-height:400px;
}

.hero-copy h1{
    font-size:clamp(3rem,6vw,5.4rem);
    line-height:.94;
    letter-spacing:-.045em;
    margin:.7rem 0 1.4rem;
    color:#173d20;
    font-weight:800;
}
.hero-copy h1 span{color:#3ca353}
.hero-copy p{
    max-width:650px;
    font-size:1.08rem;
    line-height:1.65;
    color:#5f7163;
    margin:0;
}

.badges{
    display:flex;
    flex-wrap:wrap;
    gap:.75rem;
    margin-top:1.6rem;
}
.badge{
    border:1px solid rgba(47,143,70,.22);
    background:rgba(255,255,255,.52);
    color:#56705b;
    border-radius:999px;
    padding:.55rem .9rem;
    font-size:.88rem;
}

.visual{
    display:flex;
    justify-content:center;
    align-items:center;
    min-height:320px;
    position:relative;
}
.visual-orb{
    width:min(330px,75vw);
    aspect-ratio:1/1;
    border-radius:50%;
    background:linear-gradient(145deg,#d8f1cf,#bfe4b2);
    box-shadow:inset 0 0 0 1px rgba(47,143,70,.14),0 24px 48px rgba(46,114,54,.18);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:8rem;
}
.visual-card{
    position:absolute;
    right:0;
    bottom:28px;
    width:220px;
    background:rgba(255,255,255,.82);
    border:1px solid rgba(47,143,70,.16);
    border-radius:22px;
    padding:18px;
    box-shadow:0 16px 30px rgba(54,102,46,.12);
}
.visual-card strong{display:block;color:#1f4f2a;margin-bottom:.4rem}
.visual-card span{color:#68796b;font-size:.9rem;line-height:1.4}

.section-title{
    margin:1.7rem 0 .9rem;
    font-size:1.2rem;
    font-weight:800;
    color:#1e4728;
}

.action-card{
    background:rgba(255,255,255,.63);
    border:1px solid rgba(47,143,70,.15);
    border-radius:24px;
    padding:26px;
    min-height:210px;
    box-shadow:0 14px 28px rgba(54,102,46,.10);
}
.action-icon{
    width:58px;
    height:58px;
    border-radius:18px;
    background:linear-gradient(145deg,#e7f6df,#f7fff4);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:1.9rem;
    margin-bottom:1.3rem;
}
.action-card h3{margin:0 0 .7rem;color:#183f22;font-size:1.5rem}
.action-card p{margin:0;color:#68796b;line-height:1.55}

.stButton>button{
    background:linear-gradient(135deg,#3fa653,#2f8f46);
    color:#fff;
    border:none;
    border-radius:999px;
    min-height:48px;
    font-weight:700;
    width:100%;
}
.stButton>button:hover{
    background:linear-gradient(135deg,#369549,#26783a);
    color:#fff;
    border:none;
}

.module-wrap{
    background:rgba(255,255,255,.60);
    border:1px solid rgba(47,143,70,.14);
    border-radius:28px;
    padding:18px;
    box-shadow:0 18px 40px rgba(54,102,46,.12);
}
.footer{text-align:center;color:#708173;padding-top:1.4rem;font-size:.88rem}

@media(max-width:850px){
    .hero-grid{grid-template-columns:1fr}
    .visual{min-height:260px}
    .visual-orb{width:240px;font-size:6rem}
    .visual-card{right:8px;bottom:5px;width:190px}
    .hero{padding:24px 22px}
    
}

[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,textarea{
background:#edf8e8!important;color:#1f4f2a!important;border:1px solid #b9d9b3!important;}

/* ===== Ajustes V2.6.2 ===== */

/* Faixa clara completa atrás do botão Voltar */
.module-topbar{
    height: 58px !important;
    width: 100% !important;
    margin: 0 0 -50px 0 !important;
    border-radius: 22px !important;
    background: rgba(255,255,255,.78) !important;
    border: 1px solid rgba(47,143,70,.12) !important;
    box-shadow: 0 10px 28px rgba(54,102,46,.10) !important;
}

/* Garante que o botão Voltar fique por cima da faixa */
div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) {
    position: relative;
    z-index: 2;
}

/* Campos com fundo verde muito claro e texto escuro */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-baseweb="select"] > div{
    background: #eef8e9 !important;
    color: #173d20 !important;
    border: 1px solid #2f5e38 !important;
    -webkit-text-fill-color: #173d20 !important;
}

div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stNumberInput"] input::placeholder,
div[data-testid="stTextArea"] textarea::placeholder{
    color: #718273 !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #718273 !important;
}

/* Rótulos dos campos com contraste forte */
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stSelectbox"] label{
    color: #173d20 !important;
    font-weight: 700 !important;
}

/* Botão QR Code em verde claro, diferente dos demais */
button[kind="secondary"][data-testid="baseButton-secondary"]{
    background: linear-gradient(135deg,#69c978,#57b868) !important;
    color: #ffffff !important;
    border: none !important;
}

button[kind="secondary"][data-testid="baseButton-secondary"]:hover{
    background: linear-gradient(135deg,#5dbd6d,#4aa65b) !important;
    color: #ffffff !important;
}

/* Mensagens e textos auxiliares com contraste melhor */
[data-testid="stAlert"] p,
[data-testid="stCaptionContainer"],
[data-testid="stMarkdownContainer"] p{
    color: #4e6653;
}


/* V2.6.3 button text */
div[data-testid="stButton"] button,
div[data-testid="stButton"] button *{
 color:#fff !important;
 -webkit-text-fill-color:#fff !important;
 fill:#fff !important;
}
div[data-testid="stButton"] button svg{
 stroke:#fff !important;
 fill:#fff !important;
}


/* V2.6.4 - Data da coleta no mesmo padrão verde-claro */
div[data-testid="stDateInput"] input,
div[data-testid="stDateInput"] > div > div{
    background: #eef8e9 !important;
    color: #173d20 !important;
    -webkit-text-fill-color: #173d20 !important;
    border-color: #2f5e38 !important;
}

div[data-testid="stDateInput"] input::placeholder{
    color: #718273 !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #718273 !important;
}

div[data-testid="stDateInput"] label{
    color: #173d20 !important;
    font-weight: 700 !important;
}

</style>
""", unsafe_allow_html=True)

localidade_atual = str(st.session_state.get("localidade_acesso", "") or "").strip().upper()
localidade_exibida = html.escape(localidade_atual or "NÃO INFORMADA")
kit_aberto = str(st.query_params.get("kit_contrato", "") or "") == "1"
# A tela inicial abre sem esperar a planilha. O saldo é consultado apenas ao abrir o Kit.
saldo_kit_contrato, erro_saldo_kit = carregar_saldo_kit_contrato() if kit_aberto else (None, "")
localidade_url = quote(localidade_atual)
st.markdown(
    f"""
    <div class="access-toolbar">
      <div class="access-locality">Localidade: <strong>{localidade_exibida}</strong></div>
      <div class="access-actions">
        <a class="kit-contract-link" href="?localidade={localidade_url}&kit_contrato=1" target="_self">
          <span>KIT CONTRATO</span>{f'<strong>{saldo_kit_contrato}</strong>' if saldo_kit_contrato is not None else ''}
        </a>
        <a class="central-exit-link"
           href="https://estoque-laboratorio.kodere-tecnologia.chatgpt.site/panel/painel-direto.html?sair=1"
           target="_self">Sair</a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if kit_aberto:
    st.markdown(
        f"""
        <div class="kit-contract-card">
          <h3>KIT CONTRATO</h3>
          <p>Quantidade atual: <strong>{saldo_kit_contrato}</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_kit_contrato"):
        quantidade_kit = st.number_input(
            "Quantidade",
            min_value=0,
            step=1,
            value=int(saldo_kit_contrato),
        )
        salvar_kit = st.form_submit_button("Salvar", use_container_width=True)
    if erro_saldo_kit:
        st.warning(erro_saldo_kit)
    if salvar_kit:
        sucesso_kit, mensagem_kit = salvar_saldo_kit_contrato(
            quantidade_kit,
            saldo_kit_contrato,
            localidade_atual,
        )
        if sucesso_kit:
            st.success(mensagem_kit)
            st.rerun()
        else:
            st.error(mensagem_kit)
    st.markdown(
        f'<a class="kit-contract-close" href="?localidade={localidade_url}" target="_self">Fechar</a>',
        unsafe_allow_html=True,
    )

modulo = st.session_state["modulo_atual"]

navigation_loader = None
if st.session_state.get("mostrar_loader_navegacao", False):
    navigation_loader = st.empty()
    navigation_loader.markdown(
        transition_loader_html(
            st.session_state.get(
                "mensagem_loader_navegacao",
                "Carregando...",
            )
        ),
        unsafe_allow_html=True,
    )

if modulo == "inicio":
    st.markdown("""
    <div class="soft-shell">
      <section class="hero">
        <div class="topbar">
          <div class="brand">OLIVEIRA <span>ENERGIA</span></div>
        </div>
        <div class="hero-grid">
          <div class="hero-copy">
            <h1>Controle de <span>Amostras</span> de Óleo</h1>
            <p>Gerencie o fluxo de coleta e retorno das amostras com uma interface simples, segura e organizada.</p>
            <div class="badges">
              <div class="badge">Leitura por QR Code</div>
              <div class="badge">Integração Google Sheets</div>
              <div class="badge">Retorno de amostras</div>
            </div>
          </div>
          <div class="visual">
            <div class="visual-orb">🧪</div>
            <div class="visual-card">
              <strong>Fluxo simplificado</strong>
              <span>Registre, acompanhe e processe as amostras em poucos passos.</span>
            </div>
          </div>
        </div>
      </section>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Acesso rápido</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("""
        <div class="action-card">
          <div class="action-icon">🧪</div>
          <h3>Registro de Coleta</h3>
          <p>Cadastre uma nova coleta utilizando a leitura automática do QR Code da amostra.</p>
        </div>
        """, unsafe_allow_html=True)
        st.button("Acessar Registro de Coleta", on_click=abrir_modulo, args=("coleta",), use_container_width=True, key="abrir_coleta")

    with c2:
        st.markdown("""
        <div class="action-card">
          <div class="action-icon">📦</div>
          <h3>Retorno da Amostra</h3>
          <p>Informe as amostras recebidas, registre as ordens de serviço e processe o retorno.</p>
        </div>
        """, unsafe_allow_html=True)
        st.button("Acessar Retorno da Amostra", on_click=abrir_modulo, args=("retorno",), use_container_width=True, key="abrir_retorno")

    st.markdown('<div class="footer">Oliveira Energia · Controle de Amostras de Óleo · Versão 2.6</div>', unsafe_allow_html=True)

else:
    c1,_=st.columns([1,4])
    with c1:
        st.button("← Voltar ao início", on_click=voltar_inicio, use_container_width=True, key=f"voltar_{modulo}")

    if modulo == "coleta":
        runpy.run_path(
            str(BASE_DIR / "pages" / "1_Registro_de_Coleta.py"),
            run_name="__main__",
        )
    elif modulo == "retorno":
        runpy.run_path(
            str(BASE_DIR / "pages" / "2_Retorno_da_Amostra.py"),
            run_name="__main__",
        )

if navigation_loader is not None:
    navigation_loader.empty()
    st.session_state["mostrar_loader_navegacao"] = False

    
