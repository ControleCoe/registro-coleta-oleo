from __future__ import annotations

import io
import time
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError

from oleo_utils import SPREADSHEET_ID, SHEET_NAME, _get_sheets_service
from loader_utils import pacman_loader

STATUS_COL = "AF"
DATE_COL = "AG"
OS_COL = "AH"
SAMPLE_COL = "G"
STATUS_VAL = "Retorno 1241"
DATE_FMT = "%d/%m/%Y"

RETURN_SHEET_NAME = "RETORNO"
LOCAL_OPERATION_COL = "D"
UGD_COL = "E"
RESPONSIBLE_COL = "F"
SERIAL_COL = "H"

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display: none;}
    .block-container {padding-top: 1.2rem;}
    .stButton > button {border-radius: 10px;}

    div[data-testid="stDownloadButton"] button {
        background: #38a34f !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background: #2f8f46 !important;
        color: #ffffff !important;
        border: none !important;
    }
    div[data-testid="stDownloadButton"] button * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    div[data-testid="stTextInput"] input {
        text-transform: uppercase;
    }

    .sample-white-card {
        background: #ffffff;
        border: 1px solid rgba(47, 143, 70, .22);
        border-radius: 10px;
        padding: .82rem 1rem;
        min-height: 44px;
        display: flex;
        align-items: center;
        color: #1f6531;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-weight: 700;
        box-shadow: 0 5px 15px rgba(47, 143, 70, .08);
    }
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


def _unique_nonempty(values: List[str]) -> List[str]:
    unique_values = []
    seen = set()

    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_values.append(normalized)

    return unique_values


def _build_return_block(
    rows_data: List[List[str]],
    today: str,
    launcher_name: str,
    os_value: str,
) -> List[List[str]]:
    sample_idx = _col_to_idx(SAMPLE_COL)
    serial_idx = _col_to_idx(SERIAL_COL)
    local_idx = _col_to_idx(LOCAL_OPERATION_COL)
    ugd_idx = _col_to_idx(UGD_COL)
    responsible_idx = _col_to_idx(RESPONSIBLE_COL)

    samples = [
        str(row[sample_idx]).strip() if sample_idx < len(row) else ""
        for row in rows_data
    ]
    serials = [
        str(row[serial_idx]).strip() if serial_idx < len(row) else ""
        for row in rows_data
    ]
    local_operations = _unique_nonempty(
        [
            str(row[local_idx]).strip() if local_idx < len(row) else ""
            for row in rows_data
        ]
    )
    ugds = _unique_nonempty(
        [
            str(row[ugd_idx]).strip() if ugd_idx < len(row) else ""
            for row in rows_data
        ]
    )
    responsibles = _unique_nonempty(
        [
            str(row[responsible_idx]).strip()
            if responsible_idx < len(row)
            else ""
            for row in rows_data
        ]
    )

    local_reference = "; ".join(local_operations)
    ugd_reference = "; ".join(ugds)
    responsible_reference = "; ".join(responsibles)

    header = [
        "Data Retorno",
        "Local de operação",
        "UGD",
        "Responsável",
        "Lançador do retorno",
    ]
    values = [
        today,
        local_reference,
        ugd_reference,
        responsible_reference,
        launcher_name,
    ]

    sample_value = samples[0] if samples else ""
    serial_value = serials[0] if serials else ""

    header.extend(
        [
            "Nº de Amostra",
            "",
            "Nº de Série",
            "Nº da OS",
        ]
    )
    values.extend(
        [
            sample_value,
            "",
            serial_value,
            str(os_value or "").strip(),
        ]
    )

    return [header, values]


def _next_return_block_row() -> int:
    try:
        result = (
            _svc()
            .spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{RETURN_SHEET_NAME}!A:ZZ",
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Não foi possível consultar a aba {RETURN_SHEET_NAME}: {exc}"
        ) from exc

    values = result.get("values", [])

    if not values:
        return 1

    last_used_row = 0
    for row_number, row in enumerate(values, start=1):
        if any(str(cell or "").strip() for cell in row):
            last_used_row = row_number

    # Uma linha vazia separa cada bloco.
    return last_used_row + 2


def write_return_blocks_by_os(
    rows_data: List[List[str]],
    today: str,
    os_values: List[str],
    launcher_name: str,
) -> List[int]:
    if len(rows_data) != len(os_values):
        raise RuntimeError(
            "Inconsistência interna: dados das amostras e OS não correspondem."
        )

    grouped_rows: dict[str, List[List[str]]] = {}

    for row, os_value in zip(rows_data, os_values):
        normalized_os = str(os_value or "").strip()

        if not normalized_os:
            raise RuntimeError(
                "Foi encontrada uma amostra sem Ordem de Serviço."
            )

        grouped_rows.setdefault(normalized_os, []).append(row)

    next_row = _next_return_block_row()
    created_rows: List[int] = []

    for os_value, grouped_data in grouped_rows.items():
        block = _build_return_block(
            grouped_data,
            today,
            launcher_name,
            os_value,
        )

        try:
            (
                _svc()
                .spreadsheets()
                .values()
                .update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{RETURN_SHEET_NAME}!A{next_row}",
                    valueInputOption="RAW",
                    body={"values": block},
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                f"Não foi possível gravar o bloco da OS {os_value} "
                f"na aba {RETURN_SHEET_NAME}: {exc}"
            ) from exc

        created_rows.append(next_row)

        # Cada bloco ocupa duas linhas: cabeçalho e dados.
        # A próxima OS começa após uma linha vazia.
        next_row += len(block) + 1

    return created_rows


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
st.session_state.setdefault("retorno_ultimo_fingerprint", "")
st.session_state.setdefault("retorno_ultimo_processamento_em", 0.0)
st.session_state.setdefault("retorno_limpar_campos", False)
st.session_state.setdefault("retorno_confirmacao_aberta", False)
st.session_state.setdefault("retorno_lancador", "")
st.session_state.setdefault("retorno_lancador_msg", "")
st.session_state.setdefault("retorno_limpar_lancador", False)

if st.session_state.retorno_limpar_lancador:
    st.session_state.retorno_lancador = ""
    st.session_state.retorno_limpar_lancador = False

if st.session_state.retorno_limpar_campos:
    st.session_state.retorno_codigo = ""
    st.session_state.retorno_os = ""
    st.session_state.retorno_limpar_campos = False


def _processing_fingerprint(items: dict[str, str]) -> str:
    normalized = sorted(
        (str(code).strip(), str(os_value).strip())
        for code, os_value in items.items()
    )
    return "|".join(f"{code}:{os_value}" for code, os_value in normalized)


def _validate_launcher_name(name: str) -> str:
    normalized = " ".join(str(name or "").strip().split())

    if any(character.isdigit() for character in normalized):
        return "O nome do lançador não pode conter números."

    words = [
        word
        for word in normalized.replace("-", " ").replace("'", " ").split()
        if word
    ]

    if len(words) < 2:
        return "Informe o nome e o sobrenome do lançador."

    if not all(
        all(character.isalpha() for character in word)
        for word in words
    ):
        return "Informe apenas letras no nome do lançador."

    return ""


def _sanitize_numeric_field(key: str, max_length: int) -> None:
    raw_value = str(st.session_state.get(key, "") or "")
    st.session_state[key] = "".join(
        character for character in raw_value if character.isdigit()
    )[:max_length]


def _find_sample_and_os(code: str, os_value: str) -> tuple[str, str]:
    try:
        sheet = fetch_sheet()
    except Exception as exc:
        raise RuntimeError(f"Não foi possível consultar o Google Sheets: {exc}") from exc

    if not sheet:
        raise RuntimeError("A aba da planilha está vazia.")

    _, *data = sheet
    sample_idx = _col_to_idx(SAMPLE_COL)
    os_idx = _col_to_idx(OS_COL)

    code = str(code or "").strip()
    os_value = str(os_value or "").strip()

    for row in data:
        row_code = str(row[sample_idx]).strip() if sample_idx < len(row) else ""
        row_os = str(row[os_idx]).strip() if os_idx < len(row) else ""

        if code and os_value:
            if row_code == code and row_os == os_value:
                return row_code, row_os
        elif code:
            if row_code == code:
                return row_code, row_os
        elif os_value:
            if row_os == os_value:
                return row_code, row_os

    if code and os_value:
        raise RuntimeError(
            "A combinação entre Código da amostra e Ordem de Serviço não foi encontrada."
        )
    if code:
        raise RuntimeError("Código da amostra não encontrado.")
    raise RuntimeError("Ordem de Serviço não encontrada.")


def add_item() -> None:
    _sanitize_numeric_field("retorno_codigo", 9)
    _sanitize_numeric_field("retorno_os", 6)

    code = st.session_state.retorno_codigo.strip()
    os_value = st.session_state.retorno_os.strip()

    if not code and not os_value:
        st.session_state.retorno_msg = (
            "Informe o Código da amostra ou a Ordem de Serviço."
        )
        return

    if code and len(code) != 9:
        st.session_state.retorno_msg = (
            "O código da amostra deve conter exatamente 9 números."
        )
        return

    if os_value and len(os_value) != 6:
        st.session_state.retorno_msg = (
            "A Ordem de Serviço deve conter exatamente 6 números."
        )
        return

    try:
        found_code, found_os = _find_sample_and_os(code, os_value)
    except Exception as exc:
        st.session_state.retorno_msg = str(exc)
        return

    if not found_code:
        st.session_state.retorno_msg = (
            "A Ordem de Serviço foi encontrada, mas não possui Código da amostra."
        )
        return

    if not found_os:
        st.session_state.retorno_msg = (
            "O Código da amostra foi encontrado, mas não possui Ordem de Serviço."
        )
        return

    if found_code in st.session_state.retorno_lista:
        st.session_state.retorno_msg = (
            f"A amostra {found_code} já foi adicionada."
        )
        return

    st.session_state.retorno_lista[found_code] = found_os
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
        c1.markdown(
            f'<div class="sample-white-card">{code}</div>',
            unsafe_allow_html=True,
        )
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
    process_request = st.button(
        "📥 Processar retorno",
        type="primary",
        use_container_width=True,
    )

if process_request:
    if not st.session_state.retorno_lista:
        st.error("A lista está vazia.")
    else:
        st.session_state.retorno_confirmacao_aberta = True
        st.session_state.retorno_lancador_msg = ""

generate = False
launcher_name = ""

if st.session_state.retorno_confirmacao_aberta:
    with st.container(border=True):
        st.subheader("Confirmar lançamento do retorno")
        st.caption(
            "Informe o nome e o sobrenome da pessoa responsável "
            "por lançar este retorno."
        )

        st.text_input(
            "Nome e sobrenome do lançador",
            key="retorno_lancador",
            placeholder="Ex.: Francisco Oliveira",
        )

        if st.session_state.retorno_lancador_msg:
            st.warning(st.session_state.retorno_lancador_msg)

        confirm_col, cancel_col = st.columns(2)

        with confirm_col:
            confirm_launch = st.button(
                "✅ Confirmar lançamento",
                type="primary",
                use_container_width=True,
            )

        with cancel_col:
            cancel_launch = st.button(
                "Cancelar",
                use_container_width=True,
            )

        if cancel_launch:
            st.session_state.retorno_confirmacao_aberta = False
            st.session_state.retorno_lancador_msg = ""
            st.session_state.retorno_limpar_lancador = True
            st.rerun()

        if confirm_launch:
            launcher_name = " ".join(
                str(st.session_state.retorno_lancador or "").strip().split()
            ).upper()
            validation_message = _validate_launcher_name(launcher_name)

            if validation_message:
                st.session_state.retorno_lancador_msg = validation_message
            else:
                st.session_state.retorno_lancador_msg = ""
                generate = True

if generate:
    if not st.session_state.retorno_lista:
        st.error("A lista está vazia.")
        st.stop()

    current_fingerprint = _processing_fingerprint(
        st.session_state.retorno_lista
    )
    current_time = time.monotonic()

    # Impede que o mesmo clique/rerun grave o mesmo lote duas vezes.
    if (
        current_fingerprint
        and current_fingerprint
        == st.session_state.retorno_ultimo_fingerprint
        and current_time
        - float(st.session_state.retorno_ultimo_processamento_em)
        < 30
    ):
        st.warning(
            "Este retorno já está sendo processado. "
            "A gravação duplicada foi bloqueada."
        )
        st.stop()

    # A trava é registrada antes de qualquer escrita no Google Sheets.
    st.session_state.retorno_ultimo_fingerprint = current_fingerprint
    st.session_state.retorno_ultimo_processamento_em = current_time

    with pacman_loader("Consultando a planilha..."):
        try:
            sheet = fetch_sheet()
        except Exception as exc:
            st.session_state.retorno_ultimo_fingerprint = ""
            st.session_state.retorno_ultimo_processamento_em = 0.0
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
    with pacman_loader("Gravando o retorno no Google Sheets..."):
        update_rows(rows_idx, today, os_vals)

    with pacman_loader("Criando os blocos na aba RETORNO..."):
        try:
            return_block_rows = write_return_blocks_by_os(
                rows_data,
                today,
                os_vals,
                launcher_name,
            )
        except Exception as exc:
            st.session_state.retorno_ultimo_fingerprint = ""
            st.session_state.retorno_ultimo_processamento_em = 0.0
            st.error(str(exc))
            st.stop()

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

    with pacman_loader("Gerando a planilha Excel..."):
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

    first_row = return_block_rows[0] if return_block_rows else 0
    message = (
        f"✔️ {len(df_ok)} amostra(s) atualizada(s) e exportada(s). "
        f"{len(return_block_rows)} bloco(s) criado(s) na aba "
        f"{RETURN_SHEET_NAME}, iniciando na linha {first_row}."
    )
    if missing:
        message += f" {len(missing)} amostra(s) não encontrada(s)."
    st.success(message)

    # A lista é limpa após o processamento para evitar um segundo envio acidental.
    # Os campos são limpos no próximo rerun, antes de os widgets serem criados.
    st.session_state.retorno_lista.clear()
    st.session_state.retorno_msg = ""
    st.session_state.retorno_limpar_campos = True
    st.session_state.retorno_confirmacao_aberta = False
    st.session_state.retorno_lancador_msg = ""
    st.session_state.retorno_limpar_lancador = True

    st.download_button(
        "⬇️ Baixar Excel",
        data=buffer,
        file_name=f"retorno_amostras_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
