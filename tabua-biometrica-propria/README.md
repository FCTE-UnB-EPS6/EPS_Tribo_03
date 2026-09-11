# Passo 5 — Tábua biométrica própria

Dupla responsável: Maria Clara Oleari de Araujo e Guilherme Coelho Mendonça
Bloco do escopo: Experiência biométrica e tábua própria (§6)

Consome as tabelas finais (pós-limpeza) produzidas pelo Passo 1 —
`participante` e `exposicao` — para construir a tábua biométrica própria da
Tribo 3. Não faz nenhuma limpeza adicional: isso já é responsabilidade do
pipeline de qualidade em `ambiente-de-dados/scripts/pipeline_qualidade.py`,
que só promove pra essas tabelas o que passou pelas regras R01–R09.

Fluxo completo (§6): dados sintéticos → exposição ao risco → eventos
observados → **taxas brutas** → comparação A/E → **suavização** →
credibility → comparação com tábua externa → validação → tábua própria.

Este diretório cobre o fluxo inteiro do §3. A comparação A/E **não estava
de fato bloqueada pelo Passo 3** — isso era uma confusão entre duas coisas
diferentes: esperar a outra dupla popular `referencia_externa` no banco
(esse sim é trabalho deles) vs. usar os arquivos brutos do IBGE, que já
estão baixados e versionados em `ambiente-de-dados/docs/referencias/`
desde que o Passo 3 rodou — e esses dá pra ler direto, sem tocar em nada
do banco da outra dupla.

1. **Taxas brutas de qx** (`scripts/taxas_brutas_qx.py`) — agrega `exposicao`
   por idade e submassa, cruza com óbitos observados.
2. **Coortes como artefato próprio** (`scripts/coortes.py`) — exigência
   explícita do §4.2: a contagem de eventos por submassa/ano precisa
   sobreviver como artefato versionado, não só como cálculo de passagem
   dentro do script do qx.
3. **Comparação A/E** (`scripts/comparacao_ae.py`) — óbitos observados
   (taxas brutas, por sexo — a Tábua do IBGE não conhece "submassa") vs.
   esperado sob a Tábua Completa de Mortalidade 2024 do IBGE, lida
   diretamente dos arquivos em `ambiente-de-dados/docs/referencias/`.
4. **Suavização** (`scripts/suavizacao.py`) — baseline por média móvel
   ponderada por exposição, por submassa. Reaproveita
   `taxas_brutas_qx.calcular_taxas_brutas()` em vez de ler o CSV, pra sempre
   rodar contra o estado atual do banco.
5. **Teste de aderência** (`scripts/teste_aderencia.py`) — qui-quadrado
   comparando óbitos observados vs. esperados (`qx_suavizado *
   exposicao_central`) por célula, com pooling de células com esperado < 1
   dentro de cada submassa. Valida se a suavização do item anterior ainda
   se sustenta — exigência do §3/§8 (DoD).
6. **Credibility** (`scripts/credibility.py`) — baseline **interno**: blend
   entre o qx suavizado da submassa e o qx suavizado da massa inteira
   (todas as submassas somadas), pela regra da raiz quadrada. Não usa o
   IBGE — confirmado pela ordem do §3 e pelo §4.3 do escopo (credibility e
   "comparação com tábua externa" são etapas/entregáveis separados) e pela
   teoria atuarial padrão (Bühlmann/limited fluctuation); ver
   `scripts/credibility.py` e `docs/model_card.md`.
7. **Intervalos de confiança** (`scripts/intervalos_confianca.py`) — IC de
   Poisson exato (Garwood) por célula, sobre o qx bruto.
8. **Validação temporal** (`scripts/validacao_temporal.py`) — holdout do
   ano_calendario mais recente: ajusta o qx suavizado só com os anos
   anteriores e testa (qui-quadrado) se ele explica o observado no ano de
   fora.
9. **Tábua própria — consolidação final** (`scripts/tabua_propria.py`) —
   junta bruto, suavizado, credibilizado e IC numa saída única por (idade,
   submassa), com `qx_credibilizado` como o qx oficial adotado. Antes de
   gravar, roda dois portões de qualidade reaproveitando os módulos
   anteriores: o teste de aderência geral e a razão A/E geral (Ambos)
   dentro de uma faixa de sanidade frouxa (0.5x-2x). Se algum portão não
   passar, a tábua é gravada mesmo assim (pra não travar o Passo 6), mas o
   relatório marca "REVISAR ANTES DE OFICIALIZAR" em vez de "PRONTA".

Documentação em `docs/data_card.md`, `docs/model_card.md` e
`docs/experiment_record.md` (os três exigidos separadamente pelo escopo).

**O que falta**: só rodar tudo contra dados reais — ainda sem Postgres
disponível nesta máquina. Todas as 9 etapas do fluxo já estão
implementadas e testadas (com dados sintéticos em memória e, no caso do
IBGE, com os arquivos reais) — falta a execução real contra o banco pra
saber se os dois portões de qualidade realmente passam com os dados de
verdade.

## Como rodar

Usa o mesmo Postgres do Passo 1 (`ambiente-de-dados/docker-compose.yml`).

```bash
# a partir de ambiente-de-dados/, com o .env configurado:
docker compose up -d

# a partir desta pasta:
pip install -r scripts/requirements.txt
python scripts/pipeline.py
```

`pipeline.py` roda as 9 etapas em sequência (a mesma ordem listada acima) e
para no primeiro erro — não faz sentido rodar a suavização se as taxas
brutas falharam. Cada script continua funcionando isolado também (é assim
que todos foram testados), se precisar rodar só uma etapa de novo:

```bash
python scripts/taxas_brutas_qx.py
python scripts/coortes.py
python scripts/comparacao_ae.py
python scripts/suavizacao.py
python scripts/teste_aderencia.py
python scripts/credibility.py
python scripts/intervalos_confianca.py
python scripts/validacao_temporal.py
python scripts/tabua_propria.py
```

As mesmas variáveis de ambiente do Passo 1 valem aqui (`PGHOST`, `PGPORT`,
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — ver
`ambiente-de-dados/.env.example`). Sem `.env` carregado, os scripts caem nos
mesmos defaults de `ambiente-de-dados/scripts/db.py` (`localhost:5433`).

## Saídas

- `docs/qx_bruto/qx_bruto_<data>.csv` — uma linha por (idade, submassa):
  óbitos, exposição central (soma de `tempo_exposto`) e qx bruto.
- `docs/coortes/coortes_<data>.csv` — uma linha por (ano_calendario,
  submassa): participantes distintos, linhas de exposição, óbitos,
  censuras, saídas por estudo e exposição total. É o artefato de coorte
  exigido pelo §4.2, independente do qx.
- `docs/comparacao_ae/comparacao_ae_<data>.csv` e `.md` — óbitos
  observados vs. esperados sob a Tábua do IBGE 2024, por idade e por
  categoria (M, F, Ambos), com razão A/E geral por categoria.
- `docs/qx_suavizado/qx_suavizado_<data>.csv` — qx_bruto e qx_suavizado
  lado a lado por (idade, submassa).
- `docs/teste_aderencia/teste_aderencia_<data>.md` — estatística
  qui-quadrado, graus de liberdade e p-valor por submassa e geral, com
  veredito de aderência (alpha = 0.05).
- `docs/qx_credibilizado/qx_credibilizado_<data>.csv` — qx suavizado da
  submassa, qx geral interno, peso Z de credibility e qx credibilizado
  final, por (idade, submassa).
- `docs/intervalos_confianca/ic_qx_<data>.csv` — qx bruto com limite
  inferior e superior do IC de 95% (Poisson exato), por (idade, submassa).
- `docs/validacao_temporal/validacao_temporal_<data>.md` — mesmo formato
  do teste de aderência, mas comparando o qx do treino (anos mais antigos)
  contra o observado no ano de holdout.
- `docs/tabua_propria/tabua_propria_<data>.csv` — **a saída final**: bruto,
  suavizado, credibilizado e IC lado a lado por (idade, submassa). É o
  arquivo que o Passo 6 deve consumir.
- `docs/tabua_propria/tabua_propria_<data>.md` — veredito dos dois portões
  de qualidade (aderência e A/E) e se a tábua está pronta pra oficializar
  ou precisa de revisão.

Cada rodada gera um arquivo novo com a data no nome — não sobrescreve o
anterior, pra manter histórico versionado no git.

## Por que agregar por idade inteira, não por `idade_exata`

`exposicao.idade_exata` é `DECIMAL(6,3)` (idade contínua, calculada como
`(data_base - data_nascimento) / 365.25` — ver
`ambiente-de-dados/docs/regras_geracao.md`). Numa massa de 300
participantes, agregar pelo valor contínuo deixaria quase toda célula com
uma exposição só. Os dois scripts aqui arredondam para baixo
(`FLOOR(idade_exata)`), virando idade inteira — ainda granular o bastante
pra suavizar depois, mas com células que já acumulam mais de uma
observação.

## Limitação herdada do gerador (não é bug daqui)

O gerador só cria participantes a partir da maioridade (`data_ingresso` >=
18 anos), então não existe exposição nem óbito sintético abaixo dos 18 e a
amostra fica pequena acima dos 70 — o mesmo padrão que já aparece nos
benchmarks do Passo 3 contra IBGE/HMD/BR-EMS/SOA
(`ambiente-de-dados/DATASET_CARD.md`). Vale citar isso no data card/model
card da tábua própria como limitação herdada, não como algo a corrigir
aqui.
