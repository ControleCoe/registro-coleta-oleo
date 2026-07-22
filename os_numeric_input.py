from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "os_numeric_input_frontend"
_os_numeric_input = components.declare_component(
    "os_numeric_input",
    path=str(_COMPONENT_DIR),
)


def os_numeric_input(
    label: str,
    value: str = "",
    *,
    key: Optional[str] = None,
    max_digits: int = 6,
    help_text: str = "Obrigatório: informe exatamente 6 números.",
) -> str:
    """Campo numérico que remove caracteres inválidos durante a digitação."""
    result = _os_numeric_input(
        label=label,
        value="" if value is None else str(value),
        max_digits=int(max_digits),
        help_text=help_text,
        key=key,
        default="" if value is None else str(value),
    )
    return "" if result is None else str(result)
