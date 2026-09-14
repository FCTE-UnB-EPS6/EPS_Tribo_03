# Data Card — Tábuas Geracionais e Mortality Improvement (Passo 6)

## Propósito

Tábua biométrica geracional (dinâmica) e escala de melhoria de mortalidade (*mortality improvement*) da população da Tribo 3, fornecendo a evolução temporal das probabilidades de morte $q(x, t)$ para modelagem de risco de longevidade e cálculo atuarial.

## População

- **Fonte Primária:** Tabela `exposicao` (pós-pipeline de qualidade R01-R09 do Passo 1) e tabela `tabua_propria` consolidada no Passo 5.
- **Recorte Temporal Histórico:** Série de anos civis de exposição registrados na base (`exposicao.ano_calendario`).
- **Recorte Etário:** Idades a partir da maioridade (18 a 70+ anos), correspondendo à cobertura populacional sintética do gerador.
- **Unidade de Agregação:** Célula por `(ano_calendario, FLOOR(idade_exata))`.

## Dados de Entrada e Saída, por Etapa

| Etapa | Script | Entrada | Saída |
| :--- | :--- | :--- | :--- |
| Séries Temporais | `series_temporais.py` | Tabela `exposicao` do banco | `docs/series_temporais/*.csv` |
| Teste Mann-Kendall | `teste_mann_kendall.py` | Séries históricas de $m_{x,t}$ | `docs/testes_estatisticos/teste_mann_kendall_*.md` |
| Estacionariedade | `teste_estacionariedade.py` | Séries temporais de $\ln(m_t)$ | `docs/testes_estatisticos/teste_estacionariedade_*.md` |
| Modelo Baseline | `modelo_baseline.py` | Séries históricas de treino | Parâmetros $f_x$ e $q_{x, t_0}$ |
| Modelo Lee-Carter | `modelo_lee_carter.py` | Matriz histórica de $m_{x,t}$ | Parâmetros $\alpha_x, \beta_x, \kappa_t, d$ |
| Backtesting Temporal | `backtest_temporal.py` | Treino vs Holdout | `docs/backtest/backtest_temporal_*.md` |
| Tábua Geracional | `tabua_geracional.py` | Modelo Campeão + Passo 5 | `docs/tabua_geracional/*.csv` e `*.md` |

## Limitações dos Dados e Cuidados Atuariais

1. **Volume Amostral em Idades Extremas:** Como a massa sintética base possui amostragem centrada em participantes ativos (18 a 70 anos), células com idade acima de 70 anos apresentam menor densidade de exposição, exigindo regularização e travas atuariais de plausibilidade nas taxas anuais de *improvement* ($0 \le f_x \le 0.035$).
2. **Janela Histórica:** A robustez da decomposição SVD de Lee-Carter melhora com séries históricas mais longas. Na presença de poucos anos observados, o gate de seleção do DoD favorece o modelo Baseline de extrapolação linear se Lee-Carter apresentar sobreajuste (*overfitting*).
