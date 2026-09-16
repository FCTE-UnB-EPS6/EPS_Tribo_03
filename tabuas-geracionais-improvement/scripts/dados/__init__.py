"""
Pacote de Ingestão e Agregação de Dados Históricos — Passo 6
"""

from .db import conectar
from .ingestao_passos import (
    carregar_historico_mortalidade,
    carregar_tabua_base_passo5,
    carregar_premissas_passo4,
)
from .series_temporais import carregar_dados, gravar_csv

__all__ = [
    "conectar",
    "carregar_historico_mortalidade",
    "carregar_tabua_base_passo5",
    "carregar_premissas_passo4",
    "carregar_dados",
    "gravar_csv",
]
