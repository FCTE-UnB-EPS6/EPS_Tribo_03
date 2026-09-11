# Data Card — Tábua Biométrica Própria (Passo 5)

## Propósito

Tábua de mortalidade (qx) própria da massa sintética da Tribo 3, construída
a partir da experiência observada em `exposicao`/`participante` — não é
uma tábua de mercado, é a experiência da própria massa, suavizada e
credibilizada.

## População

- Fonte: tabelas finais `participante` e `exposicao` (pós-pipeline de
  qualidade do Passo 1 — só dado promovido, ver
  `ambiente-de-dados/scripts/pipeline_qualidade.py`).
- Recorte: 3 submassas (Plano A, Plano B, Plano C), idades a partir da
  maioridade (o gerador não cria participante menor de 18 anos — ver
  `ambiente-de-dados/docs/regras_geracao.md`).
- Volume: depende do `N_PARTICIPANTES` da rodada do Passo 1 (padrão: 300).
  Célula (idade x submassa) tende a ter pouca exposição nesse volume —
  daí a suavização e o credibility interno serem necessários mesmo antes
  de qualquer comparação externa.

## Dados de entrada, por etapa

| Etapa | Script | Entrada | Saída |
| --- | --- | --- | --- |
| Taxas brutas | `taxas_brutas_qx.py` | `exposicao` | `docs/qx_bruto/*.csv` |
| Coortes (§4.2) | `coortes.py` | `exposicao` | `docs/coortes/*.csv` |
| Suavização | `suavizacao.py` | saída de taxas brutas | `docs/qx_suavizado/*.csv` |
| Comparação A/E | `comparacao_ae.py` | taxas brutas por sexo + arquivos IBGE (`ambiente-de-dados/docs/referencias/`) | `docs/comparacao_ae/*.csv` e `*.md` |
| Teste de aderência | `teste_aderencia.py` | saída da suavização | `docs/teste_aderencia/*.md` |
| Credibility | `credibility.py` | saída da suavização | `docs/qx_credibilizado/*.csv` |
| Intervalos de confiança | `intervalos_confianca.py` | taxas brutas | `docs/intervalos_confianca/*.csv` |
| Validação temporal | `validacao_temporal.py` | `exposicao` por `ano_calendario` | `docs/validacao_temporal/*.md` |
| Tábua própria (final) | `tabua_propria.py` | saída de credibility.py + intervalos_confianca.py; portões de aderência e A/E | `docs/tabua_propria/*.csv` e `*.md` |

## Versão

- **v0.3** (atual): as 9 etapas do fluxo do §3 implementadas —
  taxas brutas, coortes, comparação A/E (contra o IBGE, lido direto do
  arquivo), suavização, teste de aderência, credibility interno,
  intervalos de confiança, validação temporal e a consolidação final
  (`tabua_propria.py`, com portões de qualidade). Falta só rodar contra
  dados reais — ver "Status" abaixo.

## Status — o que falta

- ✅ **Comparação A/E**: implementada em `comparacao_ae.py`, lendo os
  arquivos brutos do IBGE (`ambiente-de-dados/docs/referencias/`)
  diretamente, sem depender de `referencia_externa` estar populada no
  banco. Não é mais bloqueada pelo Passo 3 — essa era uma confusão entre
  "esperar a outra dupla" e "usar o arquivo que ela já baixou e
  versionou", que são coisas diferentes.
- ✅ **Credibility**: implementado como "interno" (blend com o qx geral da
  massa inteira). Confirmado que essa é a leitura correta do escopo — a
  ordem do §3 (credibility e "comparação com tábua externa" como etapas
  separadas) e o §4.3 (mesma separação na lista de entregáveis) só fazem
  sentido se o credibility não usa o IBGE; bate também com a teoria
  atuarial padrão (Bühlmann/limited fluctuation usam "collateral data"
  interno, não tábua de mercado). Não precisa revisitar depois do A/E —
  ver `scripts/credibility.py`.
- ✅ **Consolidação final**: `tabua_propria.py` junta bruto, suavizado,
  credibilizado e IC numa saída única, com `qx_credibilizado` como o qx
  oficial, condicionado a dois portões de qualidade (aderência e A/E).
- ⏳ **Único item pendente**: rodar `scripts/pipeline.py` (as 9 etapas em
  sequência, num só comando) contra dados reais — falta Postgres
  disponível na máquina de desenvolvimento. Toda a lógica já foi validada
  com dados sintéticos em memória e, no caso do IBGE, com os arquivos
  reais — falta só a confirmação empírica final de que os portões passam
  e a `JANELA`/`EXPOSICAO_PLENA`/`LIMIAR_ESPERADO` não
  precisam de ajuste.

## Limitações herdadas do gerador (não são bugs deste passo)

- Sem exposição/óbito sintético abaixo dos 18 anos (gerador só cria
  participante a partir da maioridade).
- Amostra pequena acima dos 70 anos.
- Mesmo padrão de desvio já documentado nos benchmarks do Passo 3 contra
  IBGE/HMD/BR-EMS/SOA (`ambiente-de-dados/DATASET_CARD.md`).
