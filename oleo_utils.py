
# ────────────────────────────────────────────────────────────────────────────────
# utils.py — funções auxiliares (Google Sheets, PDF e UI Streamlit)
# ────────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import io
import os
import re
import json

import cv2
import numpy as np
from math import ceil
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional

import qrcode
import httplib2
from fpdf import FPDF
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from barcode import Code128
from barcode.writer import ImageWriter

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ModuleNotFoundError:
    st = None  # permite importar utils.py sem Streamlit
    components = None

# ░░░ Config Google Sheets ░░░
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = "1VLDQUCO3Aw4ClAvhjkUsnBxG44BTjz-MjHK04OqPxYM"
SHEET_NAME = "Geral"

# ░░░ Rótulo e coluna de destino do novo campo O.S. ░░░
OS_FORM_LABEL = "Ordem de Serviço (O.S.)"
OS_TARGET_COL = "AH"  # coluna onde gravaremos a O.S. após o append A..AG
REGISTRANT_FORM_LABEL = "Responsável Pelo Registro"
REGISTRANT_TARGET_COL = "AI"
REGISTRATION_DATE_FORM_LABEL = "Data do Registro"
REGISTRATION_DATE_TARGET_COL = "AJ"

# ░░░ Localidades permitidas no campo "Local de operação" ░░░
OPERATION_LOCATIONS: List[str] = [
    "UTE-NOVO REMANSO",
    "UTE-MAUÉS",
    "UTE-BOCA DO ACRE",
    "UTE-CASTANHO II KM 100",
    "UTE-CASTANHO I KM 27",
    "UTE-MANAQUIRI",
    "UTE-BARCELOS",
    "UTE-BERURÍ",
    "UTE-LÁBREA",
    "UTE-NOVO AIRÃO",
    "UTE-BOA VISTA DO RAMOS",
    "UTE-BARREIRINHA",
    "UTE-VILA AMAZÔNIA",
    "UTE-NHAMUNDÁ",
    "UTE-LINDÓIA",
    "UTE-URUCARÁ",
    "UTE-NOVO CÉU",
    "UTE-URUCURITUBA",
    "UTE-CAREIRO DA VÁRZEA",
    "UTE-S.S. DE UATUMÃ",
    "UTE-PAUINI",
    "UTE-SANTA ISABEL DO RN",
    "UTE-CANUTAMA",
    "UTE-TAPAUÁ",
    "UTE-MOCAMBO",
    "UTE-CABURI",
    "UTE-PEDRAS",
    "UTE-AUGUSTO MONTENEGRO",
    "UTE-VILA DE URUCURITUBA",
    "UTE-SANTANA DO UATUMÃ",
    "UTE-PARAUÁ",
    "UTE-CARVOEIRO",
    "UTE-MOURA",
    "UTE-CUCUI",
    "UTE-IAUARETÊ",
    "UTE-ARARAS",
    "UTE-CAMPINAS",
    "UTE-CAVIANA",
    "UTE-SACAMBU",
    "UTE-TUIUÉ",
    "UTE-BELO MONTE",
    "UTE-ITAPURU",
]

# ░░░ Cabeçalhos EXATOS da planilha (A..AG), sem a coluna OS (AH) ░░░
SHEET_HEADERS_EXCL_OS: List[str] = [
    "Estado de Origem",
    "Cliente",
    "Data da coleta",
    "Local de operação",
    "UGD",
    "Responsável Pela Coleta",
    "n.º da Amostra",
    "n.º de série Equipamento",
    "Frota",
    "Horímetro do Óleo",
    "Houve troca de óleo após coleta?",
    "Troca de Filtro após coleta",
    "Houve mudança do local de operação?",
    "Fabricante",
    "Modelo",
    "Horímetro do Motor",
    "Houve complemento de óleo",
    "Se sim, quantos litros",
    "Amostra coletada",
    "Fabricante do Óleo",
    "Grau de viscosidade",
    "Nome",
    "Apresentou limalha no filtro ou na tela?",
    "Apresentou limalhas no bujão magnético?",
    "Equipamento apresentou ruído anormal?",
    "Existem vazamentos no sistema",
    "A temperatura de operação está normal?",
    "O desempenho do sistema está normal?",
    "Detalhes das anormalidades (caso Haja)",
    "Pessoa de contato",
    "Telefone",
    "Status",        # AF — vazio nesta etapa
    "Data Status"    # AG — vazio nesta etapa
]

# ░░░ Mapeia cada cabeçalho -> label do formulário (quando diferir) ░░░
SHEET_HEADER_TO_FORM: Dict[str, str] = {
    "Estado de Origem": "Estado de Origem",
    "Cliente": "Cliente",
    "Data da coleta": "Data da coleta",
    "Local de operação": "Local de operação:",
    "UGD": "UGD:",
    "Responsável Pela Coleta": "Responsável Pela Coleta:",
    "n.º da Amostra": "n.º da Amostra",
    "n.º de série Equipamento": "n.º de série:",
    "Frota": "Frota:",
    "Horímetro do Óleo": "Horímetro do Óleo:",
    "Houve troca de óleo após coleta?": "Houve troca de óleo após coleta?",
    "Troca de Filtro após coleta": "Trocado o filtro após coleta?",
    "Houve mudança do local de operação?": "Houve mudança do local de operação?",
    "Fabricante": "Fabricante do Equipamento:",
    "Modelo": "Modelo:",
    "Horímetro do Motor": "Horímetro do Motor",
    "Houve complemento de óleo": "Houve complemento de óleo?",
    "Se sim, quantos litros": "Se sim, quantos litros?",
    "Amostra coletada": "Amostra coletada:",
    "Fabricante do Óleo": "Fabricante:",  # seção Óleo
    "Grau de viscosidade": "Grau de viscosidade:",
    "Nome": "Nome:",
    "Apresentou limalha no filtro ou na tela?": "Apresentou limalha no filtro ou na tela?",
    "Apresentou limalhas no bujão magnético?": "Apresentou limalhas no bujão magnético?",
    "Equipamento apresentou ruído anormal?": "Equipamento apresentou ruído anormal?",
    "Existem vazamentos no sistema": "Existem vazamentos no sistema?",
    "A temperatura de operação está normal?": "A temperatura de operação está normal?",
    "O desempenho do sistema está normal?": "O desempenho do sistema está normal?",
    "Detalhes das anormalidades (caso Haja)": "Detalhes das anormalidades (caso Haja):",
    "Pessoa de contato": "Pessoa de contato:",
    "Telefone": "Telefone:",
    # "Status" e "Data Status" são vazios nesta etapa
}

# ░░░ Autenticação Google ░░░
def _authorize_google_sheets() -> Credentials:
    """Autoriza o Google Sheets no computador local e no Streamlit Cloud.

    Ordem de leitura:
    1. token.json local;
    2. GOOGLE_TOKEN nos Secrets do Streamlit;
    3. GOOGLE_TOKEN em variável de ambiente;
    4. fluxo OAuth local por GOOGLE_CLIENT_SECRET (compatibilidade).
    """
    token_path = "token.json"
    creds = None

    # 1) Execução local: utiliza o token salvo no projeto.
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    # 2) Streamlit Cloud: utiliza o JSON completo do token armazenado nos Secrets.
    if creds is None:
        token_json = None
        if st is not None:
            try:
                token_json = st.secrets.get("GOOGLE_TOKEN")
            except Exception:
                token_json = None
        if not token_json:
            token_json = os.getenv("GOOGLE_TOKEN")

        if token_json:
            try:
                token_info = json.loads(str(token_json))
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            except Exception as exc:
                raise RuntimeError("GOOGLE_TOKEN inválido nos Secrets do Streamlit.") from exc

    # Atualiza automaticamente o access token usando o refresh token.
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise RuntimeError("Não foi possível renovar as credenciais Google.") from exc

    # 3) Compatibilidade para primeira autorização local.
    if not creds or not creds.valid:
        client_secret_json = None
        if st is not None:
            try:
                client_secret_json = st.secrets.get("GOOGLE_CLIENT_SECRET")
            except Exception:
                client_secret_json = None
        if not client_secret_json:
            client_secret_json = os.getenv("GOOGLE_CLIENT_SECRET")

        if not client_secret_json:
            raise RuntimeError(
                "Credenciais Google ausentes. Defina GOOGLE_TOKEN nos Secrets do Streamlit."
            )

        from google_auth_oauthlib.flow import InstalledAppFlow
        try:
            client_config = json.loads(str(client_secret_json))
        except Exception as exc:
            raise RuntimeError("GOOGLE_CLIENT_SECRET inválido (JSON).") from exc

        # Este fluxo é destinado ao uso local, onde o navegador pode ser aberto.
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

    # Persiste o token atualizado quando houver permissão de escrita local.
    try:
        with open(token_path, "w", encoding="utf-8") as fp:
            fp.write(creds.to_json())
    except Exception:
        pass

    return creds

if st is not None:
    @st.cache_resource(show_spinner=False)
    def _get_sheets_service():
        # Evita que indisponibilidade do Google mantenha Cadastro ou Retorno
        # carregando indefinidamente.
        return build(
            "sheets",
            "v4",
            credentials=_authorize_google_sheets(),
            cache_discovery=False,
        )
else:
    def _get_sheets_service():
        return build(
            "sheets",
            "v4",
            credentials=_authorize_google_sheets(),
            cache_discovery=False,
        )


if st is not None:
    @st.cache_data(ttl=120, show_spinner=False)
    def _fetch_main_sheet_cached():
        """Lê a aba Geral uma vez e reaproveita o resultado por até 2 minutos."""
        result = (
            _get_sheets_service()
            .spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:AJ",
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
        return result.get("values", [])
else:
    def _fetch_main_sheet_cached():
        result = (
            _get_sheets_service()
            .spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:AJ",
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
        return result.get("values", [])


def _clear_main_sheet_cache():
    """Invalida a leitura compartilhada imediatamente após qualquer gravação."""
    clear = getattr(_fetch_main_sheet_cached, "clear", None)
    if callable(clear):
        clear()
    sample_lookup = globals().get("_fetch_sheet_header_and_samples")
    sample_clear = getattr(sample_lookup, "clear", None)
    if callable(sample_clear):
        sample_clear()

# ░░░ Estrutura do formulário (labels do formulário) ░░░
FORM_SECTIONS: List[Tuple[str, List[Tuple[str, Any]]]] = [
    (
        "Geral",
        [
            ("Estado de Origem", "AM"),
            ("Cliente", "Pie - Oliveira Energia"),
            ("Data da coleta", ""),
            ("Local de operação:", ""),
            ("UGD:", ""),
            ("Responsável Pela Coleta:", ""),
            (REGISTRANT_FORM_LABEL, ""),
            (REGISTRATION_DATE_FORM_LABEL, ""),
            ("n.º da Amostra", ""),           # obrigatório
            (OS_FORM_LABEL, ""),              # NOVO campo — lado a lado no PDF
        ],
    ),
    (
        "Equipamento",
        [
            ("n.º de série:", ""),
            ("Frota:", ""),
            ("Horímetro do Óleo:", "250 Horas"),
            ("Houve troca de óleo após coleta?", False),
            ("Trocado o filtro após coleta?", False),
            ("Houve mudança do local de operação?", False),
            ("Fabricante do Equipamento:", "Scania"),
            ("Modelo:", "DC13"),
            ("Horímetro do Motor", ""),
        ],
    ),
    (
        "Óleo",
        [
            ("Houve complemento de óleo?", False),
            ("Se sim, quantos litros?", ""),
            ("Amostra coletada:", "Motor"),
            ("Fabricante:", "Mobil"),                 # Fabricante do Óleo
            ("Grau de viscosidade:", "15W40"),
            ("Nome:", "Mobil Delvac"),
            ("Apresentou limalha no filtro ou na tela?", False),
            ("Apresentou limalhas no bujão magnético?", False),
            ("Equipamento apresentou ruído anormal?", False),
            ("Existem vazamentos no sistema?", False),
            ("A temperatura de operação está normal?", False),
            ("O desempenho do sistema está normal?", False),
            ("Detalhes das anormalidades (caso Haja):", ""),
        ],
    ),
    (
        "Contato",
        [
            ("Pessoa de contato:", "Francisco Sampaio"),
            ("Telefone:", "(92) 99437-6579"),
        ],
    ),
]

BOOL_LABELS = {
    label
    for _, questions in FORM_SECTIONS
    for label, default in questions
    if isinstance(default, bool)
}


def _build_base_defaults() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    for _, questions in FORM_SECTIONS:
        for label, default in questions:
            defaults[label] = default
    return defaults



BASE_FORM_DEFAULTS = _build_base_defaults()

def _resolve_access_location(access_locality: Any) -> str:
    """Converte o nome vindo do login para a UTE cadastrada no formulário."""
    raw = str(access_locality or "").strip().upper()
    if not raw or raw == "LABORATORIO":
        return ""

    def normalize(text: str) -> str:
        text = text.replace("Á", "A").replace("À", "A").replace("Â", "A").replace("Ã", "A")
        text = text.replace("É", "E").replace("Ê", "E").replace("Í", "I")
        text = text.replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
        text = text.replace("Ú", "U").replace("Ü", "U").replace("Ç", "C")
        return re.sub(r"[^A-Z0-9]+", " ", text).strip()

    key = normalize(raw.removeprefix("UTE-"))
    aliases = {
        "CASTANHO 27": "UTE-CASTANHO I KM 27",
        "CASTANHO KM 27": "UTE-CASTANHO I KM 27",
        "CASTANHO I 27": "UTE-CASTANHO I KM 27",
        "CASTANHO I KM 27": "UTE-CASTANHO I KM 27",
        "CASTANHO 100": "UTE-CASTANHO II KM 100",
        "CASTANHO KM 100": "UTE-CASTANHO II KM 100",
        "CASTANHO II 100": "UTE-CASTANHO II KM 100",
        "CASTANHO II KM 100": "UTE-CASTANHO II KM 100",
        "VILA BELO MONTE": "UTE-BELO MONTE",
        "BELO MONTE": "UTE-BELO MONTE",
        "VILA URUCURITUBA": "UTE-VILA DE URUCURITUBA",
        "SÃO SEBASTIÃO DO UATUMÃ": "UTE-S.S. DE UATUMÃ",
        "SAO SEBASTIAO DO UATUMA": "UTE-S.S. DE UATUMÃ",
        "SANTA ISABEL DO RIO NEGRO": "UTE-SANTA ISABEL DO RN",
    }
    if key in aliases:
        return aliases[key]

    for option in OPERATION_LOCATIONS:
        if normalize(option.removeprefix("UTE-")) == key:
            return option
    return ""

# ░░░ Helpers de estado do formulário ░░░
def _parse_date_value(value: Any) -> Optional[date]:
    """Converte valores da planilha/formulário para o seletor de data."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _apply_form_values(values: Dict[str, Any]) -> None:
    if st is None:
        return
    form_values = st.session_state.setdefault("form_values", {})
    for label, value in values.items():
        form_values[label] = value
        if isinstance(value, bool):
            key_yes = f"{label}_yes"
            key_no = f"{label}_no"
            st.session_state[key_yes] = bool(value)
            st.session_state[key_no] = not bool(value)
        elif label == "Data da coleta":
            st.session_state[label] = _parse_date_value(value)
        else:
            st.session_state[label] = "" if value is None else str(value)


def _queue_form_updates(values: Dict[str, Any]) -> None:
    """Armazena atualizações para aplicação segura após o próximo rerun."""
    if st is None:
        return

    form_values = st.session_state.setdefault("form_values", BASE_FORM_DEFAULTS.copy())
    form_values.update(values)

    pending = st.session_state.setdefault("_pending_form_values", {})
    pending.update(values)


def sync_sample_number(sample_number: str) -> None:
    """Atualiza o campo da amostra no estado do formulário e widgets."""
    if st is None:
        return
    _queue_form_updates({"n.º da Amostra": sample_number})


def _reset_form_defaults(keep_sample: Optional[str] = None) -> None:
    defaults = BASE_FORM_DEFAULTS.copy()
    if keep_sample is not None:
        defaults["n.º da Amostra"] = keep_sample
    if st is None:
        return
    st.session_state["form_values"] = defaults
    _queue_form_updates(defaults)


def _ensure_form_state() -> None:
    if st is None:
        return
    if "form_values" not in st.session_state:
        st.session_state["form_values"] = BASE_FORM_DEFAULTS.copy()
        _apply_form_values(st.session_state["form_values"])
    pending_updates = st.session_state.pop("_pending_form_values", None)
    if pending_updates:
        st.session_state["form_values"].update(pending_updates)
        _apply_form_values(pending_updates)
    st.session_state.setdefault("sample_row_index", None)
    st.session_state.setdefault("sample_lookup_status", None)
    st.session_state.setdefault("sample_lookup_message", "")
    st.session_state.setdefault("sample_lookup_warning", None)
    st.session_state.setdefault("sample_existing_extras", {})
    st.session_state.setdefault("sample_last_loaded_number", "")


def _column_letter_to_index(col: str) -> int:
    col = col.strip().upper()
    if not col:
        raise ValueError("Coluna vazia")
    idx = 0
    for ch in col:
        if not ch.isalpha():
            raise ValueError(f"Coluna inválida: {col}")
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _coerce_sheet_value(label: str, value: Any) -> Any:
    if label in BOOL_LABELS:
        text = "" if value is None else str(value).strip().lower()
        if text in {"sim", "s", "true", "1", "yes"}:
            return True
        if text in {"não", "nao", "n", "false", "0", "no"}:
            return False
        base_default = BASE_FORM_DEFAULTS.get(label)
        return bool(base_default) if isinstance(base_default, bool) else False
    return "" if value is None else str(value)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_sheet_header_and_samples() -> Tuple[List[str], List[str]]:
    """Lê somente o cabeçalho e a coluna de etiquetas do cadastro."""
    service = _get_sheets_service()
    header_result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1:AJ1",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    sample_result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!G:G",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    header = (header_result.get("values") or [[]])[0]
    samples = [str(row[0]).strip() if row else "" for row in sample_result.get("values", [])]
    return list(header), samples


def _fetch_sample_from_sheets(sample_number: str) -> Optional[Tuple[int, Dict[str, Any], int, Dict[str, str]]]:
    try:
        header, samples = _fetch_sheet_header_and_samples()
    except HttpError as exc:
        raise RuntimeError(f"Erro ao consultar planilha: {exc}") from exc

    if not header:
        return None

    header_map = {name: idx for idx, name in enumerate(header)}
    sample_col_idx = header_map.get("n.º da Amostra")
    if sample_col_idx is None:
        raise RuntimeError("Cabeçalho 'n.º da Amostra' não encontrado na planilha.")

    os_col_idx = header_map.get(OS_FORM_LABEL)
    if os_col_idx is None:
        os_col_idx = _column_letter_to_index(OS_TARGET_COL)

    matches = [
        row_number
        for row_number, value in enumerate(samples, start=1)
        if row_number > 1 and value == sample_number
    ]

    if not matches:
        return None

    row_idx = matches[-1]
    try:
        row_result = _get_sheets_service().spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A{row_idx}:AJ{row_idx}",
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
    except HttpError as exc:
        raise RuntimeError(f"Erro ao carregar a amostra: {exc}") from exc
    row_values = (row_result.get("values") or [[]])[0]
    form_data: Dict[str, Any] = {}
    extras: Dict[str, str] = {}
    for sheet_header, form_label in SHEET_HEADER_TO_FORM.items():
        col_idx = header_map.get(sheet_header)
        if col_idx is None:
            continue
        cell_value = row_values[col_idx] if col_idx < len(row_values) else ""
        form_data[form_label] = _coerce_sheet_value(form_label, cell_value)

    if os_col_idx is not None:
        cell_value = row_values[os_col_idx] if os_col_idx < len(row_values) else ""
        form_data[OS_FORM_LABEL] = "" if cell_value is None else str(cell_value)

    registrant_col_idx = header_map.get(REGISTRANT_FORM_LABEL)
    if registrant_col_idx is None:
        registrant_col_idx = _column_letter_to_index(REGISTRANT_TARGET_COL)
    cell_value = row_values[registrant_col_idx] if registrant_col_idx < len(row_values) else ""
    form_data[REGISTRANT_FORM_LABEL] = "" if cell_value is None else str(cell_value)

    registration_date_col_idx = header_map.get(REGISTRATION_DATE_FORM_LABEL)
    if registration_date_col_idx is None:
        registration_date_col_idx = _column_letter_to_index(REGISTRATION_DATE_TARGET_COL)
    cell_value = (
        row_values[registration_date_col_idx]
        if registration_date_col_idx < len(row_values)
        else ""
    )
    form_data[REGISTRATION_DATE_FORM_LABEL] = (
        "" if cell_value is None else str(cell_value)
    )

    for header_name in ("Status", "Data Status"):
        idx = header_map.get(header_name)
        if idx is not None and idx < len(row_values):
            extras[header_name] = "" if row_values[idx] is None else str(row_values[idx])

    return row_idx, form_data, len(matches), extras


def _handle_sample_change() -> None:
    if st is None:
        return
    raw_value = st.session_state.get("n.º da Amostra", "")
    sample_value = re.sub(r"\D", "", str(raw_value))[:9]
    st.session_state["n.º da Amostra"] = sample_value
    st.session_state.setdefault("form_values", {})["n.º da Amostra"] = sample_value
    st.session_state["sample_lookup_warning"] = None

    # A busca na planilha só é executada quando o número estiver completo.
    if sample_value and len(sample_value) != 9:
        st.session_state["sample_row_index"] = None
        st.session_state["sample_lookup_status"] = None
        st.session_state["sample_lookup_message"] = ""
        st.session_state["sample_existing_extras"] = {}
        st.session_state["sample_last_loaded_number"] = ""
        return

    if sample_value:
        try:
            fetched = _fetch_sample_from_sheets(sample_value)
        except Exception as exc:  # noqa: BLE001
            st.session_state["sample_row_index"] = None
            st.session_state["sample_lookup_status"] = "error"
            st.session_state["sample_lookup_message"] = f"Erro ao buscar amostra: {exc}"
            return

        if fetched is None:
            _reset_form_defaults(keep_sample=sample_value)
            st.session_state["sample_row_index"] = None
            st.session_state["sample_lookup_status"] = "new"
            st.session_state["sample_lookup_message"] = (
                f"Amostra {sample_value} não encontrada. Preencha os dados para criar um novo registro."
            )
            st.session_state["sample_existing_extras"] = {}
            st.session_state["sample_last_loaded_number"] = sample_value
        else:
            row_idx, form_data, count, extras = fetched
            form_data["n.º da Amostra"] = sample_value
            _queue_form_updates(form_data)
            st.session_state["sample_row_index"] = row_idx
            st.session_state["sample_lookup_status"] = "loaded"
            st.session_state["sample_lookup_message"] = (
                f"Amostra {sample_value} carregada a partir da linha {row_idx}."
            )
            st.session_state["sample_existing_extras"] = extras
            st.session_state["sample_last_loaded_number"] = sample_value
            if count > 1:
                st.session_state["sample_lookup_warning"] = (
                    f"Foram encontradas {count} linhas com este número. A mais recente (linha {row_idx}) foi carregada."
                )
    else:
        _reset_form_defaults(keep_sample="")
        st.session_state["sample_row_index"] = None
        st.session_state["sample_lookup_status"] = None
        st.session_state["sample_lookup_message"] = ""
        st.session_state["sample_existing_extras"] = {}
        st.session_state["sample_last_loaded_number"] = ""



def _block_non_numeric_sample_keystrokes() -> None:
    """Impede que caracteres não numéricos apareçam no campo n.º da Amostra."""
    if components is None:
        return

    label_json = json.dumps("n.º da Amostra", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function attachNumericGuard() {{
            const input = root.querySelector(`input[aria-label="${{CSS.escape(label)}}"]`);
            if (!input || input.dataset.sampleNumericGuard === "1") return;

            input.dataset.sampleNumericGuard = "1";
            input.setAttribute("inputmode", "numeric");
            input.setAttribute("pattern", "[0-9]*");

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;

              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);

              if (allowedKeys.has(event.key)) return;
              if (/^[0-9]$/.test(event.key)) return;
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" &&
                  event.data && !/^[0-9]+$/.test(event.data)) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              const pasted = (event.clipboardData || window.clipboardData)
                .getData("text");
              if (/^\d+$/.test(pasted) && pasted.length <= 9) return;

              event.preventDefault();
              const digits = pasted.replace(/\D/g, "");
              if (!digits) return;

              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              const available = Math.max(0, 9 - (input.value.length - (end - start)));
              const insertion = digits.slice(0, available);
              if (!insertion) return;

              input.setRangeText(insertion, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);
          }}

          attachNumericGuard();
          const observer = new MutationObserver(attachNumericGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 15000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _sanitize_os_input() -> None:
    """Mantém a O.S. somente com números e limita o campo a 6 dígitos."""
    if st is None:
        return
    raw_value = st.session_state.get(OS_FORM_LABEL, "")
    digits_only = re.sub(r"\D", "", str(raw_value))[:6]
    st.session_state[OS_FORM_LABEL] = digits_only
    st.session_state.setdefault("form_values", {})[OS_FORM_LABEL] = digits_only


def _block_non_numeric_os_keystrokes() -> None:
    """Impede que caracteres não numéricos cheguem a aparecer no campo O.S."""
    if components is None:
        return

    # O pequeno componente apenas instala os eventos no text_input nativo do
    # Streamlit. Não cria campo visual nem ocupa espaço na página.
    label_json = json.dumps(OS_FORM_LABEL, ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function attachNumericGuard() {{
            const input = root.querySelector(`input[aria-label="${{CSS.escape(label)}}"]`);
            if (!input || input.dataset.osNumericGuard === "1") return;

            input.dataset.osNumericGuard = "1";
            input.setAttribute("inputmode", "numeric");
            input.setAttribute("pattern", "[0-9]*");

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;

              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);

              if (allowedKeys.has(event.key)) return;
              if (/^[0-9]$/.test(event.key)) return;

              // Bloqueia letras, espaços e caracteres especiais antes que
              // sejam inseridos no campo.
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" &&
                  event.data && !/^[0-9]+$/.test(event.data)) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              const pasted = (event.clipboardData || window.clipboardData)
                .getData("text");
              if (/^\\d+$/.test(pasted)) return;

              event.preventDefault();
              const digits = pasted.replace(/\\D/g, "");
              if (!digits) return;

              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              const available = Math.max(0, 6 - (input.value.length - (end - start)));
              const insertion = digits.slice(0, available);
              if (!insertion) return;

              input.setRangeText(insertion, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);
          }}

          attachNumericGuard();
          const observer = new MutationObserver(attachNumericGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 15000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )





def _sanitize_serial_input() -> None:
    """Mantém o n.º de série somente com números e limita a 7 dígitos."""
    if st is None:
        return
    serial_key = "n.º de série:"
    raw_value = st.session_state.get(serial_key, "")
    digits_only = re.sub(r"\D", "", str(raw_value))[:7]
    st.session_state[serial_key] = digits_only
    st.session_state.setdefault("form_values", {})[serial_key] = digits_only


def _block_non_numeric_serial_keystrokes() -> None:
    """Bloqueia letras/símbolos e limita o campo n.º de série a 7 dígitos."""
    if components is None:
        return

    label_json = json.dumps("n.º de série:", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function attachNumericGuard() {{
            const inputs = Array.from(root.querySelectorAll('input[aria-label]'));
            const input = inputs.find((el) => el.getAttribute('aria-label') === label);
            if (!input || input.dataset.serialNumericGuard === "1") return;

            input.dataset.serialNumericGuard = "1";
            input.setAttribute("inputmode", "numeric");
            input.setAttribute("pattern", "[0-9]*");
            input.setAttribute("maxlength", "7");

            const cleanAndLimit = () => {{
              const cleaned = input.value.replace(/\D/g, "").slice(0, 7);
              if (input.value !== cleaned) {{
                const nativeSetter = Object.getOwnPropertyDescriptor(
                  window.parent.HTMLInputElement.prototype, "value"
                ).set;
                nativeSetter.call(input, cleaned);
                input.dispatchEvent(new Event("input", {{ bubbles: true }}));
              }}
            }};

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;
              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);
              if (allowedKeys.has(event.key)) return;
              if (/^[0-9]$/.test(event.key)) {{
                const start = input.selectionStart ?? input.value.length;
                const end = input.selectionEnd ?? start;
                if (input.value.length - (end - start) >= 7) event.preventDefault();
                return;
              }}
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" &&
                  event.data && !/^[0-9]+$/.test(event.data)) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              event.preventDefault();
              const pasted = (event.clipboardData || window.clipboardData).getData("text");
              const digits = pasted.replace(/\D/g, "");
              if (!digits) return;

              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              const available = Math.max(0, 7 - (input.value.length - (end - start)));
              const insertion = digits.slice(0, available);
              if (!insertion) return;

              input.setRangeText(insertion, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);

            input.addEventListener("input", cleanAndLimit, true);
            cleanAndLimit();
          }}

          attachNumericGuard();
          const observer = new MutationObserver(attachNumericGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 30000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )



def _sanitize_motor_hourmeter_input() -> None:
    """Mantém o Horímetro do Motor somente com números."""
    if st is None:
        return
    key = "Horímetro do Motor"
    raw_value = st.session_state.get(key, "")
    digits_only = re.sub(r"\D", "", str(raw_value))
    st.session_state[key] = digits_only
    st.session_state.setdefault("form_values", {})[key] = digits_only


def _block_non_numeric_motor_hourmeter_keystrokes() -> None:
    """Bloqueia letras e símbolos no campo Horímetro do Motor."""
    if components is None:
        return

    label_json = json.dumps("Horímetro do Motor", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function attachNumericGuard() {{
            const inputs = Array.from(root.querySelectorAll('input[aria-label]'));
            const input = inputs.find((el) => el.getAttribute('aria-label') === label);
            if (!input || input.dataset.motorHourmeterNumericGuard === "1") return;

            input.dataset.motorHourmeterNumericGuard = "1";
            input.setAttribute("inputmode", "numeric");
            input.setAttribute("pattern", "[0-9]*");

            const clean = () => {{
              const cleaned = input.value.replace(/\D/g, "");
              if (input.value !== cleaned) {{
                const nativeSetter = Object.getOwnPropertyDescriptor(
                  window.parent.HTMLInputElement.prototype, "value"
                ).set;
                nativeSetter.call(input, cleaned);
                input.dispatchEvent(new Event("input", {{ bubbles: true }}));
              }}
            }};

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;
              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);
              if (allowedKeys.has(event.key)) return;
              if (/^[0-9]$/.test(event.key)) return;
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" &&
                  event.data && !/^[0-9]+$/.test(event.data)) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              event.preventDefault();
              const pasted = (event.clipboardData || window.clipboardData).getData("text");
              const digits = pasted.replace(/\D/g, "");
              if (!digits) return;
              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              input.setRangeText(digits, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);

            input.addEventListener("input", clean, true);
            clean();
          }}

          attachNumericGuard();
          const observer = new MutationObserver(attachNumericGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 30000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _sanitize_responsible_input() -> None:
    """Mantém o responsável somente com letras/espaços e no máximo 10 caracteres."""
    if st is None:
        return
    key = "Responsável Pela Coleta:"
    raw_value = str(st.session_state.get(key, ""))
    cleaned = "".join(ch for ch in raw_value if ch.isalpha() or ch == " ")[:10]
    st.session_state[key] = cleaned
    st.session_state.setdefault("form_values", {})[key] = cleaned


def _block_invalid_responsible_keystrokes() -> None:
    """Bloqueia números/símbolos e limita o responsável a 10 caracteres."""
    if components is None:
        return

    label_json = json.dumps("Responsável Pela Coleta:", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function onlyLettersAndSpaces(text) {{
            return Array.from(text).filter((ch) => /[\p{{L}} ]/u.test(ch)).join("");
          }}

          function attachResponsibleGuard() {{
            const inputs = Array.from(root.querySelectorAll('input[aria-label]'));
            const input = inputs.find((el) => el.getAttribute('aria-label') === label);
            if (!input || input.dataset.responsibleLettersGuard === "1") return;

            input.dataset.responsibleLettersGuard = "1";
            input.setAttribute("maxlength", "10");

            const setValue = (value) => {{
              const nativeSetter = Object.getOwnPropertyDescriptor(
                window.parent.HTMLInputElement.prototype, "value"
              ).set;
              nativeSetter.call(input, value);
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }};

            const cleanAndLimit = () => {{
              const cleaned = onlyLettersAndSpaces(input.value).slice(0, 10);
              if (input.value !== cleaned) setValue(cleaned);
            }};

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;
              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);
              if (allowedKeys.has(event.key)) return;
              if (event.key.length === 1 && /[\p{{L}} ]/u.test(event.key)) {{
                const start = input.selectionStart ?? input.value.length;
                const end = input.selectionEnd ?? start;
                if (input.value.length - (end - start) >= 10) event.preventDefault();
                return;
              }}
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" && event.data &&
                  !Array.from(event.data).every((ch) => /[\p{{L}} ]/u.test(ch))) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              event.preventDefault();
              const pasted = (event.clipboardData || window.clipboardData).getData("text");
              const valid = onlyLettersAndSpaces(pasted);
              if (!valid) return;
              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              const available = Math.max(0, 10 - (input.value.length - (end - start)));
              const insertion = valid.slice(0, available);
              if (!insertion) return;
              input.setRangeText(insertion, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);

            input.addEventListener("input", cleanAndLimit, true);
            cleanAndLimit();
          }}

          attachResponsibleGuard();
          const observer = new MutationObserver(attachResponsibleGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 30000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

def _sanitize_ugd_input() -> None:
    """Mantém a UGD somente com números e limita o campo a 2 dígitos."""
    if st is None:
        return
    ugd_key = "UGD:"
    raw_value = st.session_state.get(ugd_key, "")
    digits_only = re.sub(r"\D", "", str(raw_value))[:2]
    st.session_state[ugd_key] = digits_only
    st.session_state.setdefault("form_values", {})[ugd_key] = digits_only


def _block_non_numeric_ugd_keystrokes() -> None:
    """Impede que caracteres não numéricos apareçam no campo UGD."""
    if components is None:
        return

    label_json = json.dumps("UGD:", ensure_ascii=False)
    components.html(
        f"""
        <script>
        (() => {{
          const label = {label_json};
          const root = window.parent.document;

          function attachNumericGuard() {{
            const input = root.querySelector(`input[aria-label="${{CSS.escape(label)}}"]`);
            if (!input || input.dataset.ugdNumericGuard === "1") return;

            input.dataset.ugdNumericGuard = "1";
            input.setAttribute("inputmode", "numeric");
            input.setAttribute("pattern", "[0-9]*");

            input.addEventListener("keydown", (event) => {{
              if (event.ctrlKey || event.metaKey || event.altKey) return;
              const allowedKeys = new Set([
                "Backspace", "Delete", "Tab", "Enter", "Escape",
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End"
              ]);
              if (allowedKeys.has(event.key)) return;
              if (/^[0-9]$/.test(event.key)) return;
              if (event.key.length === 1) event.preventDefault();
            }}, true);

            input.addEventListener("beforeinput", (event) => {{
              if (event.inputType === "insertText" &&
                  event.data && !/^[0-9]+$/.test(event.data)) {{
                event.preventDefault();
              }}
            }}, true);

            input.addEventListener("paste", (event) => {{
              const pasted = (event.clipboardData || window.clipboardData).getData("text");
              event.preventDefault();
              const digits = pasted.replace(/\D/g, "");
              if (!digits) return;
              const start = input.selectionStart ?? input.value.length;
              const end = input.selectionEnd ?? start;
              const available = Math.max(0, 2 - (input.value.length - (end - start)));
              const insertion = digits.slice(0, available);
              if (!insertion) return;
              input.setRangeText(insertion, start, end, "end");
              input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            }}, true);
          }}

          attachNumericGuard();
          const observer = new MutationObserver(attachNumericGuard);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 15000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

def _sync_operation_location() -> None:
    """Mantém somente uma UTE e sincroniza corretamente após limpar/reselecionar."""
    if st is None:
        return

    key = "local_operacao_selector"
    selected = list(st.session_state.get(key, []) or [])

    # Caso duas opções sejam escolhidas muito rapidamente, mantém apenas a última.
    if len(selected) > 1:
        selected = [selected[-1]]
        st.session_state[key] = selected

    value = selected[0] if selected else ""
    st.session_state.setdefault("form_values", {})["Local de operação:"] = value


def _hide_multiselect_limit_message() -> None:
    """Oculta somente o aviso em inglês exibido pelo multiselect no limite."""
    if components is None:
        return

    message_json = json.dumps(
        "You can only select up to 1 option. Remove an option first."
    )
    components.html(
        f"""
        <script>
        (() => {{
          const targetMessage = {message_json};
          const root = window.parent.document;

          function hideLimitMessage() {{
            const elements = root.querySelectorAll('body *');
            for (const element of elements) {{
              if ((element.textContent || '').trim() !== targetMessage) continue;

              // Oculta o menor bloco que contém somente o aviso. Dessa forma,
              // o botão X e todo o restante do seletor permanecem inalterados.
              element.style.setProperty('display', 'none', 'important');
              element.setAttribute('aria-hidden', 'true');
            }}
          }}

          hideLimitMessage();
          const observer = new MutationObserver(hideLimitMessage);
          observer.observe(root.body, {{ childList: true, subtree: true }});
          window.setTimeout(() => observer.disconnect(), 60000);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

def _trigger_rerun() -> None:
    """Solicita um rerun compatível com versões antigas e novas do Streamlit."""
    if st is None:
        return

    for attr_name in ("experimental_rerun", "rerun"):
        rerun = getattr(st, attr_name, None)
        if callable(rerun):
            rerun()
            return


# ░░░ Helpers UI ░░░
def _render_sample_feedback() -> None:
    if st is None:
        return
    message = st.session_state.get("sample_lookup_message", "")
    status = st.session_state.get("sample_lookup_status")
    warning = st.session_state.get("sample_lookup_warning")

    if message:
        if status == "loaded":
            st.success(message)
        elif status == "new":
            st.info(message)
        elif status == "error":
            st.error(message)
        else:
            st.caption(message)

    if warning:
        st.warning(warning)


def _two_checkboxes(label: str, default: bool | None = None) -> bool:
    if st is None:
        raise RuntimeError("Streamlit não instalado – UI indisponível.")
    st.markdown(f"**{label}**")
    key_yes = f"{label}_yes"
    key_no  = f"{label}_no"
    if key_yes not in st.session_state and key_no not in st.session_state:
        if default is True:
            st.session_state[key_yes] = True
            st.session_state[key_no] = False
        elif default is False:
            st.session_state[key_yes] = False
            st.session_state[key_no] = True
        else:
            st.session_state[key_yes] = False
            st.session_state[key_no] = False

    col_yes, col_no = st.columns(2)

    def _sync_yes() -> None:
        if st.session_state[key_yes]:
            st.session_state[key_no] = False

    def _sync_no() -> None:
        if st.session_state[key_no]:
            st.session_state[key_yes] = False

    with col_yes:
        st.checkbox("Sim", key=key_yes, on_change=_sync_yes)
    with col_no:
        st.checkbox("Não", key=key_no, on_change=_sync_no)
    return bool(st.session_state[key_yes])



def _decode_qr_sample_image(uploaded_image: Any) -> Tuple[Optional[str], Optional[str]]:
    """Lê o QR Code de uma foto e retorna o n.º da amostra com 9 dígitos."""
    if uploaded_image is None:
        return None, None

    try:
        image_bytes = uploaded_image.getvalue()
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return None, "Não foi possível abrir a imagem capturada."

        detector = cv2.QRCodeDetector()
        decoded_text, _, _ = detector.detectAndDecode(image)
        decoded_text = str(decoded_text or "").strip()
        if not decoded_text:
            return None, "QR Code não identificado. Aproxime a câmera e tente novamente."

        digits = re.sub(r"\D", "", decoded_text)
        if len(digits) != 9:
            return None, (
                "QR Code inválido para o n.º da Amostra. "
                f"Foram encontrados {len(digits)} dígitos; são necessários exatamente 9."
            )
        return digits, None
    except Exception as exc:
        return None, f"Erro ao ler o QR Code: {exc}"


def _render_sample_qr_scanner() -> None:
    """Abre um scanner contínuo, priorizando a câmera traseira, e lê o QR automaticamente."""
    st.session_state.setdefault("sample_qr_scanner_open", False)

    button_label = (
        "🔄 Ler outro QR Code"
        if st.session_state.get("sample_qr_verified", False)
        else "▣ Ler QR Code"
    )
    if st.button(
        button_label,
        key="sample_qr_toggle",
        help="Abra a câmera traseira e aponte para o QR Code. Não é necessário tirar foto.",
        use_container_width=True,
    ):
        st.session_state["sample_qr_scanner_open"] = not st.session_state["sample_qr_scanner_open"]
        st.session_state.pop("sample_qr_component_result", None)
        st.rerun()

    if not st.session_state["sample_qr_scanner_open"]:
        return

    component_path = os.path.join(os.path.dirname(__file__), "qr_scanner_component")
    qr_scanner = components.declare_component(
        "sample_qr_live_scanner",
        path=component_path,
    )
    result = qr_scanner(
        key="sample_qr_live_scanner_instance",
        default=None,
    )

    if not result:
        return

    result = str(result).strip()
    if result == "__CLOSE__":
        st.session_state["sample_qr_scanner_open"] = False
        st.rerun()

    digits = re.sub(r"\D", "", result)
    if len(digits) != 9:
        st.error("QR Code inválido. O n.º da Amostra deve conter exatamente 9 números.")
        return

    if st.session_state.get("sample_qr_component_result") == digits:
        return

    st.session_state["sample_qr_component_result"] = digits
    st.session_state["sample_qr_verified"] = True
    st.session_state["sample_qr_scanner_open"] = False
    st.session_state["_sample_qr_apply_lookup"] = True
    _queue_form_updates({"n.º da Amostra": digits})
    st.session_state["sample_lookup_status"] = "loaded"
    st.session_state["sample_lookup_message"] = f"QR Code lido com sucesso: {digits}."
    st.rerun()


def _is_sample_qr_verified() -> bool:
    """Confirma que a amostra atual veio de uma leitura válida do QR Code."""
    qr_number = re.sub(
        r"\D", "", str(st.session_state.get("sample_qr_component_result", ""))
    )[:9]
    current_sample = re.sub(
        r"\D", "", str(st.session_state.get("n.º da Amostra", ""))
    )[:9]
    return bool(
        st.session_state.get("sample_qr_verified", False)
        and len(qr_number) == 9
        and current_sample == qr_number
    )


def _sanitize_manual_sample_input() -> None:
    """Mantém somente números no campo manual da etiqueta, limitado a 9 dígitos."""
    if st is None:
        return
    raw_value = str(st.session_state.get("sample_manual_entry", "") or "")
    st.session_state["sample_manual_entry"] = re.sub(r"\D", "", raw_value)[:9]


def _accept_manual_sample_number() -> None:
    """Valida a etiqueta digitada e libera o mesmo fluxo usado pelo QR Code."""
    _sanitize_manual_sample_input()
    digits = str(st.session_state.get("sample_manual_entry", "") or "")

    if len(digits) != 9:
        st.session_state["sample_manual_error"] = (
            "Informe exatamente 9 números no campo Número da etiqueta."
        )
        return

    st.session_state.pop("sample_manual_error", None)
    st.session_state["sample_qr_component_result"] = digits
    st.session_state["sample_qr_verified"] = True
    st.session_state["sample_qr_scanner_open"] = False
    st.session_state["_sample_qr_apply_lookup"] = True
    _queue_form_updates({"n.º da Amostra": digits})
    st.session_state["sample_lookup_status"] = "loaded"
    st.session_state["sample_lookup_message"] = (
        f"Etiqueta informada manualmente: {digits}."
    )


def require_qr_before_form() -> None:
    """Libera o formulário após QR Code válido ou etiqueta digitada manualmente."""
    if st is None:
        raise RuntimeError("Streamlit não instalado – UI indisponível.")

    _ensure_form_state()
    if st.session_state.pop("_sample_qr_apply_lookup", False):
        _handle_sample_change()
        st.rerun()

    if _is_sample_qr_verified():
        return

    st.markdown("## 📦 Nova Coleta de Óleo")
    st.info(
        "Para iniciar a coleta, leia o QR Code ou digite o número da etiqueta da amostra."
    )

    st.text_input(
        "Número da etiqueta",
        key="sample_manual_entry",
        max_chars=9,
        placeholder="Digite os 9 números da etiqueta",
        on_change=_sanitize_manual_sample_input,
        help="Aceita somente números e deve conter exatamente 9 dígitos.",
    )

    if st.button(
        "➡️ Continuar com a etiqueta",
        key="sample_manual_continue",
        use_container_width=True,
        on_click=_accept_manual_sample_number,
    ):
        pass

    manual_error = st.session_state.get("sample_manual_error")
    if manual_error:
        st.error(manual_error)

    st.markdown(
        "<div style='text-align:center; margin:0.65rem 0; opacity:0.65;'>ou</div>",
        unsafe_allow_html=True,
    )
    _render_sample_qr_scanner()
    st.caption(
        "O formulário completo será exibido após uma etiqueta válida ou uma leitura do QR Code."
    )
    st.stop()


def build_form_and_get_responses() -> Dict[str, Any]:
    """Desenha o formulário completo e retorna um dicionário label->valor."""
    if st is None:
        raise RuntimeError("Streamlit não instalado – UI indisponível.")

    _ensure_form_state()
    if st.session_state.pop("_sample_qr_apply_lookup", False):
        _handle_sample_change()
        st.rerun()

    form_values = st.session_state["form_values"]

    st.header("Formulário de Coleta de Amostras de Óleo 🛢️")

    # Proteção redundante: mesmo que esta função seja chamada diretamente,
    # nenhum campo é criado antes de uma leitura válida do QR Code.
    if not _is_sample_qr_verified():
        st.info(
            "🔒 Para iniciar o preenchimento, leia primeiro o QR Code da amostra."
        )
        st.text_input(
            "n.º da Amostra",
            value="",
            placeholder="Aguardando leitura do QR Code",
            disabled=True,
            key="sample_qr_locked_display",
        )
        _render_sample_qr_scanner()
        st.caption(
            "Os demais campos serão liberados automaticamente após a leitura válida."
        )
        st.stop()

    responses: Dict[str, Any] = {}

    for section, questions in FORM_SECTIONS:
        st.subheader(section)

        if section == "Geral":
            sample_label = "n.º da Amostra"
            col_sample, col_os = st.columns(2)

            with col_sample:
                sample_default = form_values.get(sample_label, "")
                if sample_label not in st.session_state:
                    st.session_state[sample_label] = (
                        "" if sample_default is None else str(sample_default)
                    )
                sample_value = st.text_input(
                    sample_label,
                    key=sample_label,
                    max_chars=9,
                    disabled=True,
                    help="Número validado pela leitura obrigatória do QR Code.",
                )
                sample_value = re.sub(r"\D", "", str(sample_value))[:9]
                sample_value = st.session_state.get(sample_label, sample_value)
                _render_sample_qr_scanner()
            responses[sample_label] = sample_value
            form_values[sample_label] = sample_value

            with col_os:
                os_default = form_values.get(OS_FORM_LABEL, "")
                if OS_FORM_LABEL not in st.session_state:
                    st.session_state[OS_FORM_LABEL] = (
                        "" if os_default is None else str(os_default)
                    )

                os_value = st.text_input(
                    OS_FORM_LABEL,
                    key=OS_FORM_LABEL,
                    max_chars=6,
                    on_change=_sanitize_os_input,
                    help="Obrigatório: informe exatamente 6 números.",
                )
                _block_non_numeric_os_keystrokes()
                os_value = re.sub(r"\D", "", str(os_value))[:6]

            responses[OS_FORM_LABEL] = os_value
            form_values[OS_FORM_LABEL] = os_value

            _render_sample_feedback()

            for label, default in questions:
                if label in {sample_label, OS_FORM_LABEL}:
                    continue
                effective_default = form_values.get(label, default)
                if isinstance(default, bool):
                    if isinstance(effective_default, bool):
                        default_bool = effective_default
                    else:
                        default_bool = default
                    value = _two_checkboxes(label, default=default_bool)
                elif label == "Data da coleta":
                    if label not in st.session_state:
                        st.session_state[label] = _parse_date_value(effective_default)
                    selected_date = st.date_input(
                        label,
                        key=label,
                        format="DD/MM/YYYY",
                        help="Clique no campo para selecionar a data no calendário.",
                    )
                    value = selected_date.strftime("%d/%m/%Y") if selected_date else ""
                elif label == "Local de operação:":
                    access_locality = st.session_state.get("localidade_acesso", "")
                    locked_location = _resolve_access_location(access_locality)

                    if locked_location:
                        st.session_state.setdefault("form_values", {})[
                            "Local de operação:"
                        ] = locked_location
                        st.text_input(
                            label,
                            value=locked_location,
                            disabled=True,
                            help=(
                                "Localidade preenchida automaticamente conforme "
                                "o login de acesso."
                            ),
                        )
                        value = locked_location
                        responses[label] = value
                        form_values[label] = value
                        continue

                    current_location = str(effective_default or "").strip().upper()
                    if current_location and not current_location.startswith("UTE-"):
                        current_location = f"UTE-{current_location}"
                    if current_location not in OPERATION_LOCATIONS:
                        current_location = ""

                    # O multiselect limitado a uma opção mantém o comportamento de
                    # lista suspensa e exibe o botão X. Ao clicar no X, a seleção
                    # fica vazia de verdade, sem restaurar automaticamente o valor anterior.
                    location_widget_key = "local_operacao_selector"
                    if location_widget_key not in st.session_state:
                        st.session_state[location_widget_key] = (
                            [current_location] if current_location else []
                        )

                    selected_locations = st.multiselect(
                        label,
                        options=OPERATION_LOCATIONS,
                        key=location_widget_key,
                        placeholder="CLIQUE PARA SELECIONAR UMA UTE",
                        help="Clique no campo e selecione uma localidade. Use o X para limpar.",
                        on_change=_sync_operation_location,
                    )

                    # A limitação é controlada pelo callback, evitando o travamento
                    # do componente após limpar a seleção mais de uma vez.
                    if len(selected_locations) > 1:
                        selected_locations = [selected_locations[-1]]

                    value = selected_locations[0] if selected_locations else ""
                elif label == "UGD:":
                    ugd_key = "UGD:"
                    if ugd_key not in st.session_state:
                        st.session_state[ugd_key] = re.sub(
                            r"\D", "", str(effective_default)
                        )[:2]
                    value = st.text_input(
                        ugd_key,
                        key=ugd_key,
                        max_chars=2,
                        on_change=_sanitize_ugd_input,
                        help="Informe a UGD com 2 dígitos. Ex.: 01, 02, 10, 25.",
                    )
                    _block_non_numeric_ugd_keystrokes()
                    value = re.sub(r"\D", "", str(value))[:2]
                elif label == "Responsável Pela Coleta:":
                    responsible_key = "Responsável Pela Coleta:"
                    if responsible_key not in st.session_state:
                        initial = str(effective_default or "")
                        st.session_state[responsible_key] = "".join(
                            ch for ch in initial if ch.isalpha() or ch == " "
                        )[:10]
                    value = st.text_input(
                        responsible_key,
                        key=responsible_key,
                        max_chars=10,
                        on_change=_sanitize_responsible_input,
                        help="Informe somente letras e espaços. Máximo de 10 caracteres.",
                    )
                    _block_invalid_responsible_keystrokes()
                    value = "".join(
                        ch for ch in str(value) if ch.isalpha() or ch == " "
                    )[:10]
                elif label == REGISTRANT_FORM_LABEL:
                    value = st.text_input(
                        REGISTRANT_FORM_LABEL,
                        value="" if effective_default is None else str(effective_default),
                        max_chars=60,
                        help="Informe o nome da pessoa responsável pelo registro.",
                    )
                elif label == REGISTRATION_DATE_FORM_LABEL:
                    value = datetime.now().strftime("%d/%m/%Y")
                    st.text_input(
                        REGISTRATION_DATE_FORM_LABEL,
                        value=value,
                        disabled=True,
                        help="Preenchida automaticamente no momento do registro.",
                    )
                else:
                    value = st.text_input(
                        label,
                        value="" if effective_default is None else str(effective_default),
                    )
                responses[label] = value
                form_values[label] = value
            continue

        for label, default in questions:
            effective_default = form_values.get(label, default)
            if isinstance(default, bool):
                if isinstance(effective_default, bool):
                    default_bool = effective_default
                else:
                    default_bool = default
                value = _two_checkboxes(label, default=default_bool)
            elif label == "n.º de série:":
                serial_key = "n.º de série:"
                if serial_key not in st.session_state:
                    st.session_state[serial_key] = re.sub(
                        r"\D", "", str(effective_default)
                    )[:7]
                value = st.text_input(
                    serial_key,
                    key=serial_key,
                    max_chars=7,
                    on_change=_sanitize_serial_input,
                    help="Informe o n.º de série com 7 dígitos. Ex.: 1234567.",
                )
                _block_non_numeric_serial_keystrokes()
                value = re.sub(r"\D", "", str(value))[:7]
            elif label == "Horímetro do Motor":
                if label not in st.session_state:
                    st.session_state[label] = re.sub(r"\D", "", str(effective_default))
                value = st.text_input(
                    label,
                    key=label,
                    on_change=_sanitize_motor_hourmeter_input,
                    help="Informe somente números.",
                )
                _block_non_numeric_motor_hourmeter_keystrokes()
                value = re.sub(r"\D", "", str(value))
            else:
                value = st.text_input(
                    label,
                    value="" if effective_default is None else str(effective_default),
                )
            responses[label] = value
            form_values[label] = value

    return responses

# ░░░ Persistência no Google Sheets ░░░
def _fmt(v: Any) -> str:
    if v is True:
        return "Sim"
    if v is False:
        return "Não"
    return "" if v is None else str(v)

def save_to_sheets(
    responses: Dict[str, Any],
    existing_row: Optional[int] = None,
    existing_extras: Optional[Dict[str, str]] = None,
) -> int:
    """
    Persiste os dados no Google Sheets.

    * Quando ``existing_row`` é ``None``: faz APPEND de A..AG e atualiza AH:AJ com
      a O.S., o responsável e a data do registro.
    * Quando ``existing_row`` é informado: atualiza A..AJ na linha indicada, preservando
      colunas não presentes no formulário (Status/Data Status) através de ``existing_extras``.
    Retorna o índice (1-based) da linha gravada/atualizada.
    """

    extras = existing_extras or {}

    sample_value = _fmt(responses.get("n.º da Amostra", "")).strip()
    if not re.fullmatch(r"\d{9}", sample_value):
        raise ValueError("O n.º da Amostra deve conter exatamente 9 números.")

    serial_value = _fmt(responses.get("n.º de série:", "")).strip()
    if not re.fullmatch(r"\d{7}", serial_value):
        raise ValueError("O n.º de série deve conter exatamente 7 números.")
    responses["n.º de série:"] = serial_value

    collection_date = _fmt(responses.get("Data da coleta", "")).strip()
    if not collection_date:
        raise ValueError("A Data da coleta é obrigatória.")

    motor_hourmeter = _fmt(responses.get("Horímetro do Motor", "")).strip()
    if not motor_hourmeter or not motor_hourmeter.isdigit():
        raise ValueError("O Horímetro do Motor é obrigatório e deve conter somente números.")
    responses["Horímetro do Motor"] = motor_hourmeter

    row_out: List[str] = []
    for hdr in SHEET_HEADERS_EXCL_OS:
        if hdr in ("Status", "Data Status"):
            row_out.append(extras.get(hdr, ""))
            continue
        form_label = SHEET_HEADER_TO_FORM.get(hdr)
        val = responses.get(form_label, "") if form_label else ""
        row_out.append(_fmt(val))

    os_value = _fmt(responses.get(OS_FORM_LABEL, "")).strip()
    if not re.fullmatch(r"\d{6}", os_value):
        raise ValueError("A Ordem de Serviço (O.S.) deve conter exatamente 6 números.")

    registrant_value = _fmt(responses.get(REGISTRANT_FORM_LABEL, "")).strip()
    registration_date_value = _fmt(responses.get(REGISTRATION_DATE_FORM_LABEL, "")).strip() or datetime.now().strftime("%d/%m/%Y")
    responses[REGISTRATION_DATE_FORM_LABEL] = registration_date_value

    try:
        service = _get_sheets_service()

        row_full = list(row_out)
        row_full.extend([os_value, registrant_value, registration_date_value])

        if existing_row is not None:
            row_idx_int = int(existing_row)
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A{row_idx_int}:AJ{row_idx_int}",
                valueInputOption="RAW",
                body={"values": [row_full]},
            ).execute()
            _clear_main_sheet_cache()
            return row_idx_int

        # A coleta nova é gravada completa em uma única chamada à planilha.
        append_result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:AJ",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_full]},
        ).execute()

        updated_range = (append_result or {}).get("updates", {}).get("updatedRange", "")
        m = re.search(r"!.*?(\d+):", updated_range) or re.search(r"!.*?(\d+)$", updated_range)
        if not m:
            raise RuntimeError(f"Não foi possível detectar a linha inserida: {updated_range}")
        row_idx_int = int(m.group(1))
        _clear_main_sheet_cache()
        return row_idx_int

    except HttpError as exc:
        if st:
            st.error("❌ Erro ao gravar no Google Sheets.")
        raise RuntimeError(f"Erro ao gravar → {exc}") from exc

# ░░░ PDF ░░░
_REPL = {
    "\u2013": "-",
    "\u2014": "-",
    "\u2011": "-",
    "\u00A0": " ",
    "\n": " ",
    "\r": " ",
}
def _safe(txt: object) -> str:
    if txt is None:
        return ""
    if not isinstance(txt, str):
        txt = str(txt)
    for bad, good in _REPL.items():
        txt = txt.replace(bad, good)
    return txt.encode("latin-1", "replace").decode("latin-1")

def generate_pdf(responses: Dict[str, Any]) -> bytes:
    """
    Gera um PDF A4 (retrato). O campo O.S. está logo após 'n.º da Amostra' no bloco 'Geral',
    então os dois caem lado a lado (duas colunas) sem criar linha extra.
    """
    sample_no = str(responses.get("n.º da Amostra", "SEM_NUMERO")).strip() or "SEM_NUMERO"

    # QR em memória
    qr_img = qrcode.make(sample_no)
    buf_qr = io.BytesIO()
    qr_img.save(buf_qr, format="PNG")
    buf_qr.seek(0)

    # Código de barras em memória
    buf_bar = io.BytesIO()
    barcode = Code128(sample_no, writer=ImageWriter())
    barcode.write(buf_bar, options={
        "module_width": 0.3,
        "module_height": 15,
        "font_size": 8,
    })
    buf_bar.seek(0)

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_left_margin(10)
    pdf.set_top_margin(10)
    pdf.set_right_margin(10)
    pdf.add_page()

    # Cabeçalho
    qr_w = 25
    bar_w = 30
    y_start = pdf.get_y()
    x_qr  = pdf.l_margin
    x_bar = pdf.w - pdf.r_margin - bar_w
    pdf.image(buf_qr, x=x_qr, y=y_start, w=qr_w)
    pdf.image(buf_bar, x=x_bar, y=y_start + 5, w=bar_w)
    pdf.set_font("Helvetica", size=16)
    pdf.set_y(y_start + 8)
    pdf.set_x(0)
    pdf.cell(w=0, h=10, txt="Oliveira Energia - Amostra de óleo", align="C", ln=True)
    pdf.ln(8)

    # Corpo (duas perguntas por linha)
    inner_width = pdf.w - pdf.l_margin - pdf.r_margin
    LABEL_RATIO = 0.655
    group_width = inner_width / 2
    label_w  = group_width * LABEL_RATIO
    value_w  = group_width - label_w
    row_h    = 4.5

    pdf.set_font("Helvetica", size=7)

    for section, qs in FORM_SECTIONS:
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.set_fill_color(240)
        pdf.cell(0, 7, _safe(section), ln=True, border=1, fill=True)
        pdf.set_font("Helvetica", size=9)

        pairs = []
        for label, _ in qs:
            val = responses.get(label, "")
            if val is True:
                val = "Sim"
            elif val is False:
                val = "Não"
            pairs.append((_safe(label), _safe(str(val))))

        n_rows = ceil(len(pairs) / 2)
        idx = 0
        for _ in range(n_rows):
            # esquerda
            if idx < len(pairs):
                lab, val = pairs[idx]
                pdf.cell(label_w, row_h, lab, border=1)
                pdf.cell(value_w, row_h, val, border=1)
                idx += 1
            else:
                pdf.cell(label_w, row_h, "", border=1)
                pdf.cell(value_w, row_h, "", border=1)
            # direita
            if idx < len(pairs):
                lab, val = pairs[idx]
                pdf.cell(label_w, row_h, lab, border=1)
                pdf.cell(value_w, row_h, val, border=1)
                idx += 1
            else:
                pdf.cell(label_w, row_h, "", border=1)
                pdf.cell(value_w, row_h, "", border=1)
            pdf.ln(row_h)
        pdf.ln(1)

    raw = pdf.output(dest="S")
    return bytes(raw) if isinstance(raw, (bytes, bytearray)) else str(raw).encode("latin-1")

if __name__ == "__main__":
    if st is None:
        raise SystemExit("Execute via `streamlit run streamlit_app.py`.")
