# Tribo 3 — Ambiente de dados (Postgres + migrations + massa sintética)

Implementa o documento *"Desenho do Banco de Dados de Referência (Massa
Sintética)"*: schema bitemporal, gerador de massa sintética com imperfeições
controladas, pipeline de qualidade e gabarito para medir precision/recall da
limpeza.

## Estrutura

```text
tribo3/
  docker-compose.yml
  .env.example
  migrations/
    V1__schema_inicial.sql           7 tabelas do §3 + gabarito do §5.2
    V2__enum_datas_fora_ordem.sql    9º tipo de imperfeição do §5.1
    V3__staging_cpf_e_constraints.sql camada staging + cpf_sintetico
    R__dicionario_dados.sql          catálogo do §3.6 (repeatable)
    R__referencia_externa.sql        as 4 fontes do §1 (repeatable)
  scripts/
    gerar_dataset.py             gera a massa (simulação ano a ano) e escreve no staging
    calibracao.py                qx real do IBGE 2024 + premissas declaradas -- insumo do gerador
    extrator_ibge_historico.py   série histórica de qx (2015-2024), insumo do Passo 6
    injetores.py                 os 9 tipos de imperfeição do §5.1
    regras.py                    as 9 regras de qualidade
    pipeline_qualidade.py        valida, pontua, promove e mede precision/recall
    benchmark_ibge.py            Passo 3: qx sintético x IBGE 2024
    benchmark_hmd.py             Passo 3: qx sintético x HMD (Austrália)
    benchmark_brems.py           Passo 3: qx sintético x BR-EMS
    benchmark_soa.py             Passo 3: qx sintético x SOA RP-2014
    seed.py                      orquestrador idempotente do compose
    dominio.py                   domínios e limiares compartilhados
    db.py                        conexão
  tests/
    test_calibracao.py               calibracao.py, contra o arquivo real do IBGE
    test_gerar_dataset.py            simular_trajetoria(), lógica pura
    test_extrator_ibge_historico.py  extrator_ibge_historico.py, URL + arquivos reais
  docs/
    regras_geracao.md      data card: distribuições, imperfeições, regras
    referencias/            arquivos brutos versionados (IBGE, HMD, BR-EMS, SOA)
    referencias/ibge_historico/  série histórica de qx 2015-2024 (gerada pelo extrator)
```

## Primeira vez

```bash
git clone <repo>
cd tribo3
cp .env.example .env
docker compose up -d
```

Isso sobe quatro serviços:

- **db** — Postgres 16, dados em volume Docker (não some ao reiniciar).
- **migrate** — Flyway, aplica `migrations/` em ordem. Roda uma vez e sai.
- **seed** — gera a massa sintética, roda o pipeline de qualidade e promove os
  dados. Roda uma vez e sai. **Idempotente**: se já houver dados, não faz nada.
- **pgadmin** — interface web em `http://localhost:5050`, credenciais do `.env`.

Ao terminar, o banco já está populado: staging preenchido, imperfeições
injetadas, scores calculados e as tabelas finais promovidas.

```bash
docker compose logs seed   # relatório de precision/recall por tipo de erro
```

## O que fica no banco

| Tabela | Conteúdo |
| --- | --- |
| `participante`, `evento`, `exposicao`, `contribuicao_beneficio` | dataset de análise, já curado |
| `staging.*` | entrada crua, com as imperfeições e o motivo de cada rejeição |
| `staging.v_rejeitados` | tudo que não foi promovido, com os códigos de regra |
| `data_quality_score` | scores nas 4 granularidades do §3.7 |
| `dicionario_dados` | catálogo do §3.6 |
| `gabarito.registro_erro_injetado` | erros plantados + se a limpeza pegou |
| `referencia_externa` | esqueleto das 4 fontes do §1, aguardando benchmark |

`referencia_externa` sai com `versao_tabua`, `data_consulta` e
`resultado_benchmark` nulos de propósito: eles só existem depois que alguém
baixar a tábua do IBGE/BR-EMS e rodar a comparação. Ela nunca é fonte de linhas
do dataset de entrada (§4).

## Conferir

```bash
# migrations aplicadas
docker compose logs migrate

# todo erro injetado foi avaliado (nao_avaliado deve ser 0)
docker compose exec db psql -U tribo3 -d tribo3 -c "
  SELECT tipo_erro, count(*) total,
         count(*) FILTER (WHERE detectado_pela_limpeza) detectados,
         count(*) FILTER (WHERE detectado_pela_limpeza IS NULL) nao_avaliado
  FROM gabarito.registro_erro_injetado GROUP BY 1 ORDER BY 1;"

# por que cada linha foi rejeitada
docker compose exec db psql -U tribo3 -d tribo3 -c "
  SELECT tabela_origem, unnest(motivos_rejeicao) motivo, count(*)
  FROM staging.v_rejeitados GROUP BY 1,2 ORDER BY 3 DESC;"
```

## Repopular do zero

```bash
docker compose down -v && docker compose up -d
```

`down -v` apaga o volume; sem o `-v` os dados ficam e o `seed` continua pulando.

## Rodar os scripts fora do container

```bash
pip install -r scripts/requirements.txt
cd scripts
python gerar_dataset.py --n-participantes 300 --seed 42
python pipeline_qualidade.py
```

Os defaults de conexão apontam para `localhost:5433` (a porta que o compose
publica no host). Ajuste via `PGHOST`/`PGPORT` se mudar o `.env`.

`gerar_dataset.py` precisa dos arquivos da Tábua Completa do IBGE 2024 em
`docs/referencias/` (já versionados) para calibrar o qx — sem eles,
`calibracao.py` lança `FileNotFoundError` explicando onde buscá-los. Ao
final da execução, o gerador imprime a distribuição de status realizada
e o qx bruto agregado — se sair com 0 óbitos, suba `--n-participantes`
(o Passo 5 fica sem numerador para o A/E).

## Série histórica de qx (insumo do Passo 6)

```bash
cd scripts
python extrator_ibge_historico.py                          # 2015-2024, default
python extrator_ibge_historico.py --ano-inicio 2018 --ano-fim 2024
```

Baixa (se ainda não tiver) as Tábuas Completas de Mortalidade do IBGE de
cada ano do intervalo, direto de `ftp.ibge.gov.br`, e consolida num único
CSV em `docs/referencias/ibge_historico/serie_historica_qx.csv` (colunas
`ano, sexo, idade, qx`). Só cobre 2015-2024 — antes disso o layout do FTP
do IBGE muda para `.zip` por ano, fora do escopo deste extrator (ver
docstring do módulo). Não baixa de novo um arquivo que já existe local.

## Rodar os testes

```bash
pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
```

Não precisa de Postgres nem Docker rodando — os testes exercitam
`calibracao.py`, `simular_trajetoria()` (o núcleo do gerador) e
`extrator_ibge_historico.py` isoladamente, contra os arquivos reais do
IBGE já versionados em `docs/referencias/`. O único teste que se
auto-pula é o de `test_extrator_ibge_historico.py` que depende da série
histórica já ter sido baixada (`python extrator_ibge_historico.py`
antes, uma vez).

## Volume, seed e reprodutibilidade

`N_PARTICIPANTES`, `SEED` e `DATA_REFERENCIA` vêm do `.env`. Mesma `SEED` +
mesma `DATA_REFERENCIA` produz um dataset idêntico, ids inclusive (§6). Com
`DATA_REFERENCIA` vazia o gerador usa a data de hoje — para reproduzir um lote
antigo, fixe a data.

## Mudar o schema

1. Nunca editar uma migration `V*` já aplicada — o Flyway valida checksum e
   falha.
2. Criar `migrations/V4__descricao_curta.sql`.
3. As `R__*.sql` (dicionário, referência externa) são *repeatable*: pode editar
   à vontade, o Flyway reaplica quando o conteúdo muda.
4. `docker compose up -d migrate`.

## Derrubar

```bash
docker compose down          # para os containers, mantém os dados
docker compose down -v       # para e APAGA os dados
```

## Próximo passo

A calibração de mortalidade (qx por idade/sexo, IBGE 2024) já está pronta
e testada. Falta extrair desligamento/aposentadoria/invalidez de fonte
real (RAIS/CAGED para desligamento, AEPS/PREVIC para aposentadoria) —
hoje `calibracao.py` declara esses três como premissa, não dado
calibrado (ver `PREMISSA` no módulo e no `DATASET_CARD.md`).
