# Passo 2 — Modelo Individual de Sobrevivência

**Dupla responsável:** Caio Brandão Santos e Pedro Lucas Figueiredo Santana  
**Bloco do escopo:** Multiestado e survival analytics (§6)

## Visão geral

Modelo individual de sobrevivência a partir da massa sintética do Passo 1, estimando a probabilidade de transição de estado (ativo → óbito, invalidez, aposentadoria, desligamento) ao longo do tempo.

## Estrutura

```
survival-analysis/
├── README.md                  # este arquivo
├── requirements.txt           # dependências Python
├── scripts/
│   ├── construir_dataset.py   # extrai dataset analítico do banco
│   ├── kaplan_meier.py        # baseline: estimador KM por subgrupo
│   ├── cox_ph.py              # baseline: modelo de Cox PH
│   ├── survival_forest.py     # challenger: Random Survival Forest
│   └── comparar_modelos.py    # comparação champion-challenger
├── docs/
│   ├── model_card.md          # propósito, população, métricas, limitações
│   └── experiment_record.md   # registro de cada rodada experimental
└── data/                      # datasets analíticos gerados (não versionados)
```

## Dependências

Depende do Passo 1 (participante, evento e exposição estáveis). O núcleo do Passo 1 já está pronto.

## Como rodar

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Gerar o dataset analítico (requer Postgres do Passo 1 rodando)
python scripts/construir_dataset.py

# 3. Rodar o baseline (Kaplan-Meier)
python scripts/kaplan_meier.py

# 4. Rodar o baseline (Cox PH)
python scripts/cox_ph.py

# 5. Rodar o challenger (Random Survival Forest)
python scripts/survival_forest.py

# 6. Comparar modelos
python scripts/comparar_modelos.py
```

## Decisões de projeto

- **Baseline antes de complexidade**: Kaplan-Meier e Cox primeiro, Survival Forest só se houver ganho mensurável.
- **Evento de interesse do MVP**: óbito (evento terminal mais claro para survival analysis previdenciária).
- **Censura**: participantes ativos ou desligados por motivo diferente de óbito são censurados na data de saída ou na data de referência.
- **Covariáveis**: idade ao ingresso, sexo, plano_tipo, submassa — verificadas para multicolinearidade antes da inclusão.
- **A estimativa individual é insumo analítico para gestão de risco coletivo, nunca decisão automática sobre direitos individuais** — restrição explícita do escopo.
