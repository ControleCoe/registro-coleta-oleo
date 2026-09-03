"""Compatibilidade com versões antigas do carregador de transição.

Algumas instâncias publicadas ainda importam ``loader_html``. O carregador
atual vive em ``loader_utils``; esta ponte impede erro durante a atualização.
"""

from loader_utils import transition_loader_html

__all__ = ["transition_loader_html"]
