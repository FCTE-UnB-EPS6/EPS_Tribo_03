"""
Passo 6 — Configurações e Constantes Centrais

Centraliza caminhos do projeto, diretórios de documentação e saídas,
além das constantes metodológicas e parâmetros atuariais/estatísticos.
"""

from pathlib import Path

# Diretórios Principais
PASTA_SCRIPTS = Path(__file__).resolve().parent
PASTA_RAIZ_PASSO6 = PASTA_SCRIPTS.parent
PASTA_DOCS = PASTA_RAIZ_PASSO6 / "docs"

# Diretórios de Saída de Artefatos
PASTA_SERIES_TEMPORAIS = PASTA_DOCS / "series_temporais"
PASTA_TESTES_ESTATISTICOS = PASTA_DOCS / "testes_estatisticos"
PASTA_BACKTEST = PASTA_DOCS / "backtest"
PASTA_TABUA_GERACIONAL = PASTA_DOCS / "tabua_geracional"

# Caminhos para integração com outros passos (sem acoplamento)
RAIZ_PROJETO = PASTA_RAIZ_PASSO6.parent
PASTA_PASSO1_REFS = RAIZ_PROJETO / "ambiente-de-dados" / "docs" / "referencias"
PASTA_PASSO4_CONFIG = RAIZ_PROJETO / "cenarios-economicos" / "config"
PASTA_PASSO5_DOCS = RAIZ_PROJETO / "tabua-biometrica-propria" / "docs" / "tabua_propria"

# Parâmetros Atuariais e Metodológicos (DoD §3 e §8)
HORIZONTE_PROJECAO_ANOS = 30
LIMIAR_GANHO_COMPLEXIDADE = 0.05  # Ganho mínimo de 5% no RMSE para adotar Lee-Carter
ALPHA = 0.05                       # Nível de significância estatística (Mann-Kendall / ADF / KPSS)
LIMITE_FX_MAX = 0.035              # Trava atuarial máxima de melhoria anual (3.5% a.a.)
PROPORCAO_HOLDOUT = 0.25           # Fração de anos recentes reservados para teste cego no backtest
