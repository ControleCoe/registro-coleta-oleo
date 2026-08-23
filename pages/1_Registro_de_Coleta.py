import streamlit as st
from loader_utils import pacman_loader


st.title("Registro de Coleta de Amostra de Óleo")
st.caption("Oliveira Energia")




# ────────────────────────────────────────────────────────────────────────────────
# streamlit_app.py — aplicativo Streamlit
# ────────────────────────────────────────────────────────────────────────────────
from typing import Dict


from oleo_utils import (
    build_form_and_get_responses,
    save_to_sheets,
    generate_pdf,
    sync_sample_number,
    require_qr_before_form,
)




if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None
if "pdf_file_name" not in st.session_state:
    st.session_state["pdf_file_name"] = "amostra.pdf"
if "pdf_ready_message" not in st.session_state:
    st.session_state["pdf_ready_message"] = ""


# Mantém o PDF disponível mesmo depois de limpar o formulário.
if st.session_state["pdf_bytes"]:
    if st.session_state["pdf_ready_message"]:
        st.success(st.session_state["pdf_ready_message"])
    st.download_button(
        label="⬇️ Baixar PDF",
        data=st.session_state["pdf_bytes"],
        file_name=st.session_state["pdf_file_name"],
        mime="application/pdf",
        key="baixar_pdf_ultima_coleta",
    )


# Barreira principal: o formulário nem é criado antes da leitura do QR Code.
require_qr_before_form()
responses: Dict[str, object] = build_form_and_get_responses()


if st.button("✅ Enviar & Gerar PDF"):
    sample_no = str(responses.get("n.º da Amostra", "") or "").strip()
    os_value = str(responses.get("Ordem de Serviço (O.S.)", "") or "").strip()
    serial_value = str(responses.get("n.º de série:", "") or "").strip()
    if not (sample_no.isdigit() and len(sample_no) == 9):
        st.error("⚠️ O n.º da Amostra deve conter exatamente 9 números.")
    elif not (os_value.isdigit() and len(os_value) == 6):
        st.error("⚠️ A Ordem de Serviço (O.S.) deve conter exatamente 6 números.")
    elif not (serial_value.isdigit() and len(serial_value) == 7):
        st.error("⚠️ O n.º de série deve conter exatamente 7 números.")
    else:
        responses["Ordem de Serviço (O.S.)"] = os_value
        responses["n.º da Amostra"] = sample_no
        responses["n.º de série:"] = serial_value
        sync_sample_number(sample_no)


        last_loaded = st.session_state.get("sample_last_loaded_number", "") or ""
        existing_row = st.session_state.get("sample_row_index")
        existing_extras = dict(st.session_state.get("sample_existing_extras", {}))
        if sample_no != last_loaded:
            existing_row = None
            existing_extras = {}
            st.session_state["sample_row_index"] = None
            st.session_state["sample_existing_extras"] = {}


        with pacman_loader("Salvando no Google Sheets..."):
            try:
                row_idx = save_to_sheets(
                    responses,
                    existing_row=existing_row,
                    existing_extras=existing_extras,
                )
                st.session_state["sample_row_index"] = row_idx
                st.session_state["sample_last_loaded_number"] = sample_no
                st.session_state["sample_existing_extras"] = existing_extras
                st.session_state["sample_lookup_status"] = "loaded"
                st.session_state["sample_lookup_message"] = (
                    f"Amostra {sample_no} sincronizada na linha {row_idx}."
                )
                if existing_row is not None:
                    st.success(f"♻️ Registro atualizado na linha {row_idx} (A..AH).")
                else:
                    st.success(f"📊 Dados gravados na linha {row_idx} (A..AH).")
            except Exception as exc:
                st.error(str(exc))
                st.stop()
        with pacman_loader("Gerando PDF..."):
            st.session_state["pdf_bytes"] = generate_pdf(responses)
            st.session_state["pdf_file_name"] = f"amostra_{sample_no}.pdf"

        # A gravação e o PDF terminaram com sucesso. Limpa somente os dados
        # desta coleta e mantém o PDF pronto para download.
        st.session_state["pdf_ready_message"] = (
            f"✅ Amostra {sample_no} salva e PDF gerado. O formulário já está pronto para uma nova coleta."
        )
        for field_key in list(responses.keys()):
            st.session_state.pop(field_key, None)
        for state_key in (
            "form_values",
            "_pending_form_values",
            "_sample_qr_apply_lookup",
            "sample_qr_component_result",
            "sample_qr_verified",
            "sample_qr_scanner_open",
            "sample_manual_entry",
            "sample_manual_error",
            "sample_row_index",
            "sample_lookup_status",
            "sample_lookup_message",
            "sample_lookup_warning",
            "sample_existing_extras",
            "sample_last_loaded_number",
        ):
            st.session_state.pop(state_key, None)
        st.rerun()
