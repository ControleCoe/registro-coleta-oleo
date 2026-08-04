
from contextlib import contextmanager
import html
import streamlit as st


def _loader_html(message: str) -> str:
    safe_message = html.escape(str(message or "Carregando..."))
    return f"""
    <style>
    .oe-loader-overlay {{
        position: fixed;
        inset: 0;
        z-index: 999999;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(226, 244, 217, 0.82);
        backdrop-filter: blur(5px);
        -webkit-backdrop-filter: blur(5px);
    }}
    .oe-loader-card {{
        min-width: 310px;
        max-width: 88vw;
        padding: 30px 34px 24px;
        border-radius: 24px;
        background: rgba(255,255,255,.94);
        border: 1px solid rgba(47,143,70,.18);
        box-shadow: 0 24px 60px rgba(38,87,43,.22);
        text-align: center;
    }}
    .oe-pac-stage {{
        position: relative;
        width: 310px;
        height: 88px;
        margin: 0 auto 14px;
        overflow: hidden;
    }}
    .oe-pacman {{
        position: absolute;
        left: 42px;
        top: 10px;
        width: 70px;
        height: 35px;
        border-radius: 100em 100em 0 0;
        background: #fed75a;
        transform-origin: bottom;
        animation: oe-eating-top .5s infinite;
    }}
    .oe-pacman::before {{
        content: "";
        display: block;
        position: absolute;
        width: 70px;
        height: 35px;
        top: 35px;
        left: 0;
        transform-origin: top;
        border-radius: 0 0 100em 100em;
        background: #fed75a;
        transform: rotate(80deg);
        animation: oe-eating-bottom .5s infinite;
    }}
    .oe-pacman::after {{
        position: absolute;
        content: "";
        display: block;
        height: 14px;
        width: 14px;
        border-radius: 50%;
        top: 28px;
        left: 36px;
        transform-origin: center;
        animation: oe-center .5s infinite, oe-ball .5s -.33s infinite linear;
    }}
    .oe-loader-message {{
        color: #173d20;
        font-weight: 800;
        font-size: 1rem;
        letter-spacing: .01em;
    }}
    .oe-loader-sub {{
        margin-top: 6px;
        color: #6c7f70;
        font-size: .84rem;
    }}
    @keyframes oe-eating-top {{
        0% {{ transform: rotate(-40deg); }}
        50% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(-40deg); }}
    }}
    @keyframes oe-eating-bottom {{
        0% {{ transform: rotate(80deg); }}
        50% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(80deg); }}
    }}
    @keyframes oe-center {{
        0% {{ transform: rotate(40deg); }}
        50% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(40deg); }}
    }}
    @keyframes oe-ball {{
        0% {{
            opacity: .75;
            box-shadow:
                70px 0 0 0 #38a34f,
                120px 0 0 0 #38a34f,
                170px 0 0 0 #38a34f,
                220px 0 0 0 #38a34f;
        }}
        100% {{
            opacity: 1;
            box-shadow:
                20px 0 0 0 #38a34f,
                70px 0 0 0 #38a34f,
                120px 0 0 0 #38a34f,
                170px 0 0 0 #38a34f;
        }}
    }}
    </style>
    <div class="oe-loader-overlay">
      <div class="oe-loader-card">
        <div class="oe-pac-stage"><div class="oe-pacman"></div></div>
        <div class="oe-loader-message">{safe_message}</div>
        <div class="oe-loader-sub">Aguarde um instante</div>
      </div>
    </div>
    """


@contextmanager
def pacman_loader(message: str):
    placeholder = st.empty()
    placeholder.markdown(_loader_html(message), unsafe_allow_html=True)
    try:
        yield
    finally:
        placeholder.empty()
