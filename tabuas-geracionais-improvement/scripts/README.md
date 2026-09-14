# Scripts — Passo 6: Tábuas Geracionais e Mortality Improvement

Esta pasta contém os scripts de execução, modelagem atuarial e testes estatísticos do **Passo 6**.

A estrutura foi desenhada de forma enxuta, clara e direta:
1. **Arquivo Principal (`main.py`)**: inicializa e executa todas as etapas sequencialmente.
2. **Arquivo de Configuração (`config.py`)**: centraliza caminhos de pastas (`docs/`) e parâmetros atuariais compartilhados.
3. **Scripts de Etapas**: arquivos diretos e autocontidos para cada parte do fluxo atuarial.

---

## 1. Estrutura de Arquivos

```text
scripts/
├── main.py                  # 1. Arquivo principal (roda toda a esteira do Passo 6)
├── pipeline.py              # Atalho / alias para main.py
├── config.py                # 2. Arquivo de configuração (caminhos docs/ e constantes atuariais)
├── db.py                    # Conexão com banco de dados PostgreSQL
├── series_temporais.py      # Etapa 1: Agregação da série histórica e dados sintéticos
├── teste_mann_kendall.py    # Etapa 2: Teste não-paramétrico de tendência de queda
├── teste_estacionariedade.py# Etapa 3: Testes de raiz unitária ADF e KPSS
├── modelo_baseline.py       # Modelo simples de redução geométrica anual (fx)
├── modelo_lee_carter.py     # Modelo estocástico Lee-Carter via SVD e Random Walk
├── backtest_temporal.py     # Etapa 4: Backtesting temporal e duelo de modelos (DoD)
├── tabua_geracional.py      # Etapa 5: Projeção final da tábua geracional para 30 anos
├── requirements.txt         # Dependências do Python
└── README.md                # Esta documentação
```

---

## 2. Como Executar

### Execução Completa (Recomendado)
Para rodar toda a esteira de uma só vez (as 5 etapas em sequência):
```bash
python scripts/main.py
```
*(Ou através do atalho: `python scripts/pipeline.py`)*

### Execução de uma Etapa Específica
Cada script pode ser executado individualmente a qualquer momento:
```bash
python scripts/series_temporais.py
python scripts/teste_mann_kendall.py
python scripts/teste_estacionariedade.py
python scripts/modelo_baseline.py
python scripts/modelo_lee_carter.py
python scripts/backtest_temporal.py
python scripts/tabua_geracional.py
```

---

## 3. Relação entre as Etapas

As etapas não são isoladas; elas formam uma **esteira encadeada**:
1. `series_temporais.py` gera a base histórica de exposição e óbitos.
2. `teste_mann_kendall.py` e `teste_estacionariedade.py` comprovam a tendência estatística de queda na mortalidade e a presença de raiz unitária na série da etapa 1.
3. `modelo_baseline.py` e `modelo_lee_carter.py` ajustam suas curvas com base na etapa 1.
4. `backtest_temporal.py` testa os dois modelos contra os anos recentes da etapa 1 e decide o campeão (princípio de parcimônia do DoD).
5. `tabua_geracional.py` usa o modelo campeão para consolidar a tábua oficial para os próximos 30 anos.
