# Model Card — Tábua Biométrica Própria

## Propósito

Estimar qx (probabilidade de morte na idade x) por submassa a partir da
experiência observada, como insumo para o Passo 6 (tábuas geracionais) e
para gestão de risco coletivo da Tribo 3 — **não** é uma ferramenta de
decisão automática sobre direitos de nenhum participante individual (mesma
restrição de uso registrada no model card do Passo 2, que se aplica aqui
por analogia: é insumo analítico agregado, não decisão individual).

## Método, por etapa

| Etapa | Método | Por quê |
| --- | --- | --- |
| Taxas brutas | óbitos / exposição central (soma de `tempo_exposto`) | exposição em anos-pessoa, não contagem de linhas — mais correto que a aproximação do benchmark preliminar do Passo 3 |
| Comparação A/E | observado (taxas brutas, por sexo) / esperado (qx do IBGE 2024 x exposição), lido direto dos arquivos em `ambiente-de-dados/docs/referencias/` | segue a ordem do §3 (A/E vem logo após as taxas brutas, antes da suavização); usa taxas brutas, não a curva suavizada, por estar antes dela no fluxo |
| Suavização | média móvel ponderada por exposição, janela ±2 idades | baseline simples antes de complexidade (mesmo princípio usado nos Passos 2/4/6); evoluir para Whittaker-Henderson só se o teste de aderência não se sustentar |
| Teste de aderência | qui-quadrado (observado x esperado), com pooling de células com esperado < 1 óbito por submassa | KS/Anderson-Darling comparam distribuições contínuas; aqui o dado já é discretizado em células de exposição — qui-quadrado é o padrão atuarial |
| Credibility | raiz quadrada: Z = min(1, sqrt(exposição / 10 anos)), blend com o qx geral da massa (todas as submassas somadas) na mesma idade | baseline **interno**, confirmado pela ordem do §3 (credibility e comparação com tábua externa são etapas separadas) e pela teoria atuarial padrão (Bühlmann/limited fluctuation usam "collateral data" interno) — ver `scripts/credibility.py` |
| Intervalos de confiança | Poisson exato (Garwood, 1936), IC de 95% | exposição contínua (anos-pessoa), não contagem discreta de indivíduos — Poisson é o modelo padrão aqui |
| Validação temporal | holdout do ano_calendario mais recente; qx ajustado só com os anos anteriores é testado (qui-quadrado) contra o observado no ano de fora | usa o campo `ano_calendario` que já existe em `exposicao`, sem precisar de infraestrutura nova |
| Consolidação final | `qx_credibilizado` adotado como qx oficial, condicionado a dois portões: aderência geral (qui-quadrado) e A/E geral (Ambos) dentro de 0.5x-2x | reaproveita os módulos anteriores em vez de recalcular; se um portão falhar, grava mesmo assim mas marca "revisar" em vez de "pronta" — não trava o Passo 6 esperando um ajuste fino |

## Métricas

As métricas de cada rodada (estatística qui-quadrado, graus de liberdade,
p-valor por submassa) não são fixas aqui — variam a cada execução, porque
dependem do estado atual do banco (seed, volume, imperfeições injetadas).
Ver `docs/teste_aderencia/*.md` e `docs/validacao_temporal/*.md` para os
resultados de cada rodada, e `experiment_record.md` para o registro
consolidado de parâmetros x resultado por execução.

## Limitações

- **Amostra pequena**: com o volume padrão (300 participantes), a maioria
  das células (idade x submassa) tem menos de 1 óbito esperado — daí o
  pooling no teste de aderência e o credibility puxando forte pro baseline
  geral em idades com pouca exposição.
- **Comparação A/E só contra o IBGE por enquanto**: `comparacao_ae.py`
  compara contra a Tábua Completa de Mortalidade do IBGE, não contra
  HMD/BR-EMS/SOA (os outros 3 arquivos também já estão versionados em
  `ambiente-de-dados/docs/referencias/`, mas ainda não foram usados aqui —
  extensão natural, mesmo raciocínio de leitura direta de arquivo).
- **A/E instável célula a célula**: com a amostra pequena, a razão A/E por
  idade individual é ruidosa; a leitura confiável é a razão agregada
  (soma dos óbitos / soma do esperado) por categoria (M, F, Ambos), não
  célula a célula — ver `docs/comparacao_ae/*.md`.
- **Limitações herdadas do gerador**: sem exposição/óbito sintético abaixo
  de 18 anos, amostra pequena acima de 70 — ver `data_card.md`.

## Origem dos dados

Massa sintética do Passo 1 (`ambiente-de-dados/`), tabelas `participante` e
`exposicao` pós-pipeline de qualidade. Nenhum dado real de participante,
CPF ou fundo de previdência — ver `ambiente-de-dados/DATASET_CARD.md`.
