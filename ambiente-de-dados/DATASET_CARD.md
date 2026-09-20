# Data Card — Massa Sintética Tribo 3

## Propósito

Massa de dados previdenciária de **estrutura sintética e parâmetros
calibrados com fonte pública real**, criada para testar um pipeline de
qualidade de dados (curadoria, detecção de imperfeições, scoring) antes
de aplicá-lo a dados reais. Nenhum participante, CPF ou valor corresponde
a pessoa ou entidade real — todos são gerados por algoritmo.

## Estrutura sintética, parâmetros reais

Esta distinção é o que define o dataset, e vale a pena ser explícito
sobre ela em vez de dizer só "é sintético".

**Por que a estrutura continua sintética**, e não vai deixar de ser:

1. **Não existe base pública de participante de fundo de previdência no
   Brasil.** O que é público é agregado (PREVIC Painel-Cidadão) ou
   populacional (IBGE, SIM), nunca a trajetória individual de entrada,
   contribuição e saída que este dataset precisa.
2. **O propósito exige gabarito conhecido.** O pipeline de qualidade é
   medido por precision/recall contra
   `gabarito.registro_erro_injetado`. Isso só funciona se soubermos
   exatamente quais registros foram corrompidos de propósito — o que é
   impossível numa base real, onde não se sabe qual valor é o certo.
3. **LGPD.** Dado individual de participante é dado pessoal sensível;
   uma massa sintética elimina a questão na origem, e não só a mitiga.

**O que passou a ser real:** a mortalidade. A trajetória de cada
participante é simulada ano a ano, e a probabilidade de morte em cada ano
vem do **qx por idade e sexo da Tábua Completa de Mortalidade do IBGE
2024**, com um fator de seleção declarado de 0,85×. Antes, `status_atual`
era um sorteio único com peso global fixo (`obito = 5%`), idêntico para
um participante de 25 e um de 85 anos.

**O que continua sendo premissa, não dado:** as taxas de desligamento,
aposentadoria e invalidez. São ordem de grandeza plausível, declaradas em
`docs/regras_geracao.md`, e não devem ser citadas como calibradas.

**Atenção de quem for validar** (Passo 5): a massa foi calibrada com o
IBGE, então comparar o A/E dela contra o IBGE é circular — mede se a
simulação reproduziu seu próprio insumo, não se ela é realista. A
referência de validação independente é a **BR-EMS** (mesmo universo
demográfico brasileiro). A SOA RP-2014 resolve a circularidade mas é
mortalidade de planos americanos: serve como referência internacional
complementar, não como substituto.

## Escopo

- **Cobre**: participantes, eventos de carreira/saída, exposição ao
  risco (base para cálculo atuarial de mortalidade) e contribuições/
  benefícios, de um plano de previdência complementar fictício com 3
  submassas (Plano A, Plano B, Plano C) e 3 tipos de plano (BD, CD, CV).
- **Não cobre**: dados de nenhuma entidade real, nenhum CPF real (o
  campo `cpf_sintetico` nunca corresponde a documento real), nenhum
  valor monetário com relação a moeda real além da unidade (BRL nominal).
- **Uso pretendido**: exercitar e validar as regras de qualidade e o
  cálculo do Data Quality Score. A mortalidade calibrada torna a massa
  utilizável como insumo de teste metodológico para os Passos 2, 5 e 6 —
  mas ela continua sendo uma simulação, e nenhum resultado obtido sobre
  ela é premissa atuarial de um plano real.

## Processo de geração

1. `gerar_dataset.py` gera participantes, eventos, exposição e
   contribuições em memória, com seed fixa, e escreve tudo no schema
   `staging` (colunas `TEXT`, sem validação de tipo ainda). Cada
   participante é simulado **ano a ano** desde o ingresso, sorteando
   morte/sobrevivência com o qx real da idade daquele ano
   (`scripts/calibracao.py`); `status_atual` e as linhas de `exposicao`
   são resultado dessa simulação, não sorteios independentes.
2. Nesse mesmo passo, injeta imperfeições propositais em uma fração dos
   registros (9 tipos, um por dimensão de qualidade — ver
   `docs/regras_geracao.md`), registrando cada uma em
   `gabarito.registro_erro_injetado` com valor original e valor
   injetado.
3. `pipeline_qualidade.py` lê o staging, aplica as 9 regras automatizadas
   (`scripts/regras.py`), grava o Data Quality Score por variável,
   participante, submassa/plano e data-base, promove as linhas aprovadas
   para as tabelas tipadas (`participante`, `evento`, `exposicao`,
   `contribuicao_beneficio`) e marca no gabarito quais imperfeições foram
   detectadas.
4. Todo o processo é reprodutível: a mesma combinação de seed, data de
   referência e tábua de calibração produz o mesmo dataset, IDs
   incluídos (UUIDs derivados do gerador seedado, não do sistema). A
   tábua entra por arquivo versionado em `docs/referencias/`, nunca pela
   rede — nenhuma etapa da geração faz requisição HTTP, então não há como
   uma API devolver valor diferente e mudar o dataset por baixo.

Parâmetros e distribuições usados: ver `docs/regras_geracao.md`.

## Volume e período

- Volume desta rodada: 300 participantes sintéticos (parâmetro
  `N_PARTICIPANTES`, ajustável).
- Período coberto: o ingresso é sorteado nos **30 anos** anteriores à
  data de referência (`DATA_REFERENCIA`, padrão hoje), e cada
  participante é simulado dali até a data de referência. Não representa
  um recorte histórico fixo, mas uma massa "atual" a cada nova geração.
  A janela longa é necessária: o qx de adulto é da ordem de 0,2% ao ano,
  então histórias curtas produziriam quase nenhum óbito e deixariam o
  Passo 5 sem numerador para o A/E.
- O gerador imprime, ao fim de cada lote, a distribuição realizada de
  `status_atual` e o qx bruto agregado, com alerta explícito se o lote
  sair com zero óbitos. Como o status não é mais sorteado, essa é a
  verificação de que a calibração pegou.
- **300 participantes ficaram pequenos para comparação por faixa etária.**
  Com a mortalidade calibrada, os óbitos se concentram nas idades altas
  em vez de se espalharem uniformemente: um lote de 300 produziu 9
  óbitos, que não cobrem as 7 faixas dos `benchmark_*.py` — a maioria sai
  com zero óbito e razão 0,0x. Um lote de 3.000 produziu 147 óbitos e
  razões de 1,0x a 2,2x contra a BR-EMS. Os 300 continuam suficientes
  para o propósito principal (exercitar as regras de qualidade); para
  qualquer leitura atuarial da massa, subir `N_PARTICIPANTES`.

## Limitações conhecidas

- `exposicao` e `contribuicao_beneficio` usam lógica simplificada (uma
  linha por ano civil / até 6 meses de competência), não cobrem todas as
  transições possíveis de status no meio do ano.
- Campo `responsavel` no dicionário de dados está com valor genérico
  ("Tribo 3") — pendente de atribuição por pessoa/dupla.
- O relatório de qualidade com precision/recall completo é impresso no
  console pelo `pipeline_qualidade.py`; a versão persistida em arquivo
  (`docs/relatorios/`) cobre recall e tratamento de exceções, mas não
  recalcula falsos positivos sem rodar o pipeline de novo.
- Apenas um snapshot por participante nesta rodada (`versao_registro =
  1`) — retificação bitemporal (corrigir um snapshot antigo mantendo
  histórico) ainda não é exercitada pelo gerador.
- **Os resultados de benchmark gravados em `referencia_externa` são
  anteriores à calibração e estão desatualizados.** Eles mediam a massa
  gerada pelo sorteio único com peso global (`obito = 5%` para qualquer
  idade), e os desvios que registravam — até ~49x contra o HMD e ~36x
  contra a BR-EMS na faixa de mulheres 20-29 — eram efeito desse
  mecanismo, não só de amostra pequena como se supunha na análise
  original. Os quatro `benchmark_*.py` precisam ser rodados de novo
  sobre a massa calibrada.
- A faixa 0-19 é uma fatia fina, não uma faixa de verdade, e isso não é
  erro: o gerador só cria participantes a partir dos 18 anos de idade de
  ingresso, então a única exposição nessa faixa vem do intervalo 18-19.
  Num lote de 3.000 participantes isso deu ~89 anos-pessoa para homens,
  contra ~14.900 na faixa 30+. Com esse denominador, **um único óbito**
  leva a razão contra a referência a ~28x. O número é instável por
  construção e não deve ser lido como desvio de calibração.
- A faixa 70+ fica sistematicamente abaixo da referência por um motivo
  de construção do benchmark, não de geração: o qx da faixa é a média
  simples das idades 70 a 130 na tábua, dominada por idades muito
  avançadas, enquanto a massa simulada raramente passa dos 85. Comparar
  médias de faixas largas contra uma população com outra distribuição
  etária interna produz esse viés. Só o A/E por idade do Passo 5
  resolve isso.
- A comparação contra o **IBGE** deixou de ser validação e virou
  diagnóstico: é a fonte de calibração (ver "Estrutura sintética,
  parâmetros reais").

## Changelog de versões do schema

- **V1** — schema inicial: 8 entidades (participante, evento, exposicao,
  contribuicao_beneficio, referencia_externa, dicionario_dados,
  data_quality_score, gabarito.registro_erro_injetado).
- **V2** — adiciona o 9º tipo de imperfeição (`datas_fora_ordem`) ao
  enum de tipos de erro.
- **V3** — adiciona `cpf_sintetico` a `participante`; cria o schema
  `staging` (área de entrada + log de rejeição); torna
  `data_quality_score` idempotente (`ON CONFLICT`); relaxa
  `referencia_externa` para aceitar fontes ainda não consultadas.
- **R\_\_dicionario_dados** / **R\_\_referencia_externa** — migrations
  repetíveis, reaplicadas sempre que o conteúdo muda.

O schema **não muda** com a calibração: a simulação ano a ano produz
exatamente as mesmas colunas que o sorteio único produzia, e por isso não
há uma V4.

## Changelog do gerador

- **Calibração com mortalidade real** — `status_atual` deixa de ser um
  sorteio único com pesos fixos (ativo 55%, aposentado 20%, desligado
  15%, óbito 5%, pensionista 5%) e passa a emergir de uma simulação ano a
  ano com qx real por idade/sexo (IBGE 2024, fator de seleção 0,85×).
  Novo módulo `scripts/calibracao.py`. Sem mudança no schema, nos
  injetores, nas 9 regras ou no pipeline de qualidade.

## Passo 3 — Benchmark externo (§6, referencia_externa)

Concluído para as 4 fontes previstas, em ordem de prioridade:

1. **IBGE** — Tábua Completa de Mortalidade 2024, Ambos os Sexos.
2. **HMD** — Austrália 2021 (period life tables 1x1); Brasil não está
   disponível na base, Austrália usada como referência metodológica.
3. **BR-EMS** — BR-EMSsb v.2026 (sobrevivência), vigência 2026-2031.
4. **SOA** — RP-2014 Rates-Total Dataset (mortalidade de ativo, EUA),
   idade 18-80.

Todas as 4 linhas de `referencia_externa` têm `versao_tabua`,
`data_consulta` e `resultado_benchmark` preenchidos. Arquivos brutos
versionados em `docs/referencias/`.
