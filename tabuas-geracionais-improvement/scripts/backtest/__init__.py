"""
Pacote de Avaliação, Backtesting Temporal e Seleção Champion-Challenger — Passo 6
"""

from .backtest_temporal import (
    separar_treino_holdout,
    avaliar_previsoes,
    executar_backtest,
    montar_relatorio,
)

__all__ = [
    "separar_treino_holdout",
    "avaliar_previsoes",
    "executar_backtest",
    "montar_relatorio",
]
