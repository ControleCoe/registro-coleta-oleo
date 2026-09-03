import io
import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import oleo_utils

ROOT = Path(__file__).resolve().parents[1]


class Sheets:
    """In-memory Google boundary. No production credentials or records are used."""

    def __init__(self):
        self.header = list(oleo_utils.SHEET_HEADERS_EXCL_OS) + [
            oleo_utils.OS_FORM_LABEL, oleo_utils.REGISTRANT_FORM_LABEL,
            oleo_utils.REGISTRATION_DATE_FORM_LABEL,
        ]
        self.row = [""] * 36
        self.row[3:9] = ["UTE-CANUTAMA", "01", "CAROL", "123456789", "1234567", ""]
        self.row[33] = "123456"
        self.rows = [self.header, self.row]
        self.writes = []
        self.reads = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    @staticmethod
    def response(value):
        class Response:
            def execute(self):
                return value
        return Response()

    def read(self, range):
        self.reads.append(range)
        if range == "RETORNO!A:A":
            return []
        if "A1:AJ1" in range:
            return [self.header]
        if range.endswith("!G:G"):
            return [[r[6]] for r in self.rows]
        if range.endswith("!AH:AH"):
            return [[r[33]] for r in self.rows]
        if match := re.search(r"!D(\d+):AH\d+$", range):
            return [self.rows[int(match[1]) - 1][3:34]]
        if range.endswith("!A2:AJ2"):
            return [self.row]
        raise AssertionError(f"Unexpected read: {range}")

    def get(self, *, range, **kwargs):
        return self.response({"values": self.read(range)})

    def batchGet(self, *, ranges, **kwargs):
        return self.response({"valueRanges": [{"values": self.read(r)} for r in ranges]})

    def batchUpdate(self, *, body, **kwargs):
        self.writes.append(body)
        return self.response({})

    def append(self, *, body, **kwargs):
        self.writes.append(body)
        self.rows.extend(body["values"])
        return self.response({"updates": {"updatedRange": "Geral!A3:AJ3"}})


@pytest.fixture
def sheets():
    st.cache_data.clear()
    fake = Sheets()
    with patch.object(oleo_utils, "_get_sheets_service", return_value=fake):
        yield fake
    st.cache_data.clear()


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_collection_save_confirms_success_after_reset(sheets):
    app = AppTest.from_file(str(ROOT / "pages/1_Registro_de_Coleta.py"), default_timeout=20)
    app.run()
    app.text_input(key="sample_manual_entry").set_value("987654321")
    click(app, "➡️ Continuar com a etiqueta")
    app.text_input(key=oleo_utils.OS_FORM_LABEL).set_value("654321")
    app.text_input(key="n.º de série:").set_value("7654321")
    app.text_input(key="Horímetro do Motor").set_value("1200")
    app.date_input(key="Data da coleta").set_value(date(2026, 9, 3))
    click(app, "✅ Salvar coleta")
    assert not app.error
    assert sheets.rows[-1][6] == "987654321"
    assert sheets.rows[-1][33] == "654321"
    assert any("987654321" in message.value for message in app.success)
    click(app, "📄 Gerar PDF da última coleta")
    assert app.session_state["pdf_bytes"].startswith(b"%PDF")


@pytest.mark.parametrize("code", ["123456789", "987654321"])
def test_return_produces_download_and_keeps_it_after_rerun(sheets, code):
    app = AppTest.from_file(str(ROOT / "pages/2_Retorno_da_Amostra.py"), default_timeout=20)
    app.session_state["retorno_lista"] = {code: "123456"}
    app.session_state["retorno_localidades"] = {code: "CANUTAMA"}
    kit_moves = []

    def kit_response(req, **kwargs):
        kit_moves.append(json.loads(req.data))
        return io.BytesIO(b'{"ok":true}')

    with patch("urllib.request.urlopen", side_effect=kit_response):
        app.run()
        click(app, "📥 Processar retorno")
        app.text_input(key="retorno_lancador").set_value("CAROL PASSOS")
        click(app, "✅ Confirmar lançamento")
        assert not app.error
        assert len(app.get("download_button")) == 1
        assert len(kit_moves) == 1
        assert kit_moves[0]["quantity"] == 1
        assert kit_moves[0]["responsible"] == "CANUTAMA"
        with ZipFile(io.BytesIO(app.session_state["retorno_arquivo"])) as archive:
            assert sorted(Path(name).suffix for name in archive.namelist()) == [".docx", ".xlsx"]
            for name in archive.namelist():
                with ZipFile(io.BytesIO(archive.read(name))) as document:
                    assert document.testzip() is None
        app.run()
        assert len(app.get("download_button")) == 1
        assert len(kit_moves) == 1
        assert not app.session_state["retorno_lista"]


def test_registration_header_and_sample_index_use_one_round_trip(sheets):
    with patch.object(sheets, "get", side_effect=AssertionError("Use one batch read")):
        header, samples = oleo_utils._fetch_sheet_header_and_samples()
    assert header[6] == "n.º da Amostra"
    assert samples == ["n.º da Amostra", "123456789"]


def test_return_can_find_collection_saved_after_previous_lookup(sheets):
    app = AppTest.from_file(str(ROOT / "pages/2_Retorno_da_Amostra.py"), default_timeout=20)
    app.run()
    app.text_input(key="retorno_os").set_value("654321")
    click(app, "➕ Adicionar amostra")
    assert not app.session_state["retorno_lista"]
    oleo_utils.save_to_sheets({
        "n.º da Amostra": "987654321", "n.º de série:": "7654321",
        "Data da coleta": "03/09/2026", "Horímetro do Motor": "1200",
        "Ordem de Serviço (O.S.)": "654321", "Local de operação:": "UTE-CANUTAMA",
    })
    click(app, "➕ Adicionar amostra")
    assert app.session_state["retorno_lista"] == {"987654321": "654321"}


def test_return_does_not_write_an_os_that_already_has_a_return(sheets):
    """A second confirmation must not create duplicate return blocks."""
    status_idx = 31  # AF
    sheets.row[status_idx] = "RETORNO"
    app = AppTest.from_file(str(ROOT / "pages/2_Retorno_da_Amostra.py"), default_timeout=20)
    app.session_state["retorno_lista"] = {"123456789": "123456"}
    app.session_state["retorno_localidades"] = {"123456789": "CANUTAMA"}

    app.run()
    click(app, "📥 Processar retorno")
    app.text_input(key="retorno_lancador").set_value("CAROL PASSOS")
    click(app, "✅ Confirmar lançamento")

    assert app.warning
    assert not sheets.writes


@pytest.mark.parametrize("code", ["123456789", "987654321"])
def test_invalid_word_template_does_not_write_return_or_debit_kits(sheets, code):
    app = AppTest.from_file(str(ROOT / "pages/2_Retorno_da_Amostra.py"), default_timeout=20)
    app.session_state["retorno_lista"] = {code: "123456"}
    app.session_state["retorno_localidades"] = {code: "CANUTAMA"}
    with patch("lxml.etree.fromstring", side_effect=ValueError("Invalid template")):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"ok":true}')) as stock:
            app.run()
            click(app, "📥 Processar retorno")
            app.text_input(key="retorno_lancador").set_value("CAROL PASSOS")
            click(app, "✅ Confirmar lançamento")
            assert app.error
            assert not sheets.writes
            stock.assert_not_called()
            assert app.session_state["retorno_lista"] == {code: "123456"}
