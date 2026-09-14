# Passo 6 — Tábuas Geracionais e Mortality Improvement

**Dupla responsável:** Danielle Soares da Silva e Maria Eduarda Quaresma de Andrade  
**Bloco do escopo:** Tábuas geracionais e improvement (§6)

---

## Visão Geral

Consome as bases históricas de `exposicao` (produzidas no Passo 1) e a tábua biométrica própria consolidada no Passo 5 para construir a **Tábua Biométrica Geracional (Dinâmica) e a Escala de Mortality Improvement** da Tribo 3.

No Passo 5, foi produzida uma taxa estática $q_x$ (probabilidade de morte fixa por idade no período base). No entanto, em planos de previdência e fundos de pensão, a mortalidade decresce ao longo do tempo (as pessoas vivem mais a cada geração). Projetar passivos atuariais com uma tábua estática gera subavaliação do risco de longevidade e déficit atuarial.

O **Passo 6** resolve isso projetando $q(x, t)$ (idade $x$ no ano de calendário $t$), garantindo conformidade estrita com o Definition of Done (§3/§8 DoD):

1. **Séries Temporais Históricas** (`scripts/series_temporais.py`): extrai e agrega óbitos e exposição por ano de calendário e idade inteira.
2. **Teste de Tendência de Mann-Kendall** (`scripts/teste_mann_kendall.py`): teste estatístico não-paramétrico exigido pelo DoD para confirmar a direção e significância estatística do *mortality improvement*.
3. **Testes de Estacionariedade ADF e KPSS** (`scripts/teste_estacionariedade.py`): avaliação econométrica de raiz unitária na série temporal de mortalidade, fundamentando a modelagem via passeio aleatório com *drift*.
4. **Modelo Baseline de Projeção** (`scripts/modelo_baseline.py`): modelo atuarial de referência (extrapolação de melhoria anual geométrica/exponencial $f_x$).
5. **Modelo Estocástico de Lee-Carter** (`scripts/modelo_lee_carter.py`): decomposição canônica via SVD ($\ln(m_{x,t}) = \alpha_x + \beta_x \kappa_t$) e projeção de $\kappa_t$ por Random Walk with Drift.
6. **Backtesting Temporal** (`scripts/backtest_temporal.py`): holdout temporal nos anos mais recentes; o modelo complexo (Lee-Carter) só é adotado se obtiver ganho mensurável no RMSE fora da amostra (critério DoD).
7. **Consolidação da Tábua Geracional** (`scripts/tabua_geracional.py`): geração da matriz de projeção $q(x,t)$ para um horizonte de 30 anos, com taxas anuais de *improvement* e tabela formatada por coorte.

---

## Estrutura de Diretórios

```text
tabuas-geracionais-improvement/
├── README.md
├── docs/
│   ├── data_card.md
│   ├── model_card.md
│   ├── experiment_record.md
│   ├── series_temporais/         # CSVs da série histórica observada
│   ├── testes_estatisticos/      # Relatórios de Mann-Kendall, ADF e KPSS
│   ├── backtest/                 # Avaliação comparativa de erro fora da amostra
│   └── tabua_geracional/         # Tábua oficial projetada q(x, t) em CSV e Markdown
├── dashboard/
│   ├── README.md                 # Instruções de visualização
│   ├── gerar_preview.py          # Script gerador do dashboard
│   └── preview.html              # Dashboard interativo autocontido (abra no navegador)
├── scripts/
│   ├── README.md                 # Documentação técnica e guia de execução
│   ├── requirements.txt          # Dependências do projeto
│   ├── main.py                   # 1. Arquivo principal (executa todo o fluxo do Passo 6)
│   ├── pipeline.py               # Atalho para main.py
│   ├── config.py                 # 2. Arquivo de configuração (docs/ e constantes atuariais)
│   ├── db.py                     # Conexão com banco de dados PostgreSQL
│   ├── series_temporais.py       # Etapa 1: Agregação da série histórica
│   ├── teste_mann_kendall.py     # Etapa 2: Teste estatístico de tendência de queda
│   ├── teste_estacionariedade.py # Etapa 3: Testes de raiz unitária ADF e KPSS
│   ├── modelo_baseline.py        # Modelo simples de redução anual (fx)
│   ├── modelo_lee_carter.py      # Modelo estocástico Lee-Carter
│   ├── backtest_temporal.py      # Etapa 4: Backtest temporal e seleção Champion-Challenger
│   └── tabua_geracional.py       # Etapa 5: Tábua geracional consolidada a 30 anos
└── tests/
    └── test_passo6.py            # Suíte de testes automatizados
```

---

## Como Rodar

### 1. Instalação das dependências
```bash
pip install -r scripts/requirements.txt
```

### 2. Execução Completa via Pipeline
Roda as 5 etapas em sequência metodológica e para no primeiro erro:
```bash
python scripts/pipeline.py
```

### 3. Execução Isolada de Etapas
Cada etapa pode ser executada individualmente:
```bash
python scripts/series_temporais.py
python scripts/teste_mann_kendall.py
python scripts/teste_estacionariedade.py
python scripts/backtest_temporal.py
python scripts/tabua_geracional.py
```

### 4. Execução dos Testes Automatizados
```bash
python -m unittest tests/test_passo6.py
```

---

## Saídas Geradas

- `docs/series_temporais/serie_historica_<data>.csv`: matriz histórica de óbitos, exposição, $m_x$ e $q_x$ por ano e idade.
- `docs/testes_estatisticos/teste_mann_kendall_<data>.md`: estatísticas $S$, $Z$, $p$-valor e confirmação de tendência de queda de mortalidade.
- `docs/testes_estatisticos/teste_estacionariedade_<data>.md`: estatísticas ADF e KPSS comprovando a presença de tendência/raiz unitária.
- `docs/backtest/backtest_temporal_<data>.md`: comparativo de RMSE, MAE e Qui-quadrado entre Baseline e Lee-Carter, com o veredito de seleção.
- `docs/tabua_geracional/tabua_geracional_<data>.csv`: a saída final com `ano_calendario`, `idade`, `coorte_nascimento`, `qx_projetado` e `improvement_anual_pct`.
- `docs/tabua_geracional/tabua_geracional_<data>.md`: resumo executivo e tabela de evolução para idades chave.

---

## Integração Intertribos

- **Passo 7 (Explicabilidade / SHAP / ALE):** Consome os parâmetros estimados ($\alpha_x, \beta_x, \kappa_t$) para gerar curvas de sensibilidade.
- **Passo 8 (Ensemble e Diagnóstico Probabilístico):** Consome as projeções e resíduos para calibração de intervalos e choques de longevidade (CVaR).
- **Tribo 2 (Backend / APIs):** Consome a tábua geracional oficial em formato de contrato de dados versionado para simulações atuariais.
