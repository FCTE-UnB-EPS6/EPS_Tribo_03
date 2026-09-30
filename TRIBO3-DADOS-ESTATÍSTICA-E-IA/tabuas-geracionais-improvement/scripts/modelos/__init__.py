"""
Pacote de Modelos Atuariais e Estocásticos de Mortalidade — Passo 6
"""

from .baseline import treinar_baseline, projetar_baseline
from .lee_carter import (
    montar_matriz_mortalidade,
    ajustar_lee_carter,
    treinar_lee_carter,
    projetar_lee_carter,
)

__all__ = [
    "treinar_baseline",
    "projetar_baseline",
    "montar_matriz_mortalidade",
    "ajustar_lee_carter",
    "treinar_lee_carter",
    "projetar_lee_carter",
]
