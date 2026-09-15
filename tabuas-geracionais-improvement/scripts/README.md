# Scripts — Passo 6: Tábuas Geracionais e Mortality Improvement

Esta pasta contém os scripts de execução, modelagem atuarial e testes estatísticos do **Passo 6**, organizados em subpacotes modulares por responsabilidade técnica.

---

## 1. Estrutura Modular de Pastas

```text
scripts/
├── config.py                 # Configurações centrais, caminhos (docs/) e constantes atuariais
├── main.py                   # Orquestrador principal sequencial (roda todo o fluxo)
├── pipeline.py               # Atalho retrocompatível para main.py
├── requirements.txt          # Dependências do Python
├── __init__.py               # Inicializador do pacote de scripts
│
├── dados/                    # Pacote de Ingestão e Agregação Histórica
│   ├── __init__.py
│   ├── db.py                 # Conexão com banco de dados PostgreSQL (Passo 1)
│   ├── ingestao_passos.py    # Ingestão interpassos com fallback real (Passos 1, 3, 4 e 5)
│   └── series_temporais.py   # Etapa 1: Agregação da série histórica em células (ano x idade)
│
├── estatistica/              # Pacote de Testes Estatísticos e Hipóteses
│   ├── __init__.py
│   ├── teste_mann_kendall.py # Etapa 2: Teste não-paramétrico de tendência de queda (DoD)
│   └── teste_estacionariedade.py # Etapa 3: Testes de raiz unitária ADF e KPSS
│
├── modelos/                  # Pacote de Modelos Preditivos de Mortalidade
│   ├── __init__.py
│   ├── baseline.py           # Modelo simples de redução geométrica anual (fx)
│   └── lee_carter.py         # Modelo estocástico Lee-Carter via SVD e Random Walk
│
├── backtest/                 # Pacote de Avaliação Fora da Amostra
│   ├── __init__.py
│   └── backtest_temporal.py  # Etapa 4: Backtesting cego e seleção Champion-Challenger (DoD)
│
└── projecao/                 # Pacote de Consolidação Final
    ├── __init__.py
    └── tabua_geracional.py   # Etapa 5: Projeção final da tábua geracional para 30 anos
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
Cada script pode ser executado individualmente a qualquer momento diretamente da sua subpasta:
```bash
python scripts/dados/series_temporais.py
python scripts/estatistica/teste_mann_kendall.py
python scripts/estatistica/teste_estacionariedade.py
python scripts/modelos/baseline.py
python scripts/modelos/lee_carter.py
python scripts/backtest/backtest_temporal.py
python scripts/projecao/tabua_geracional.py
```

---

## 3. Relação entre as Etapas

As etapas formam uma **esteira encadeada**:
1. `dados/series_temporais.py` extrai e consolida a base histórica de exposição e óbitos.
2. `estatistica/teste_mann_kendall.py` e `estatistica/teste_estacionariedade.py` comprovam a tendência estatística de queda na mortalidade e a presença de raiz unitária na série histórica.
3. `modelos/baseline.py` e `modelos/lee_carter.py` calibram suas curvas e índices temporais com base nos dados.
4. `backtest/backtest_temporal.py` testa os dois modelos contra os anos recentes da amostra (holdout) e decide o modelo campeão (princípio de parcimônia do DoD).
5. `projecao/tabua_geracional.py` utiliza o modelo campeão para consolidar a tábua oficial para os próximos 30 anos.
