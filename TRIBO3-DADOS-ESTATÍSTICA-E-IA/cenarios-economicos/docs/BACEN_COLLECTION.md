# Coleta de dados brutos do Bacen SGS

Uma fixture real pequena do IPCA/SGS e o teste de integração opt-in estão
descritos em [Fixtures reais e integrações ao vivo](PHASE8_REAL_DATA_TESTS.md).

Versao do coletor: `0.1.0`

O coletor baixa e preserva respostas JSON do Sistema Gerenciador de Series
Temporais do Banco Central. Ele nao anualiza taxas, nao calcula retornos e nao
alimenta automaticamente o gerador de cenarios. Essas transformacoes pertencem
a uma etapa posterior de normalizacao e calibracao.

## Series catalogadas

| Chave | Codigo SGS | Frequencia | Unidade declarada no manifesto |
|---|---:|---|---|
| `selic_daily` | 11 | diaria | percentual ao dia |
| `selic_target` | 432 | diaria | percentual ao ano |
| `cdi` | 12 | diaria | percentual ao dia |
| `ipca` | 433 | mensal | percentual ao mes |
| `igpm` | 189 | mensal | percentual ao mes |
| `usd_brl` | 1 | diaria | reais por dolar dos Estados Unidos |

Os codigos identificam series com semanticas diferentes. Em particular, as
series 11 e 432 nao devem ser tratadas como valores intercambiaveis.

## Execucao

Dentro de `cenarios-economicos/`:

```bash
python3 scripts/collect_bacen.py \
  --start 2015-01-01 \
  --end 2026-09-17 \
  --output data/raw/bacen
```

Por padrao, todas as series sao coletadas. Para limitar a execucao, repita
`--series`, por exemplo:

```bash
python3 scripts/collect_bacen.py \
  --start 2025-01-01 \
  --series ipca \
  --series selic_target
```

A data final padrao e a data corrente. Periodos longos sao divididos em janelas
contiguas de no maximo 3.640 dias para permanecer abaixo do limite de dez anos
por consulta do SGS.

## Estrutura do snapshot

Uma execucao bem-sucedida cria um diretorio novo:

```text
data/raw/bacen/bacen-sgs-AAAAMMDDTHHMMSSZ-identificador/
  manifest.json
  raw/
    ipca/
      AAAA-MM-DD_AAAA-MM-DD.json
    selic_daily/
      AAAA-MM-DD_AAAA-MM-DD.json
```

Os arquivos em `raw/` contem exatamente os bytes retornados pela API. O
`manifest.json` registra:

- fonte, versao do coletor e instante UTC da coleta;
- periodo total solicitado e cada janela efetivamente consultada;
- URL completa de cada requisicao;
- codigo, frequencia e unidade declarada de cada serie;
- quantidade de registros, quantidade de bytes e SHA-256 de cada arquivo.

O diretorio e publicado somente depois que todas as series forem validadas. Uma
falha de rede, JSON invalido, mudanca inesperada no envelope ou serie totalmente
vazia remove a area temporaria e nao deixa um snapshot parcial com aparencia de
sucesso.

## Testes

Os testes usam um transportador em memoria e nao dependem da disponibilidade da
API externa:

```bash
python3 -m unittest tests.test_bacen_collector -v
```

Eles verificam janelas longas sem sobreposicao, preservacao exata dos bytes,
hashes, manifesto, rejeicao de respostas invalidas e ausencia de snapshots
parciais. Uma consulta curta a API real deve ser usada como smoke test antes de
publicar uma nova versao do coletor.

## Transformacoes posteriores

O manifesto prova quais bytes foram usados e como eles foram obtidos, mas nao
aprova a semantica economica de uma transformacao. As regras metodologicas foram
definidas separadamente na
[politica de transformacoes de frequencia](FREQUENCY_TRANSFORMATIONS.md),
incluindo:

- composicao das taxas diarias Selic e CDI;
- composicao dos indices mensais IPCA e IGP-M;
- calculo de retornos a partir dos niveis do cambio;
- tratamento de ausencias, revisoes e valores duplicados.

A implementacao e os testes dessas regras estao no
[artefato versionado de calibracao](CALIBRATION_ARTIFACT.md). O coletor continua
responsavel somente pelos dados brutos e seu manifesto.
