# Passo 7: Explicabilidade e Model Risk

**Dupla responsável:** D3.7, Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega
**Slice:** SL-07 (Issue `FCTE-UnB-EPS6/estudos-populacionais#53`)
**Bloco do escopo:** Ensemble e diagnóstico probabilístico (Passos 7 e 8)
**Risco (GOV-004):** R3 (modelo estatístico/IA e dados)

---

## O que esta pasta faz

Explica **por que** os modelos de mortalidade da Tribo 3 dão os resultados que dão e **quais riscos** eles carregam (model risk), sem treinar nem alterar esses modelos. Os modelos são de outras duplas; aqui só lemos o que eles publicam pelos contratos.

A SL-07 é entregue em 3 etapas, uma por modelo de origem:

| Etapa | Modelo explicado | Situação |
|---|---|---|
| **1** | **Lee-Carter, Passo 6** (tábua geracional) | **Esta entrega** |
| 2 | Tábua própria, Passo 5 | Aguarda a tábua consolidada no Postgres real |
| 3 | Cox e Random Survival Forest, Passo 2 | Aguarda o Passo 2 rodar na massa calibrada |

## Etapa 1: Lee-Carter em 1 minuto

O Lee-Carter descreve a mortalidade de cada idade *x* em cada ano *t* assim:

    ln m(x,t) = alpha_x + beta_x · kappa_t        e        q(x,t) = 1 − exp(−m(x,t))

- **alpha_x:** nível médio de mortalidade da idade *x* (sobe com a idade).
- **kappa_t:** "termômetro" geral da mortalidade no ano *t* (cai quando a mortalidade melhora).
- **beta_x:** o quanto a idade *x* acompanha o termômetro.
- **drift:** quanto o kappa_t cai por ano em média; é o que projeta o futuro.

O script `scripts/explicar_lee_carter.py`:

1. lê alpha_x, beta_x, kappa_t e drift pelo contrato do Passo 6, `obter_parametros_para_passo7()`, sem alterá-lo;
2. recalcula q(x,t) com a fórmula do Passo 6 para 2015-2024 (histórico, com o kappa_t ajustado de cada ano) e 2025-2054 (projeção de 30 anos, idêntica ao Passo 6);
3. faz **checagens de plausibilidade**: se alguma falhar, a explicação **não é publicada** (status `BLOQUEADO`);
4. gera **alertas de model risk**, que não bloqueiam mas ficam registrados;
5. calcula o **ALE** (efeito médio de idade e de ano sobre q) e o **SHAP** (quanto idade e ano contribuem para cada q);
6. salva gráficos PNG e o relatório JSON (contrato v1.0.0) em `docs/lee_carter/`.

O que cada técnica significa e como ler os resultados está em [`docs/model_card_lee_carter.md`](docs/model_card_lee_carter.md).

## Primeira vez (instalação)

Pré-requisito: Python 3.12 e a pasta do Passo 6 (`../tabuas-geracionais-improvement/`) no mesmo repositório.

```bash
# fora do repositório, para o ambiente virtual não entrar em commits
cd /caminho/para/fora/do/repositorio
python3 -m venv venv
source venv/bin/activate
pip install -r <repositorio>/TRIBO3-DADOS-ESTATÍSTICA-E-IA/explicabilidade-model-risk/requirements.txt
```

No Windows (PowerShell):

```powershell
cd C:\caminho\para\fora\do\repositorio
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
pip install -r <repositorio>\TRIBO3-DADOS-ESTATÍSTICA-E-IA\explicabilidade-model-risk\requirements.txt
```

O Passo 6 usa a série do IBGE já versionada no repositório. **Não precisa de Docker nem de Postgres** nesta etapa.

## Como rodar

De dentro de `explicabilidade-model-risk/`, com o venv ativado:

```bash
python scripts/explicar_lee_carter.py
```

Para ver o código de saída: `echo $?` no bash, `echo $LASTEXITCODE` no PowerShell.

- Código de saída `0`: relatório `APROVADO`.
- Código de saída `1`: relatório `BLOQUEADO`. O motivo aparece no terminal (linhas `ERROR BLOQUEADO`) e no JSON.
- Linhas `WARNING ALERTA` são achados de model risk; ver [`docs/limitacoes-e-vieses.md`](docs/limitacoes-e-vieses.md).

## Como testar

```bash
python -m pytest -v
```

São 30 testes. A maior parte usa um **Lee-Carter de brinquedo**, com parâmetros escolhidos à mão para que a resposta seja conhecida. Os testes `test_integracao_*` usam o **contrato real** do Passo 6. Testes com brinquedo não comprovam a integração; só os de integração comprovam.

## Estrutura

```text
explicabilidade-model-risk/
├── README.md                       # este arquivo
├── requirements.txt                # dependências com versão fixa
├── .gitignore                      # ignora cache do Python e do pytest
├── scripts/
│   └── explicar_lee_carter.py      # Etapa 1: explicação do Lee-Carter
├── schemas/
│   └── relatorio_explicabilidade.schema.json   # contrato v1.0.0 do relatório JSON
├── tests/
│   └── test_explicar_lee_carter.py # unitários (brinquedo) + integração (contrato real)
└── docs/
    ├── model_card_lee_carter.md        # card de explicabilidade e model risk do Lee-Carter
    ├── experiment_record_lee_carter.md # rodadas: data, versões, parâmetros, resultados, quem rodou
    ├── decisoes.md                     # decisões, alternativas e motivos
    ├── limitacoes-e-vieses.md          # limitações, vieses e alertas de model risk
    ├── reidentificacao.md              # análise de reidentificação (para a Tribo 4)
    ├── evidencias.md                   # comando, resultado e commit de cada evidência
    └── lee_carter/                     # saídas geradas pelo script (JSON + PNG)
```

## Contratos

| Direção | Contrato | Versão | Alteração |
|---|---|---|---|
| Entrada | `tabuas-geracionais-improvement/contracts/api_modelos.py::obter_parametros_para_passo7()` | do Passo 6 | **nenhuma** (só leitura) |
| Saída | `schemas/relatorio_explicabilidade.schema.json` | **1.0.0** | novo |

Consumidores da saída: Tribo 1 (explicações para o dashboard), Tribo 6 (evidências) e SL-08 (#54) desta dupla.

## Uso responsável

Este trabalho explica um modelo de **mortalidade populacional agregada**. O resultado é insumo para a gestão coletiva de risco atuarial e **nunca** deve ser usado para decisão automática sobre pessoas.
