# Passo 2 — Modelo Individual de Sobrevivência

**Dupla responsável:** Caio Brandão Santos e Pedro Lucas Figueiredo Santana  
**Bloco do escopo:** Multiestado e survival analytics (§6)

O MVP estima sobrevivência até óbito desde o ingresso usando idade ao ingresso,
sexo, tipo de plano e submassa. Kaplan-Meier descreve a massa; Cox é o baseline
e Random Survival Forest (RSF) é o challenger. Aposentadoria e invalidez não
encerram o acompanhamento. Desligamento anterior ao óbito e a data de referência
censuram o acompanhamento. Riscos competitivos estão fora desta entrega.

## Fonte e dependência do Passo 1

A execução oficial lê as tabelas **finais e curadas** do Postgres do Passo 1.
O banco pode ser iniciado em outra cópia/branch `feat/ambiente-de-dados`, seguindo
o README de `ambiente-de-dados/`. Não é necessário mesclar o gerador nessa branch.
Alinhar com a dupla do Passo 1 a versão, lote, seed, quantidade e referência.

A consulta seleciona o snapshot atual por participante, agrega óbitos e agrega
exposições **antes** da junção, preservando uma linha por pessoa. A duração é
calculada pelas datas; a soma de `exposicao.tempo_exposto` é guardada para auditoria.
Ela usa dias inclusivos/teto anual e pode diferir da duração contínua. Diferenças
acima de 0,03 ano e ausência de exposição são contadas no manifesto, para inspeção.
Não há alteração automática das datas com base nessa soma.

`--fonte banco` é o padrão e **nunca recorre ao gerador local se falhar**.
`--fonte local` é uma fixture independente para desenvolvimento, não reproduz o
pipeline oficial. Por padrão, seus arquivos ficam em `data/local/`.

## Execução oficial

Na raiz do repositório:

```bash
cd survival-analysis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Conexão via `PGHOST`, `PGPORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD`
(mesmos defaults de desenvolvimento do Passo 1; porta 5433). O script não carrega
`.env` automaticamente: exporte as variáveis se o ambiente usar outros valores.

Exemplo de rodada — **substitua a identificação, referência e corte pelos valores
alinhados com o grupo antes de avaliar os resultados**. O corte e o horizonte
não devem ser escolhidos procurando melhorar o desempenho de teste.

```bash
python scripts/construir_dataset.py --fonte banco --data-referencia 2026-08-31 --identificacao-fonte "SUBSTITUIR: commit do Passo 1 e lote/seed/n da rodada"
python scripts/kaplan_meier.py
python scripts/cox_ph.py
python scripts/comparar_modelos.py --data-corte 2016-01-01 --horizonte 5
```

`cox_ph.py` ajusta a massa completa apenas para descrição (HR, Schoenfeld e
C-index **de treino**). `comparar_modelos.py` refaz o Cox e o RSF no mesmo treino
para calcular discriminação e calibração no teste; é a avaliação de referência.
`survival_forest.py` continua disponível como diagnóstico aleatório exploratório,
sem função de escolher o modelo, e não é necessário executá-lo no fluxo oficial.

## Saídas e rastreabilidade

- `data/dataset_survival.csv`: IDs, datas, categorias originais, dummies e fonte.
- `dataset_survival.bruto.csv`, `.exclusoes.csv` e `.metadata.json`: extração,
  motivos por participante, identificação declarada do lote, hashes, comando,
  versões e contagens. Nenhuma senha é registrada.
- `data/graficos/`: KM e log-rank por sexo, BD/CD/CV e Plano A/B/C, com contagens.
- `data/metricas_cox_treino.csv`: métricas aparentes, não usadas para promoção.
- `data/avaliacao/resultado.json`: procedência, corte, grade, métricas dos dois
  modelos, motivos de indisponibilidade, critérios e veredito.
- `data/avaliacao/divisao_temporal.csv`: IDs, datas e desfechos efetivamente usados
  em cada conjunto, inclusive a censura de treino no corte.
- `data/avaliacao/calibracao.csv`, `calibracao.png` e `metricas_subgrupos.csv`:
  calibração previsto versus KM por grupos de risco e avaliação por sexo, plano,
  submassa e faixas de idade no ingresso.

`--saida` no comparador permite outro diretório de rodada. Não reutilize o mesmo
diretório para experimentos que precisem ser preservados. Os dados e resultados
gerados não são versionados automaticamente; registre a rodada aprovada nos
[documentos do experimento](docs/experiment_record.md) e no [model card](docs/model_card.md).

## Desenho da avaliação

Treino = ingresso anterior ao corte, com desfechos posteriores **censurados no
corte**. Teste = ingresso no corte ou depois, acompanhado até evento/saída/referência.
O cadastro é o snapshot atual extraído, portanto essa simulação por calendário
não reconstitui integralmente o conhecimento bitemporal disponível naquela época.

C-index usa risco positivo no Cox. Brier/IBS usam as mesmas pessoas, grade e pesos
IPCW estimados no treino. Calibração direta compara probabilidade média prevista
de óbito com `1 − KM(horizonte)` e fornece IC95% observado e curvas por tercis de
risco. Essa medida global não é ICI; não detecta todos os erros individuais.

Métrica sem suporte vem com motivo, não com zero. Nenhum modelo é promovido por
falta de evidência. Os critérios completos e limites estão no model card.

## Verificação automatizada

```bash
python -m unittest discover -s tests -v
python scripts/construir_dataset.py --fonte local --data-referencia 2026-08-31 --n-participantes 2000 --saida data/teste_integracao/dataset_survival.csv
python scripts/kaplan_meier.py --dataset data/teste_integracao/dataset_survival.csv
python scripts/comparar_modelos.py --dataset data/teste_integracao/dataset_survival.csv --data-corte 2016-01-01 --horizonte 5
```

Os 2.000 registros são uma fixture de teste do software, não substituem a massa
da tribo nem recomendam alterar a taxa de óbitos do gerador oficial.

**A estimativa individual é insumo analítico para gestão de risco coletivo,
nunca decisão automática sobre direitos individuais.**
