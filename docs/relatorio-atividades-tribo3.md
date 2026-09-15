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

Construção da infraestrutura de dados sintéticos e do pipeline de qualidade que serve de base para todas as demais duplas da Tribo 3. Conferido item a item contra o código.

- ✅ Schema bitemporal em Postgres com as 7 entidades do desenho de referência (participante, evento, exposicao, contribuicao_beneficio, referencia_externa, dicionario_dados, data_quality_score), mais o schema gabarito.registro_erro_injetado.
- ✅ Gerador de massa sintética reprodutível (seed fixa, UUIDs derivados do rng, Faker) — mesma seed produz sempre o mesmo dataset.
- ✅ Camada staging (colunas TEXT) para viabilizar a injeção de imperfeições em campos que, nas tabelas finais, são tipados e obrigatórios.
- ✅ 9 regras automatizadas de qualidade (R01–R09), cobrindo as 7 dimensões do escopo: completude, validade, consistência, unicidade, acurácia, temporalidade e materialidade — acima do mínimo de 5 exigido.
- ✅ Dicionário de dados com 69 campos documentados (nome, tipo, unidade, domínio, obrigatoriedade, origem, responsável, versão) — hoje só como tabela no banco.
- ✅ Pipeline que promove linhas aprovadas para as tabelas finais e mede precision/recall da limpeza contra o gabarito de erros injetados.
- ✅ Relatório de qualidade versionado, gerado automaticamente a partir do estado do banco.

### O que ficou pendente

- ⚠️ Gerar o dicionário de dados como documento PDF formal — hoje só existe como tabela no banco. Exportar (SELECT * ORDER BY tabela, nome_campo), formatar com capa, versão e data de emissão, e organizar por entidade. É o artefato mínimo de interface exigido pelo escopo.
- ⚠️ dicionario_dados.responsavel está genérico ("Tribo 3") nos 69 campos — confirmado nos 69 registros. Atribuir o nome da dupla responsável por cada tabela antes de fechar o PDF.
- ⚠️ O mapeamento do erro unidade_trocada aponta para a dimensão materialidade, mas o desenho de referência pede consistência — confirmado, sem ajuste nem comentário de justificativa até agora. Ajustar o mapeamento ou registrar em comentário por que a decisão foi diferente (como já foi feito para o erro orfao).
- ⚠️ Registrar formalmente o tratamento LGPD (minimização e anonimização) do dataset antes da entrega — exigência explícita do Definition of Done (§8). Confirmado: não há nenhuma menção a isso em nenhum arquivo do projeto ainda.

---

## PASSO 2 — Modelo individual de sobrevivência

**Dupla responsável:** Caio Brandão Santos e Pedro Lucas Figueiredo Santana  
**Bloco do escopo:** Multiestado e survival analytics (§6)

### Depende de outros passos

✅ Depende só do Passo 1 (participante, evento e exposicao estáveis) — como o núcleo do Passo 1 já está pronto (só faltam as pendências administrativas), esta dupla pode começar agora, em paralelo a todos os outros passos.

### O que já foi feito

Implementação revisada do Passo 2 em `survival-analysis/`; resultados oficiais ainda dependem da execução integrada.

- ✅ Extração das tabelas finais de participante/evento, com exposição agregada para auditoria, uma linha por participante e registro de fonte, hashes e exclusões por inconsistência temporal.
- ✅ Kaplan-Meier e log-rank global por sexo, BD/CD/CV e submassa Plano A/B/C, com contagens por grupo.
- ✅ Cox PH interpretável, correlação diagnóstica, Schoenfeld e métricas de treino identificadas como aparentes.
- ✅ Comparação Cox/RSF no mesmo corte por data de ingresso, limitando os desfechos de treino ao corte; C-index com sinal corrigido, Brier/IBS e calibração direta por KM.
- ✅ Avaliação por subgrupo, motivos explícitos quando falta suporte e critério de comparação que exige discriminação e calibração, com bootstrap pareado.
- ✅ Testes de regressão para datas, evento/censura, corte temporal, direção do risco e decisão conjunta; model card e experiment record corrigidos.
- ✅ Gerador local restrito a desenvolvimento e identificado separadamente; resultados históricos locais preservados como evidência de revisão, sem atribuição à massa oficial.

### O que ficou pendente

- ⚠️ Executar sobre o Postgres do Passo 1 com lote/versão/referência alinhados; inspecionar exclusões e diferenças da exposição, registrar os números oficiais e avaliar se os eventos suportam a conclusão.
- ⚠️ A divisão por calendário usa o cadastro atual extraído; não reconstrói integralmente o conhecimento bitemporal disponível no passado. Essa limitação está documentada.

Riscos competitivos estão fora do escopo desta entrega e não são condição para concluir o Passo 2.

### O que fazer

Não depende da tábua própria nem da tábua geracional — só precisa da base participante/evento/exposicao, que já está de pé.

- Baseline interpretável primeiro: Kaplan-Meier e/ou Cox, usando idade, sexo, plano_tipo e submassa como covariáveis.
- Modelos mais complexos (survival forest, gradient boosting survival, abordagens bayesianas) só entram se houver ganho comprovado de calibração e discriminação frente ao baseline.
- Validação temporal e por subgrupo, com calibração e discriminação documentadas — exigência do Definition of Done.
- Testar correlação/dependência entre covariáveis (Pearson/Spearman e, quando justificado, cópulas) antes de incluir no modelo, para evitar multicolinearidade — exigência do §3/§4.2 do escopo.
- Registrar o experiment record do treinamento (dados usados, hiperparâmetros, métricas, versão), além do model card — os dois documentos são exigidos separadamente pelo escopo (§3/§4.4).
- Deixar registrado no model card que a estimativa individual é insumo analítico para gestão de risco coletivo, nunca decisão automática sobre direitos individuais — restrição explícita do escopo.

---

## PASSO 3 — Benchmark externo (IBGE e demais fontes)

**Dupla responsável:** Júlia Takaki Neves e Jefferson Sena Oliveira  
**Bloco do escopo:** Data quality e massa sintética (§6) — qualidade e curadoria de dados

### Depende de outros passos

✅ Nenhuma dependência formal — mas é a mesma dupla do Passo 1, então na prática entra depois que as pendências administrativas de lá forem fechadas.

### O que já foi feito

Passo mais avançado do que a versão anterior deste roteiro sugeria — conferido direto no código, não só na descrição da tarefa.

- ✅ Scripts de benchmark implementados para as 4 fontes: benchmark_ibge.py, benchmark_hmd.py, benchmark_brems.py e benchmark_soa.py.
- ✅ Arquivos brutos das 4 fontes já baixados e versionados em docs/referencias/.
- ✅ Bug identificado e corrigido: benchmark_ibge.py fazia o UPDATE em referencia_externa sem gravar versao_tabua (diferente dos outros 3 scripts, que gravam certinho) — mesmo rodando o benchmark do IBGE, a linha ficava sem o dado que o Passo 5 precisa para a comparação A/E. Já corrigido no código, com nota atualizada em regras_geracao.md e aviso adicionado na migration R__referencia_externa.sql para não perder os dados de novo no futuro.

### O que ficou pendente

- ⚠️ Rodar benchmark_ibge.py novamente contra o Postgres para a correção valer no banco — ainda não rodou porque não há Docker instalado nesta máquina.

---

## PASSO 4 — Cenários econômicos (Economic Scenario Generator)

**Dupla responsável:** Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira  
**Bloco do escopo:** Economic Scenario Generator (§6)

### Depende de outros passos

✅ Nenhuma dependência para começar — dupla livre, pode rodar em paralelo aos Passos 2 e 3. Só precisa alinhar parâmetros com os Passos 5 e 6 antes de finalizar, para não duplicar premissas divergentes.

### O que já foi feito

- ✅ Contrato econômico inicial `0.1.0` documentado em `cenarios-economicos/docs/SCENARIO_CONTRACT.md` em 2026-09-13: variáveis, unidades, fontes, entrada, saída, regras de ajuste, validação e reprodução.
- ✅ Planejamento atualizado para integração direta pela API HTTP, sem componente de automação intermediário.

- ✅ Premissas sintéticas e regras aditivas dos três cenários criadas em `cenarios-economicos/config/`, versão `0.1.0`, com fontes internas, responsáveis e justificativas em `docs/ASSUMPTIONS.md`. Exemplo completo de requisição em `examples/`; valores conferidos com aritmética decimal, sem execução de gerador.

- ✅ Núcleo determinístico `0.1.0` implementado em `cenarios-economicos/app/services/scenario_generator.py`, com validação, aritmética decimal exata, trajetórias anuais e snapshots independentes. Os 18 testes locais passaram; evidência em `cenarios-economicos/docs/CORE_VALIDATION.md`.

- ✅ Camada de aplicação e persistência PostgreSQL implementadas: IDs, horário UTC, snapshots, consulta de execuções/cenários, transação atômica e conflito de versões sob concorrência. Cliente local disponível via `python -m app`; testes com PostgreSQL real registrados em `cenarios-economicos/docs/PERSISTENCE_VALIDATION.md`.

- ✅ API FastAPI implementada em `cenarios-economicos/app/main.py`: health, geração HTTP 201 após commit, consultas, erros estruturados e documentação OpenAPI. Suíte com 45 testes aprovada e fluxo real via Uvicorn/PostgreSQL verificado; evidência em `cenarios-economicos/docs/API_VALIDATION.md`.

- ✅ Containerização implementada: imagem com usuário não root, Compose com PostgreSQL interno, volume persistente, migração antes da API, health check e Compose de testes isolado. Os 45 testes passaram dentro do Docker; evidência em `cenarios-economicos/docs/CONTAINER_VALIDATION.md`.

### O que ficou pendente

- ⚠️ Alinhar o contrato com os Passos 5 e 6 e identificar os consumidores de projeção/avaliação. A versão inicial ainda não está estabilizada entre as duplas.

### O que fazer

Bloco relativamente independente dos demais — pode começar assim que houver clareza sobre quais variáveis econômicas o projeto vai precisar (taxa de juros, inflação, etc. aplicáveis ao CD/CV).

- Começar por cenários determinísticos parametrizáveis — nada de Monte Carlo ainda, seguindo o princípio de baseline antes de complexidade.
- Definir as premissas econômicas de forma versionada e documentada, do mesmo jeito que o dataset sintético.
- Monte Carlo, correlações entre fatores e stress testing entram só como evolução condicionada, depois que os cenários determinísticos estiverem validados e houver necessidade demonstrada.
- Alinhar com o Passo 5 (tábua própria) e o Passo 6 (geracional) se haverá consumo direto de parâmetros econômicos ou integração no componente de projeção, para não duplicar premissas divergentes.

---

## PASSO 5 — Tábua biométrica própria

**Dupla responsável:** Maria Clara Oleari de Araujo e Guilherme Coelho Mendonça  
**Bloco do escopo:** Experiência biométrica e tábua própria (§6)

### Depende de outros passos

⚠️ Depende do Passo 3 só para a etapa de comparação A/E (precisa do qx do IBGE em referencia_externa). O Passo 3 já está quase concluído — falta só rodar o script novamente após a correção do bug. As demais etapas — taxas brutas, suavização, credibility interno, IC, validação temporal — não dependem de nada e podem começar agora.

### O que já foi feito

As 9 etapas do fluxo da tábua própria já estão implementadas como scripts individuais, orquestradas por um pipeline único. A ambiguidade metodológica do credibility também já foi resolvida.

- ✅ As 9 etapas do fluxo — taxas brutas de qx, coortes e contagem de eventos por submassa, comparação A/E, suavização, teste de aderência, credibility, intervalos de confiança e validação temporal — implementadas como scripts individuais (ex.: taxas_brutas_qx.py, suavizacao.py).
- ✅ pipeline.py criado, orquestrando as 9 etapas em sequência e parando no primeiro erro (ex.: não roda suavizacao.py se taxas_brutas_qx.py falhou) — não precisa mais rodar cada etapa manualmente; os comandos individuais ficam documentados no README só como opção para repetir uma etapa isolada.
- ✅ Ambiguidade do credibility (baseline interno vs. externo) resolvida: usa o baseline interno da própria massa sintética, e a comparação com o IBGE é uma etapa de validação separada e posterior — consistente com a ordem do fluxo do §3/§4.3 do escopo (credibility e "comparação com tábua externa" aparecem como etapas distintas).
- ✅ Estrutura do experiment_record.md pronta, incluindo a nova coluna "Veredito tabua_propria.py" — hoje só falta preencher com números reais.

### O que ficou pendente

Único item pendente: rodar e testar tudo de ponta a ponta. Nenhuma decisão de método ou código em aberto — é só execução e leitura de resultado.

- ⚠️ Subir o Postgres (docker compose up -d dentro de ambiente-de-dados/), aplicar as migrations e popular a massa sintética — hoje bloqueado só pela falta de Docker nesta máquina.
- ⚠️ Rodar python scripts/pipeline.py — um comando único que executa as 9 etapas em sequência e para no primeiro erro.
- ⚠️ Ler o veredito do tabua_propria.py: "PRONTA PARA OFICIALIZAR" ou "REVISAR", conforme os dois portões (aderência e A/E). P-valor baixo no teste de aderência → ajustar a JANELA=2 da suavização. Razão A/E fora de 0.5x–2x → revisar antes de considerar a tábua definitiva.
- ⚠️ Preencher o experiment_record.md com os números reais dessa primeira rodada (hoje vazio, só com a estrutura pronta).

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
