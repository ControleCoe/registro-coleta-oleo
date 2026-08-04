from pathlib import Path
import runpy
import streamlit as st
from loader_utils import pacman_loader

st.set_page_config(
    page_title="Controle de Amostras de Óleo",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent

if "modulo_atual" not in st.session_state:
    st.session_state["modulo_atual"] = "inicio"

def abrir_modulo(nome):
    st.session_state["modulo_atual"] = nome

def voltar_inicio():
    st.session_state["modulo_atual"] = "inicio"

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

modulo = st.session_state["modulo_atual"]

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
        with pacman_loader("Carregando Registro de Coleta..."):
            runpy.run_path(
                str(BASE_DIR / "pages" / "1_Registro_de_Coleta.py"),
                run_name="__main__",
            )
    elif modulo == "retorno":
        with pacman_loader("Carregando Retorno da Amostra..."):
            runpy.run_path(
                str(BASE_DIR / "pages" / "2_Retorno_da_Amostra.py"),
                run_name="__main__",
            )

    
