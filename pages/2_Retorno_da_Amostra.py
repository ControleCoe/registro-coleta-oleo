from __future__ import annotations

import io
import json
import time
from datetime import datetime
from pathlib import Path
from urllib import request
from uuid import uuid4
from typing import List
from zoneinfo import ZoneInfo
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
from lxml import etree

from oleo_utils import (
    SPREADSHEET_ID,
    SHEET_NAME,
    _get_sheets_service,
    _fetch_main_sheet_cached,
    _clear_main_sheet_cache,
)
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
FLEET_COL = "I"
WORD_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "modelo_envio_amostras_oleo.docx"
)

STOCK_SHEETS_ENDPOINT = "https://script.google.com/macros/s/AKfycbzUtD0MyAr_iZ5IybtZ41mZQtiiiUBoTvUWIzEgisjgrpxeDGMDaw1q26PRTwh6E0Eixw/exec"
KIT_CONTRACT_MATERIAL = "KIT CONTRATO"


def baixar_kit_contrato_por_retorno(localidade: str, quantidade: int) -> None:
    """Registra a baixa automática do Kit somente após o retorno ser confirmado."""
    kits_utilizados = max(0, int(quantidade or 0))
    if not kits_utilizados:
        return

    agora = datetime.now(ZoneInfo("America/Manaus"))
    movimento = {
        "id": str(uuid4()),
        "type": "Baixa comum",
        "material": KIT_CONTRACT_MATERIAL,
        "measure": "",
        "quantity": kits_utilizados,
        "responsible": str(localidade or "LOCALIDADE").strip().upper(),
        "date": agora.strftime("%Y-%m-%d"),
        "time": agora.strftime("%H:%M:%S"),
        "origin": "retorno-amostra",
        "notes": (
            f"[HORA:{agora.strftime('%H:%M:%S')}] Baixa automática de "
            f"{kits_utilizados} KIT CONTRATO por retorno de amostra"
        ),
    }
    requisicao = request.Request(
        STOCK_SHEETS_ENDPOINT,
        data=json.dumps(movimento).encode("utf-8"),
        headers={"Content-Type": "text/plain;charset=utf-8"},
        method="POST",
    )
    with request.urlopen(requisicao, timeout=15) as response:
        resposta = response.read().decode("utf-8")
    if resposta:
        resultado = json.loads(resposta)
        if isinstance(resultado, dict) and resultado.get("ok") is False:
            raise RuntimeError(resultado.get("error") or "Falha ao baixar o Kit")


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
    # Cache global de curta duração: vários usuários reutilizam a mesma leitura.
    return _fetch_main_sheet_cached()


def _unique_nonempty(values: List[str]) -> List[str]:
    unique_values = []
    seen = set()

    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_values.append(normalized)

    return unique_values


def _normalize_locality(value: str) -> str:
    """Normaliza nomes equivalentes de localidades para a mesma referência."""
    locality = " ".join(str(value or "").strip().split()).upper()
    for prefix in ("UTE - ", "UTE-", "UTE – ", "UTE—", "UTE "):
        if locality.startswith(prefix):
            locality = locality[len(prefix):].strip(" -–—")
            break

    accents = str.maketrans("ÁÀÂÃÉÊÍÓÔÕÚÜÇ", "AAAAEEIOOOUUC")
    key = locality.translate(accents)
    key = " ".join(key.replace("-", " ").split())

    aliases = {
        "CASTANHO 27": "CASTANHO I KM 27",
        "CASTANHO KM 27": "CASTANHO I KM 27",
        "CASTANHO I 27": "CASTANHO I KM 27",
        "CASTANHO I KM 27": "CASTANHO I KM 27",
        "CASTANHO 100": "CASTANHO II KM 100",
        "CASTANHO KM 100": "CASTANHO II KM 100",
        "CASTANHO II 100": "CASTANHO II KM 100",
        "CASTANHO II KM 100": "CASTANHO II KM 100",
        "VILA BELO MONTE": "BELO MONTE",
        "VILA URUCURITUBA": "VILA DE URUCURITUBA",
        "SAO SEBASTIAO DO UATUMA": "S.S. DE UATUMÃ",
        "SANTA ISABEL DO RIO NEGRO": "SANTA ISABEL DO RN",
    }
    return aliases.get(key, locality)


def _row_value(row: List[str], column: str) -> str:
    index = _col_to_idx(column)
    return str(row[index]).strip() if index < len(row) else ""


def _resolve_locality(row: List[str], all_rows: List[List[str]]) -> str:
    direct_locality = _normalize_locality(_row_value(row, LOCAL_OPERATION_COL))
    if direct_locality:
        return direct_locality

    serial = _row_value(row, SERIAL_COL)
    fleet = _row_value(row, FLEET_COL)

    # Registros recentes podem vir sem o local preenchido. Nesse caso, usa o
    # histórico do mesmo equipamento, priorizando o número de série e depois a frota.
    for reference_value, column in ((serial, SERIAL_COL), (fleet, FLEET_COL)):
        if not reference_value:
            continue
        for candidate in reversed(all_rows):
            if _row_value(candidate, column) != reference_value:
                continue
            historical_locality = _normalize_locality(
                _row_value(candidate, LOCAL_OPERATION_COL)
            )
            if historical_locality:
                return historical_locality

    return ""


def _batch_locality(rows_data: List[List[str]]) -> str:
    local_idx = _col_to_idx(LOCAL_OPERATION_COL)
    localities = _unique_nonempty(
        [
            _normalize_locality(row[local_idx]) if local_idx < len(row) else ""
            for row in rows_data
        ]
    )
    return " / ".join(localities).upper() or "LOCALIDADE NÃO INFORMADA"


def _batch_identification(locality: str, sample_count: int) -> str:
    sample_word = "AMOSTRA" if sample_count == 1 else "AMOSTRAS"
    return f"{locality} - {sample_count} {sample_word}"


def _safe_file_name(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    return "".join("-" if character in forbidden else character for character in value)


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
WORD_TAG = f"{{{WORD_NS}}}"


def _word_run(text: str, *, bold: bool, color: str, size: int):
    run = etree.Element(f"{WORD_TAG}r")
    properties = etree.SubElement(run, f"{WORD_TAG}rPr")
    fonts = etree.SubElement(properties, f"{WORD_TAG}rFonts")
    fonts.set(f"{WORD_TAG}ascii", "Arial")
    fonts.set(f"{WORD_TAG}hAnsi", "Arial")
    fonts.set(f"{WORD_TAG}cs", "Arial")
    if bold:
        etree.SubElement(properties, f"{WORD_TAG}b")
    color_element = etree.SubElement(properties, f"{WORD_TAG}color")
    color_element.set(f"{WORD_TAG}val", color)
    size_element = etree.SubElement(properties, f"{WORD_TAG}sz")
    size_element.set(f"{WORD_TAG}val", str(size))
    size_complex = etree.SubElement(properties, f"{WORD_TAG}szCs")
    size_complex.set(f"{WORD_TAG}val", str(size))
    text_element = etree.SubElement(run, f"{WORD_TAG}t")
    if text.startswith(" ") or text.endswith(" "):
        text_element.set(f"{{{XML_NS}}}space", "preserve")
    text_element.text = text
    return run


def _word_paragraph_properties(paragraph, *, centered: bool) -> None:
    properties = paragraph.find(f"{WORD_TAG}pPr")
    if properties is None:
        properties = etree.Element(f"{WORD_TAG}pPr")
        paragraph.insert(0, properties)

    for tag in ("jc", "spacing"):
        for existing in properties.findall(f"{WORD_TAG}{tag}"):
            properties.remove(existing)

    alignment = etree.SubElement(properties, f"{WORD_TAG}jc")
    alignment.set(f"{WORD_TAG}val", "center" if centered else "left")
    if not centered:
        spacing = etree.SubElement(properties, f"{WORD_TAG}spacing")
        spacing.set(f"{WORD_TAG}after", "140")


def _replace_word_paragraph(paragraph, runs, *, centered: bool) -> None:
    for child in list(paragraph):
        if child.tag != f"{WORD_TAG}pPr":
            paragraph.remove(child)
    _word_paragraph_properties(paragraph, centered=centered)
    for run in runs:
        paragraph.append(run)


def _set_word_paragraph_text(paragraph, text: str) -> None:
    """Troca apenas o texto e preserva toda a formatação do modelo."""
    text_nodes = paragraph.xpath(".//w:t", namespaces={"w": WORD_NS})
    if not text_nodes:
        return
    text_nodes[0].text = text
    for text_node in text_nodes[1:]:
        text_node.text = ""


def _build_word_document(
    locality: str,
    sample_count: int,
    request_date: str,
) -> io.BytesIO:
    if not WORD_TEMPLATE_PATH.exists():
        raise RuntimeError("O modelo Word de envio de amostras não foi encontrado.")

    output = io.BytesIO()
    with ZipFile(WORD_TEMPLATE_PATH, "r") as source:
        document_xml = source.read("word/document.xml")
        root = etree.fromstring(document_xml)
        namespace = {"w": WORD_NS}
        tables = root.xpath(".//w:tbl", namespaces=namespace)
        if not tables:
            raise RuntimeError("O modelo Word não possui a tabela esperada.")

        cells = tables[0].xpath(".//w:tc", namespaces=namespace)
        if len(cells) < 2:
            raise RuntimeError("O modelo Word de envio de amostras está inválido.")

        replacements = {"ute": 0, "quantity": 0, "date": 0}
        quantity_text = f"{sample_count:02d} AMOSTRAS DE ÓLEO"
        date_text = f"DATA: {request_date}"

        for paragraph in root.xpath(".//w:p", namespaces=namespace):
            current_text = "".join(
                node.text or ""
                for node in paragraph.xpath(".//w:t", namespaces=namespace)
            ).strip()
            normalized = current_text.upper().replace("Ó", "O")

            if normalized in {"UTE", "UTE -"}:
                _set_word_paragraph_text(paragraph, f"UTE - {locality}")
                replacements["ute"] += 1
            elif normalized == "00 AMOSTRAS DE OLEO":
                _set_word_paragraph_text(paragraph, quantity_text)
                replacements["quantity"] += 1
            elif normalized == "DATA: 00 / 00 / 2026":
                _set_word_paragraph_text(paragraph, date_text)
                replacements["date"] += 1

        if any(count != 2 for count in replacements.values()):
            raise RuntimeError(
                "O modelo Word não possui os dois campos esperados de UTE, "
                "quantidade e data."
            )

        updated_xml = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        with ZipFile(output, "w") as destination:
            for item in source.infolist():
                data = updated_xml if item.filename == "word/document.xml" else source.read(item.filename)
                destination.writestr(item, data)

    output.seek(0)
    return output


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
                range=f"{RETURN_SHEET_NAME}!A:Z",
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Falha ao consultar a aba {RETURN_SHEET_NAME}. "
            "Tente novamente em alguns segundos."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível acessar a aba {RETURN_SHEET_NAME}."
        ) from exc

    values = result.get("values", [])

    if not values:
        return 1

    last_used_row = 0
    for row_number, row in enumerate(values, start=1):
        if any(str(cell or "").strip() for cell in row):
            last_used_row = row_number

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
        _clear_main_sheet_cache()
    except HttpError as exc:
        st.error(f"❌ Falha ao gravar no Google Sheets: {exc}")
        st.stop()


def append_missing_samples(
    codes: List[str],
    today: str,
    header: List[str],
) -> tuple[List[List[str]], List[str]]:
    """Inclui no Geral as amostras digitadas que ainda não existem."""
    sample_idx = _col_to_idx(SAMPLE_COL)
    os_idx = _col_to_idx(OS_COL)
    locality_idx = _col_to_idx(LOCAL_OPERATION_COL)
    # A baixa só acontece depois de o retorno ser gravado com sucesso.
    # Cada amostra retornada consome um KIT da localidade que está logada.
    kit_localidade = str(
        st.session_state.get("localidade_acesso", "") or ""
    ).strip().upper()
    try:
        baixar_kit_contrato_por_retorno(kit_localidade, len(all_rows_data))
    except Exception as exc:
        st.warning(
            "O retorno foi registrado, mas não foi possível atualizar o saldo "
            f"do KIT CONTRATO agora: {exc}"
        )

    status_idx = _col_to_idx(STATUS_COL)
    date_idx = _col_to_idx(DATE_COL)
    width = max(len(header), sample_idx + 1, os_idx + 1, locality_idx + 1, status_idx + 1, date_idx + 1)
    rows: List[List[str]] = []
    os_values: List[str] = []

    for code in codes:
        row = [""] * width
        row[sample_idx] = code
        row[os_idx] = st.session_state.retorno_lista[code]
        row[locality_idx] = st.session_state.retorno_localidades.get(code, "")
        row[status_idx] = STATUS_VAL
        row[date_idx] = today
        rows.append(row)
        os_values.append(row[os_idx])

    try:
        _svc().spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:AH",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        _clear_main_sheet_cache()
    except HttpError as exc:
        raise RuntimeError(f"Não foi possível adicionar as novas amostras na planilha: {exc}") from exc

    return rows, os_values


st.session_state.setdefault("retorno_lista", {})
st.session_state.setdefault("retorno_localidades", {})
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


def _find_sample_and_os(code: str, os_value: str) -> tuple[str, str, str]:
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
        row_locality = _resolve_locality(row, data)

        if code and os_value:
            if row_code == code and row_os == os_value:
                return row_code, row_os, row_locality
        elif code:
            if row_code == code:
                return row_code, row_os, row_locality
        elif os_value:
            if row_os == os_value:
                return row_code, row_os, row_locality

    if code and os_value:
        raise RuntimeError(
            "A combinação entre Código da amostra e Ordem de Serviço não foi encontrada."
        )
    if code:
        raise RuntimeError("Código da amostra não encontrado.")
    raise RuntimeError("Ordem de Serviço não encontrada.")


def _os_already_processed(os_value: str) -> bool:
    """Retorna True quando a O.S. já recebeu retorno anteriormente."""
    target_os = str(os_value or "").strip()
    if not target_os:
        return False
    try:
        sheet = fetch_sheet()
    except Exception:
        # A validação normal da amostra exibirá o erro de conexão ao usuário.
        return False

    _, *data = sheet
    for row in data:
        if _row_value(row, OS_COL) != target_os:
            continue
        status = _row_value(row, STATUS_COL).upper()
        if status.startswith("RETORNO"):
            return True
    return False


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
        found_code, found_os, found_locality = _find_sample_and_os(code, os_value)
    except Exception:
        # Quando código e O.S. ainda não estiverem no Geral, aceita o lançamento.
        # Eles serão incluídos na planilha ao confirmar o retorno.
        if not (code and os_value):
            st.session_state.retorno_msg = (
                "Informe o Código da amostra e a Ordem de Serviço para cadastrar uma nova amostra."
            )
            return
        found_code = code
        found_os = os_value
        found_locality = st.session_state.get("localidade_acesso", "")

    found_locality = _normalize_locality(found_locality)
    access_locality = _normalize_locality(
        st.session_state.get("localidade_acesso", "")
    )

    if access_locality:
        if not found_locality:
            st.session_state.retorno_msg = (
                "Não foi possível confirmar a localidade desta O.S. "
                "Ela não pode ser adicionada neste acesso."
            )
            return
        if found_locality != access_locality:
            st.session_state.retorno_msg = (
                f"O acesso atual é de {access_locality}, mas esta O.S. "
                f"pertence a {found_locality}. A amostra não foi adicionada."
            )
            return

    listed_localities = _unique_nonempty(
        [
            _normalize_locality(value)
            for value in st.session_state.retorno_localidades.values()
            if value != "LOCALIDADE NÃO INFORMADA"
        ]
    )
    if listed_localities and found_locality not in listed_localities:
        st.session_state.retorno_msg = (
            f"A lista atual pertence a {listed_localities[0]}. "
            f"Não é permitido adicionar uma O.S. de {found_locality}. "
            "Limpe a lista para iniciar outra localidade."
        )
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
    st.session_state.retorno_localidades[found_code] = (
        _normalize_locality(found_locality) or "LOCALIDADE NÃO INFORMADA"
    )
    st.session_state.retorno_codigo = ""
    st.session_state.retorno_os = ""
    st.session_state.retorno_msg = ""


access_locality = _normalize_locality(
    st.session_state.get("localidade_acesso", "")
)
if access_locality:
    st.info(
        f"Acesso da localidade: **{access_locality}**. "
        "Somente amostras e O.S. desta localidade serão aceitas."
    )

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
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        c1.markdown(
            f'<div class="sample-white-card">{code}</div>',
            unsafe_allow_html=True,
        )
        c2.write(f"OS {os_value}")
        c3.write(st.session_state.retorno_localidades.get(
            code,
            "LOCALIDADE NÃO INFORMADA",
        ))
        if c4.button("Remover", key=f"retorno_rm_{code}"):
            st.session_state.retorno_lista.pop(code, None)
            st.session_state.retorno_localidades.pop(code, None)
            st.rerun()
else:
    st.info("Nenhuma amostra adicionada.")

col_clear, col_generate = st.columns(2)
with col_clear:
    if st.button("🗑️ Limpar lista", use_container_width=True):
        st.session_state.retorno_lista.clear()
        st.session_state.retorno_localidades.clear()
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
        today = datetime.now(ZoneInfo("America/Manaus")).strftime(DATE_FMT)
        all_rows_data = list(rows_data)
        all_os_vals = list(os_vals)

        if missing:
            try:
                new_rows, new_os_vals = append_missing_samples(missing, today, header)
            except Exception as exc:
                st.session_state.retorno_ultimo_fingerprint = ""
                st.session_state.retorno_ultimo_processamento_em = 0.0
                st.error(str(exc))
                st.stop()
            all_rows_data.extend(new_rows)
            all_os_vals.extend(new_os_vals)
            st.info(
                "Amostras não encontradas foram adicionadas normalmente à planilha: "
                + ", ".join(missing)
            )

        if not all_rows_data:
            st.stop()

    with pacman_loader("Gravando o retorno no Google Sheets..."):
        if rows_idx:
            update_rows(rows_idx, today, os_vals)

    with pacman_loader("Criando os blocos na aba RETORNO..."):
        try:
            return_block_rows = write_return_blocks_by_os(
                all_rows_data,
                today,
                all_os_vals,
                launcher_name,
            )
        except Exception as exc:
            st.session_state.retorno_ultimo_fingerprint = ""
            st.session_state.retorno_ultimo_processamento_em = 0.0
            st.error(
                "Não foi possível criar os blocos na aba RETORNO. "
                f"Detalhe: {exc}"
            )
            st.stop()

    status_idx = _col_to_idx(STATUS_COL)
    date_idx = _col_to_idx(DATE_COL)
    required_width = max(len(header), status_idx + 1, date_idx + 1, os_idx + 1)
    export_header = list(header) + [""] * (required_width - len(header))

    normalized_rows = []
    for row, os_value in zip(all_rows_data, all_os_vals):
        row += [""] * (required_width - len(row))
        row[status_idx] = STATUS_VAL
        row[date_idx] = today
        row[os_idx] = os_value
        normalized_rows.append(row)

    df_ok = pd.DataFrame(normalized_rows, columns=export_header)
    locality = _batch_locality(all_rows_data)
    access_locality = _normalize_locality(
        st.session_state.get("localidade_acesso", "")
    )
    if access_locality:
        locality = access_locality
    if locality == "LOCALIDADE NÃO INFORMADA":
        session_localities = _unique_nonempty(
            [
                _normalize_locality(value)
                for value in st.session_state.retorno_localidades.values()
                if value != "LOCALIDADE NÃO INFORMADA"
            ]
        )
        if session_localities:
            locality = " / ".join(session_localities)
    identification = _batch_identification(locality, len(df_ok))
    safe_identification = _safe_file_name(identification)

    with pacman_loader("Gerando a planilha Excel..."):
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            writer.book.set_properties(
                {
                    "title": identification,
                    "subject": identification,
                    "comments": "Retorno de amostras de óleo - Oliveira Energia",
                }
            )
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
        excel_buffer.seek(0)

    with pacman_loader("Gerando o documento Word..."):
        try:
            word_buffer = _build_word_document(
                locality,
                len(df_ok),
                today,
            )
        except Exception as exc:
            st.session_state.retorno_ultimo_fingerprint = ""
            st.session_state.retorno_ultimo_processamento_em = 0.0
            st.error(f"Não foi possível gerar o documento Word: {exc}")
            st.stop()

    first_row = return_block_rows[0] if return_block_rows else 0
    message = (
        f"✔️ {len(df_ok)} amostra(s) processada(s) e exportada(s). "
        f"{len(return_block_rows)} bloco(s) criado(s) na aba "
        f"{RETURN_SHEET_NAME}, iniciando na linha {first_row}."
    )
    if missing:
        message += f" {len(missing)} amostra(s) que não estavam na planilha foram adicionadas."
    st.success(message)

    # A lista é limpa após o processamento para evitar um segundo envio acidental.
    # Os campos são limpos no próximo rerun, antes de os widgets serem criados.
    st.session_state.retorno_lista.clear()
    st.session_state.retorno_localidades.clear()
    st.session_state.retorno_msg = ""
    st.session_state.retorno_limpar_campos = True
    st.session_state.retorno_confirmacao_aberta = False
    st.session_state.retorno_lancador_msg = ""
    st.session_state.retorno_limpar_lancador = True

    all_files_buffer = io.BytesIO()
    with ZipFile(all_files_buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{safe_identification}.xlsx",
            excel_buffer.getvalue(),
        )
        archive.writestr(
            f"{safe_identification}.docx",
            word_buffer.getvalue(),
        )
    all_files_buffer.seek(0)

    st.download_button(
        "⬇️ Baixar todos",
        data=all_files_buffer,
        file_name=f"{safe_identification}.zip",
        mime="application/zip",
        use_container_width=True,
    )
