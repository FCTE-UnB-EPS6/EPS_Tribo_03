"""
Passo 6 — Tábuas Geracionais e Mortality Improvement (Tribo 3)

Estrutura modular de pacotes:
    - dados: ingestão PostgreSQL, fallback HMD/IBGE e séries temporais
    - estatistica: testes de hipótese Mann-Kendall, ADF e KPSS
    - modelos: modelos Baseline e Lee-Carter (SVD + Drift)
    - backtest: avaliação Champion-Challenger e métricas fora da amostra
    - projecao: tábua geracional oficial projetada a 30 anos
"""

from .config import (
    HORIZONTE_PROJECAO_ANOS,
    LIMIAR_GANHO_COMPLEXIDADE,
    ALPHA,
    LIMITE_FX_MAX,
    PROPORCAO_HOLDOUT,
)

__all__ = [
    "HORIZONTE_PROJECAO_ANOS",
    "LIMIAR_GANHO_COMPLEXIDADE",
    "ALPHA",
    "LIMITE_FX_MAX",
    "PROPORCAO_HOLDOUT",
]
