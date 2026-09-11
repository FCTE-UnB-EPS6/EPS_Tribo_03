# TRIBO 3 — DADOS, ESTATÍSTICA E IA

## Roteiro de Próximos Passos

Oito passos, ordenados por desbloqueio: o que depende de menos coisas (ou já está com a base pronta) vem primeiro, mesmo que seja de uma dupla diferente. O Passo 2, por exemplo, só depende do núcleo do Passo 1 — que já está pronto — então avança na frente do Benchmark e dos Cenários econômicos, que são da mesma dupla do Passo 1 ou têm menos urgência.

### Mapa de dependências e trilhas paralelas

Verde: pode começar agora, em paralelo. Âmbar: entra na fila só depois que a dependência indicada estiver pronta.

---

## PASSO 1 — Data quality e massa sintética

**Dupla responsável:** Júlia Takaki Neves e Jefferson Sena Oliveira  
**Bloco do escopo:** Data quality e massa sintética (§6)

### Depende de outros passos

✅ Nenhuma dependência — é o passo fundacional, todos os demais dependem dele.

### O que já foi feito

Construção da infraestrutura de dados sintéticos e do pipeline de qualidade que serve de base para todas as demais duplas da Tribo 3.

- ✅ Schema bitemporal em Postgres com as 7 entidades do desenho de referência (participante, evento, exposicao, contribuicao_beneficio, referencia_externa, dicionario_dados, data_quality_score), mais o schema gabarito.registro_erro_injetado.
- ✅ Gerador de massa sintética reprodutível (seed fixa, UUIDs derivados do rng, Faker) — mesma seed produz sempre o mesmo dataset.
- ✅ Camada staging (colunas TEXT) para viabilizar a injeção de imperfeições em campos que, nas tabelas finais, são tipados e obrigatórios.
- ✅ 9 regras automatizadas de qualidade (R01–R09), cobrindo as 7 dimensões do escopo: completude, validade, consistência, unicidade, acurácia, temporalidade e materialidade — acima do mínimo de 5 exigido.
- ✅ Dicionário de dados com 69 campos documentados (nome, tipo, unidade, domínio, obrigatoriedade, origem, responsável, versão) — hoje só como tabela no banco.
- ✅ Pipeline que promove linhas aprovadas para as tabelas finais e mede precision/recall da limpeza contra o gabarito de erros injetados.
- ✅ Relatório de qualidade versionado, gerado automaticamente a partir do estado do banco.

### O que ficou pendente

- ⚠️ Gerar o dicionário de dados como documento PDF formal — hoje só existe como tabela no banco. Exportar (SELECT * ORDER BY tabela, nome_campo), formatar com capa, versão e data de emissão, e organizar por entidade. É o artefato mínimo de interface exigido pelo escopo.
- ⚠️ dicionario_dados.responsavel está genérico ("Tribo 3") nos 69 campos — atribuir o nome da dupla responsável por cada tabela antes de fechar o PDF.
- ⚠️ O mapeamento do erro unidade_trocada aponta para a dimensão materialidade, mas o desenho de referência pede consistência — ajustar o mapeamento ou registrar em comentário por que a decisão foi diferente (como já foi feito para o erro orfao).
- ⚠️ Conferir se o DATASET_CARD.md já declara as distribuições, dependências, eventos raros e inconsistências intencionais do gerador — é uma exigência explícita da governança de dados sintéticos.
- ⚠️ Registrar formalmente o tratamento LGPD (minimização e anonimização) do dataset antes da entrega — exigência explícita do Definition of Done (§8), mesmo sendo dado sintético.

---

## PASSO 2 — Modelo individual de sobrevivência

**Dupla responsável:** Caio Brandão Santos e Pedro Lucas Figueiredo Santana  
**Bloco do escopo:** Multiestado e survival analytics (§6)

### Depende de outros passos

✅ Depende só do Passo 1 (participante, evento e exposicao estáveis) — como o núcleo do Passo 1 já está pronto (só faltam as pendências administrativas), esta dupla pode começar agora, em paralelo a todos os outros passos.

### O que fazer

Construir e validar um modelo individual de sobrevivência a partir da massa sintética disponível, começando por um baseline interpretável e comparando posteriormente com um modelo challenger mais complexo.

- Definir o problema de sobrevivência do MVP: população analisada, evento de interesse, período de observação e regras de censura.
- Construir e versionar o dataset analítico de survival a partir de participante, evento e exposição, contendo tempo observado, ocorrência do evento, censura e covariáveis utilizadas pelo modelo. Essas entidades já estão previstas no desenho do banco de referência.
- Construir um baseline interpretável com Kaplan-Meier e/ou Cox, utilizando covariáveis disponíveis e justificadas.
- Treinar pelo menos um modelo challenger de sobrevivência, como Survival Forest, para comparação com o baseline.
- Avaliar e comparar os modelos por validação temporal, calibração e discriminação, adotando o modelo mais complexo apenas se houver ganho mensurável frente ao baseline.
- Registrar os experimentos de forma reproduzível, incluindo versão dos dados, covariáveis, métodos, parâmetros, métricas e resultados.
- Documentar o contrato de saída do modelo, incluindo estimativas, versão, métricas, incerteza e limitações.

---

## PASSO 3 — Benchmark externo (IBGE e demais fontes)

**Dupla responsável:** Júlia Takaki Neves e Jefferson Sena Oliveira  
**Bloco do escopo:** Data quality e massa sintética (§6) — qualidade e curadoria de dados

### Depende de outros passos

✅ Nenhuma dependência formal — mas é a mesma dupla do Passo 1, então na prática entra depois que as pendências administrativas de lá forem fechadas.

### O que fazer

Popular a referencia_externa, hoje com os registros criados mas versao_tabua, data_consulta e resultado_benchmark todos nulos. Sem isso, o Passo 5 não consegue calcular A/E.

- Baixar a Tábua Completa de Mortalidade mais recente do IBGE (fonte pública, sem necessidade de convênio).
- Versionar a tábua bruta baixada no repositório (ex.: pasta docs/referencias/), preservando o arquivo original para rastreabilidade.
- Atualizar a linha fonte = 'IBGE' com versao_tabua (ano/edição) e data_consulta (data do download).
- Rodar uma comparação preliminar de plausibilidade (ordem de grandeza do qx sintético vs. IBGE por faixa etária) e registrar o resumo em resultado_benchmark.
- Repetir depois para HMD, BR-EMS e SOA, nessa ordem de prioridade — IBGE primeiro por ser o mais simples de obter e o baseline demográfico mais direto.

---

## PASSO 4 — Cenários econômicos (Economic Scenario Generator)

**Dupla responsável:** Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira  
**Bloco do escopo:** Economic Scenario Generator (§6)

### Depende de outros passos

✅ Nenhuma dependência para começar — dupla livre, pode rodar em paralelo aos Passos 2 e 3. Só precisa alinhar parâmetros com os Passos 5 e 6 antes de finalizar, para não duplicar premissas divergentes.

### O que fazer

Bloco relativamente independente dos demais — pode começar assim que houver clareza sobre quais variáveis econômicas o projeto vai precisar (taxa de juros, inflação, etc. aplicáveis ao CD/CV).

- Começar por cenários determinísticos parametrizáveis — nada de Monte Carlo ainda, seguindo o princípio de baseline antes de complexidade.
- Definir as premissas econômicas de forma versionada e documentada, do mesmo jeito que o dataset sintético.
- Monte Carlo, correlações entre fatores e stress testing entram só como evolução condicionada, depois que os cenários determinísticos estiverem validados e houver necessidade demonstrada.
- Alinhar com o Passo 5 (tábua própria) e o Passo 6 (geracional) quais parâmetros econômicos essas tábuas vão consumir, para não duplicar premissas divergentes.

---

## PASSO 5 — Tábua biométrica própria

**Dupla responsável:** Maria Clara Oleari de Araujo e Guilherme Coelho Mendonça  
**Bloco do escopo:** Experiência biométrica e tábua própria (§6)

### Depende de outros passos

⚠️ Depende do Passo 3 só para a etapa de comparação A/E (precisa do qx do IBGE em referencia_externa). As demais etapas — taxas brutas, suavização, credibility interno, IC, validação temporal — não dependem de nada e podem começar agora.

### O que fazer

Seguir o fluxo do escopo oficial: dados sintéticos → exposição ao risco → eventos observados → taxas brutas → comparação A/E → suavização → credibility → comparação com tábua externa → validação → tábua própria.

- Taxas brutas de qx: agregar exposicao por idade exata e submassa, calcular mortes observadas sobre exposição — pode começar sem esperar o Passo 3.
- Construir e versionar as coortes e a contagem de eventos por submassa como artefato próprio, não só como insumo intermediário do qx — exigência explícita do §4.2 do escopo.
- Comparação A/E: comparar o qx bruto sintético contra o qx do IBGE registrado pelo Passo 3 — depende dele estar concluído.
- Suavização: método baseline simples primeiro (ex.: Whittaker-Henderson ou média móvel), só evoluindo se houver ganho demonstrável.
- Teste de aderência (KS, Anderson-Darling ou Qui-quadrado) para validar se a curva suavizada do qx se ajusta plausivelmente aos dados observados — exigência do §3/§8 (DoD).
- Credibility: blend entre taxa observada e baseline externo para submassas com exposição baixa.
- Intervalos de confiança: bootstrap ou IC binomial/Poisson por célula de qx.
- Validação temporal: holdout por ano_calendario (campo já existe em exposicao).
- Data card, model card e experiment record da tábua: propósito, população, dados, método, versão, métricas, limitações — os três documentos são exigidos separadamente pelo escopo.

---

## PASSO 6 — Tábuas geracionais e mortality improvement

**Dupla responsável:** Danielle Soares da Silva e Maria Eduarda Quaresma de Andrade  
**Bloco do escopo:** Tábuas geracionais e improvement (§6)

### Depende de outros passos

⚠️ Depende do Passo 5 estar concluído — usa a tábua própria (qx suavizado e validado) como base para projetar qx,t.

### O que fazer

Depende da tábua própria do Passo 5 estar pronta como base de qx. Evoluir de uma taxa estática para a projeção ao longo do tempo (qx,t).

- Método baseline para evolução de qx → qx,t primeiro (ex.: extrapolação simples de tendência usando os anos já disponíveis em exposicao.ano_calendario).
- Teste de tendência (Mann-Kendall) para confirmar direção estatisticamente significativa do mortality improvement ao longo dos anos — exigência do §3/§8 (DoD).
- Teste de estacionariedade (ADF/KPSS) na série temporal de qx antes de ajustar o modelo geracional.
- Comparar depois com Lee-Carter, CBD e/ou P-splines, avançando só se o backtest mostrar ganho real sobre o baseline.
- Backtesting temporal, usando os anos mais recentes como holdout.
- Documentar em data card, model card e experiment record específicos da tábua geracional, incluindo o horizonte de projeção escolhido.

---

## PASSO 7 — Explicabilidade (SHAP/ALE) e model risk

**Dupla responsável:** Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega  
**Bloco do escopo:** Ensemble e diagnóstico probabilístico (§6) — etapa 5 do fluxo técnico do MVP

### Depende de outros passos

⚠️ Depende dos Passos 2, 5 e 6 já existirem (modelo individual, tábua própria, tábua geracional) — o trabalho aqui é explicar esses modelos, não construir um novo.

### O que fazer

- Gerar explicações SHAP/ALE para os modelos não triviais (ex.: o modelo individual de sobrevivência do Passo 2) — a Tribo 1 precisa disso sem jargão técnico para dashboards.
- Montar o model card e o experiment record de cada modelo entregue até aqui: propósito, população, dados, método, versão, métricas, limitações e origem dos dados.
- Relatório de limitações e vieses por subgrupo, quando pertinente — exigência do Definition of Done.
- Reportar à Tribo 4 as ameaças de inferência/reidentificação e superfícies de risco dos modelos, conforme a matriz de integração do escopo.

---

## PASSO 8 — Ensemble, calibração e diagnóstico probabilístico

**Dupla responsável:** Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega  
**Bloco do escopo:** Ensemble e diagnóstico probabilístico (§6)

### Depende de outros passos

⚠️ Depende do Passo 7 estar concluído — usa os mesmos modelos já explicados para comparar e decidir promoção champion-challenger.

### O que fazer

Sequência natural do Passo 7, usando os mesmos modelos já explicados: agora o objetivo é comparar e decidir promoção champion-challenger.

- Calibração e discriminação dos modelos documentadas, comparando sempre contra o baseline simples — o DoD exige que a complexidade extra seja justificada, não assumida.
- Construir modelos challenger e comparar via ensemble, registrando se algum supera o baseline com ganho mensurável.
- Registrar o experiment record de cada rodada de comparação champion-challenger (dados, parâmetros, métricas, versão) — rastreabilidade exigida pelo escopo.
- Quantificação de incerteza por CVaR/distribuição de simulação onde fizer sentido, complementando os IC já calculados nos Passos 5 e 6.
- Registrar as métricas de promoção champion-challenger num formato consumível pela observabilidade da Tribo 5.
