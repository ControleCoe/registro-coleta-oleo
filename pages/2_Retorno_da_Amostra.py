from __future__ import annotations

import io
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError

from oleo_utils import SPREADSHEET_ID, SHEET_NAME, _get_sheets_service

STATUS_COL = "AF"
DATE_COL = "AG"
OS_COL = "AH"
SAMPLE_COL = "G"
STATUS_VAL = "Retorno 1241"
DATE_FMT = "%d/%m/%Y"

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display: none;}
    .block-container {padding-top: 1.2rem;}
    .stButton > button {border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Retorno da Amostra")
st.caption("Oliveira Energia")


def _svc():
    return _get_sheets_service()


def _col_to_idx(col: str) -> int:
    idx = 0
    for char in col:
        idx = idx * 26 + (ord(char.upper()) - 64)
    return idx - 1


def fetch_sheet() -> List[List[str]]:
    result = (
        _svc()
        .spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_NAME,
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    return result.get("values", [])


def update_rows(rows_idx: List[int], today: str, os_vals: List[str]) -> None:
    if len(rows_idx) != len(os_vals):
        st.error("Inconsistência interna: linhas e ordens de serviço não correspondem.")
        st.stop()

    data = []
    for idx, os_val in zip(rows_idx, os_vals):
        data.extend(
            [
                {"range": f"{SHEET_NAME}!{STATUS_COL}{idx}", "values": [[STATUS_VAL]]},
                {"range": f"{SHEET_NAME}!{DATE_COL}{idx}", "values": [[today]]},
                {"range": f"{SHEET_NAME}!{OS_COL}{idx}", "values": [[os_val]]},
            ]
        )

    try:
        _svc().spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()
    except HttpError as exc:
        st.error(f"❌ Falha ao gravar no Google Sheets: {exc}")
        st.stop()


st.session_state.setdefault("retorno_lista", {})
st.session_state.setdefault("retorno_codigo", "")
st.session_state.setdefault("retorno_os", "")
st.session_state.setdefault("retorno_msg", "")


def _sanitize_numeric_field(key: str, max_length: int) -> None:
    raw_value = str(st.session_state.get(key, "") or "")
    st.session_state[key] = "".join(
        character for character in raw_value if character.isdigit()
    )[:max_length]


def add_item() -> None:
    _sanitize_numeric_field("retorno_codigo", 9)
    _sanitize_numeric_field("retorno_os", 6)
    code = st.session_state.retorno_codigo.strip()
    os_value = st.session_state.retorno_os.strip()

    if not (code.isdigit() and len(code) == 9):
        st.session_state.retorno_msg = "O código da amostra deve conter exatamente 9 números."
        return
    if not (os_value.isdigit() and len(os_value) == 6):
        st.session_state.retorno_msg = "A Ordem de Serviço deve conter exatamente 6 números."
        return
    if code in st.session_state.retorno_lista:
        st.session_state.retorno_msg = f"A amostra {code} já foi adicionada."
        return

    st.session_state.retorno_lista[code] = os_value
    st.session_state.retorno_codigo = ""
    st.session_state.retorno_os = ""
    st.session_state.retorno_msg = ""


with st.container(border=True):
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "Código da amostra",
            key="retorno_codigo",
            max_chars=9,
            placeholder="9 números",
            on_change=_sanitize_numeric_field,
            args=("retorno_codigo", 9),
        )
    with c2:
        st.text_input(
            "Ordem de Serviço",
            key="retorno_os",
            max_chars=6,
            placeholder="6 números",
            on_change=_sanitize_numeric_field,
            args=("retorno_os", 6),
        )
    st.button("➕ Adicionar amostra", on_click=add_item, use_container_width=True)

if st.session_state.retorno_msg:
    st.warning(st.session_state.retorno_msg)

if st.session_state.retorno_lista:
    st.subheader("Amostras adicionadas")
    for code, os_value in list(st.session_state.retorno_lista.items()):
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.code(code)
        c2.write(f"OS {os_value}")
        if c3.button("Remover", key=f"retorno_rm_{code}"):
            st.session_state.retorno_lista.pop(code, None)
            st.rerun()
else:
    st.info("Nenhuma amostra adicionada.")

col_clear, col_generate = st.columns(2)
with col_clear:
    if st.button("🗑️ Limpar lista", use_container_width=True):
        st.session_state.retorno_lista.clear()
        st.session_state.retorno_msg = ""
        st.rerun()
with col_generate:
    generate = st.button("📥 Processar retorno", type="primary", use_container_width=True)

if generate:
    if not st.session_state.retorno_lista:
        st.error("A lista está vazia.")
        st.stop()

    with st.spinner("Consultando a planilha..."):
        try:
            sheet = fetch_sheet()
        except Exception as exc:
            st.error(f"Não foi possível consultar o Google Sheets: {exc}")
            st.stop()

        if not sheet:
            st.error("A aba da planilha está vazia.")
            st.stop()

        header, *data = sheet
        sample_idx = _col_to_idx(SAMPLE_COL)
        os_idx = _col_to_idx(OS_COL)
        rows_idx, os_vals, rows_data = [], [], []
        found = set()

        for row_number, row in enumerate(data, start=2):
            code = str(row[sample_idx]).strip() if sample_idx < len(row) else ""
            if code in st.session_state.retorno_lista:
                rows_idx.append(row_number)
                os_vals.append(st.session_state.retorno_lista[code])
                rows_data.append(list(row))
                found.add(code)

        all_codes = list(st.session_state.retorno_lista.keys())
        missing = [code for code in all_codes if code not in found]

        if missing:
            st.warning(
                "As seguintes amostras não foram localizadas e não serão atualizadas: "
                + ", ".join(missing)
            )
        if not rows_idx:
            st.stop()

    today = datetime.now().strftime(DATE_FMT)
    with st.spinner("Gravando o retorno no Google Sheets..."):
        update_rows(rows_idx, today, os_vals)

    status_idx = _col_to_idx(STATUS_COL)
    date_idx = _col_to_idx(DATE_COL)
    required_width = max(len(header), status_idx + 1, date_idx + 1, os_idx + 1)
    export_header = list(header) + [""] * (required_width - len(header))

    normalized_rows = []
    for row, os_value in zip(rows_data, os_vals):
        row += [""] * (required_width - len(row))
        row[status_idx] = STATUS_VAL
        row[date_idx] = today
        row[os_idx] = os_value
        normalized_rows.append(row)

    df_ok = pd.DataFrame(normalized_rows, columns=export_header)

    with st.spinner("Gerando a planilha Excel..."):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_ok.to_excel(writer, index=False, sheet_name="Amostras")
            if missing:
                pd.DataFrame(
                    [
                        {
                            "Amostra": code,
                            "OS informada": st.session_state.retorno_lista[code],
                        }
                        for code in missing
                    ]
                ).to_excel(writer, index=False, sheet_name="Nao_Encontradas")
        buffer.seek(0)

    message = f"✔️ {len(df_ok)} amostra(s) atualizada(s) e exportada(s)."
    if missing:
        message += f" {len(missing)} amostra(s) não encontrada(s)."
    st.success(message)

    st.download_button(
        "⬇️ Baixar Excel",
        data=buffer,
        file_name=f"retorno_amostras_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
