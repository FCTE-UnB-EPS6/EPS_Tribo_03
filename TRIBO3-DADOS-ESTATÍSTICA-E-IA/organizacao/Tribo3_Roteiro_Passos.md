# Tribo 3 — Dados, Estatística e IA
## Roteiro de passos

Oito passos, ordenados por desbloqueio: o que depende de menos coisas vem primeiro, mesmo que seja de uma dupla diferente.

---

## Passo 1 — Data quality e massa sintética

**Dupla responsável:** Júlia Takaki Neves e Jefferson Sena Oliveira
**Bloco do escopo:** Data quality e massa sintética (§6)
**Depende de:** nenhum passo — é a fundação, todos os demais dependem dele.

### Atividades
- Schema bitemporal em Postgres com as 7 entidades do desenho de referência (participante, evento, exposicao, contribuicao_beneficio, referencia_externa, dicionario_dados, data_quality_score), mais o schema gabarito.registro_erro_injetado.
- Gerador de massa sintética reprodutível (seed fixa, UUIDs derivados do rng, Faker).
- Camada staging (colunas TEXT) para viabilizar a injeção de imperfeições em campos que, nas tabelas finais, são tipados e obrigatórios.
- 9 regras automatizadas de qualidade (R01–R09), cobrindo completude, validade, consistência, unicidade, acurácia, temporalidade e materialidade.
- Dicionário de dados com os campos documentados (nome, tipo, unidade, domínio, obrigatoriedade, origem, responsável, versão).
- Pipeline que promove linhas aprovadas para as tabelas finais e mede precision/recall da limpeza contra o gabarito de erros injetados.
- Relatório de qualidade versionado, gerado a partir do estado do banco.
- Gerar o dicionário de dados como documento PDF formal, com capa, versão e data de emissão, organizado por entidade.
- Atribuir o nome da dupla responsável por cada tabela em dicionario_dados.responsavel.
- Ajustar o mapeamento do erro unidade_trocada (ou documentar por que ele diverge do desenho de referência).
- Registrar formalmente o tratamento LGPD (minimização e anonimização) do dataset antes da entrega.

---

## Passo 2 — Modelo individual de sobrevivência

**Dupla responsável:** Caio Brandão Santos e Pedro Lucas Figueiredo Santana
**Bloco do escopo:** Multiestado e survival analytics (§6)
**Depende de:** Passo 1 (participante, evento e exposicao estáveis).

### Atividades
- Baseline interpretável: Kaplan-Meier e/ou Cox, usando idade, sexo, plano_tipo e submassa como covariáveis.
- Modelos mais complexos (survival forest, gradient boosting survival, abordagens bayesianas) condicionados a ganho comprovado de calibração e discriminação frente ao baseline.
- Validação temporal e por subgrupo, com calibração e discriminação documentadas.
- Teste de correlação/dependência entre covariáveis (Pearson/Spearman e, quando justificado, cópulas) antes de incluir no modelo.
- Experiment record do treinamento (dados usados, hiperparâmetros, métricas, versão), além do model card.
- Registro no model card de que a estimativa individual é insumo analítico para gestão de risco coletivo, nunca decisão automática sobre direitos individuais.

---

## Passo 3 — Benchmark externo (IBGE e demais fontes)

**Dupla responsável:** Júlia Takaki Neves e Jefferson Sena Oliveira
**Bloco do escopo:** Data quality e massa sintética (§6) — qualidade e curadoria de dados
**Depende de:** nenhum passo formalmente (mesma dupla do Passo 1).

### Atividades
- Scripts de benchmark para as 4 fontes: benchmark_ibge.py, benchmark_hmd.py, benchmark_brems.py e benchmark_soa.py.
- Download e versionamento dos arquivos brutos das 4 fontes em docs/referencias/.
- Atualização das linhas de referencia_externa com versao_tabua e data_consulta de cada fonte.
- Comparação preliminar de plausibilidade (ordem de grandeza do qx sintético vs. cada fonte por faixa etária), registrada em resultado_benchmark.
- Rodar novamente benchmark_ibge.py contra o banco após a correção do preenchimento de versao_tabua.

---

## Passo 4 — Cenários econômicos (Economic Scenario Generator)

**Dupla responsável:** Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira
**Bloco do escopo:** Economic Scenario Generator (§6)
**Depende de:** nenhum passo — pode alinhar parâmetros com os Passos 5 e 6 antes de finalizar.

### Atividades
- Cenários determinísticos parametrizáveis (taxa de juros, inflação, etc. aplicáveis ao CD/CV).
- Premissas econômicas versionadas e documentadas, no mesmo padrão do dataset sintético.
- Monte Carlo, correlações entre fatores e stress testing como evolução condicionada, após os cenários determinísticos estarem validados.
- Alinhamento com os Passos 5 e 6 sobre quais parâmetros econômicos as tábuas vão consumir.

---

## Passo 5 — Tábua biométrica própria

**Dupla responsável:** Maria Clara Oleari de Araujo e Guilherme Coelho Mendonça
**Bloco do escopo:** Experiência biométrica e tábua própria (§6)
**Depende de:** Passo 3, só para a etapa de comparação A/E.

### Atividades
- Taxas brutas de qx: agregação de exposicao por idade exata e submassa.
- Construção e versionamento das coortes e da contagem de eventos por submassa como artefato próprio.
- Comparação A/E contra o qx do IBGE registrado no Passo 3.
- Suavização com método baseline simples (ex.: Whittaker-Henderson ou média móvel).
- Teste de aderência (KS, Anderson-Darling ou Qui-quadrado) sobre a curva suavizada.
- Credibility: blend entre taxa observada e baseline externo para submassas com exposição baixa.
- Intervalos de confiança (bootstrap ou IC binomial/Poisson) por célula de qx.
- Validação temporal via holdout por ano_calendario.
- Data card, model card e experiment record da tábua.

---

## Passo 6 — Tábuas geracionais e mortality improvement

**Dupla responsável:** Danielle Soares da Silva e Maria Eduarda Quaresma de Andrade
**Bloco do escopo:** Tábuas geracionais e improvement (§6)
**Depende de:** Passo 5 (tábua própria concluída).

### Atividades
- Método baseline para evolução de qx → qx,t (extrapolação de tendência a partir de exposicao.ano_calendario).
- Teste de tendência (Mann-Kendall) sobre o mortality improvement ao longo dos anos.
- Teste de estacionariedade (ADF/KPSS) na série temporal de qx.
- Comparação com Lee-Carter, CBD e/ou P-splines, condicionada a ganho real em backtest.
- Backtesting temporal usando os anos mais recentes como holdout.
- Data card, model card e experiment record específicos da tábua geracional, com o horizonte de projeção escolhido.

---

## Passo 7 — Explicabilidade (SHAP/ALE) e model risk

**Dupla responsável:** Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega
**Bloco do escopo:** Ensemble e diagnóstico probabilístico (§6) — etapa 5 do fluxo técnico do MVP
**Depende de:** Passos 2, 5 e 6 (modelos já existentes para explicar).

### Atividades
- Explicações SHAP/ALE para os modelos não triviais.
- Model card e experiment record de cada modelo entregue: propósito, população, dados, método, versão, métricas, limitações, origem dos dados.
- Relatório de limitações e vieses por subgrupo.
- Reporte à Tribo 4 das ameaças de inferência/reidentificação e superfícies de risco dos modelos.

---

## Passo 8 — Ensemble, calibração e diagnóstico probabilístico

**Dupla responsável:** Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega
**Bloco do escopo:** Ensemble e diagnóstico probabilístico (§6)
**Depende de:** Passo 7 concluído.

### Atividades
- Calibração e discriminação dos modelos documentadas, comparando sempre contra o baseline simples.
- Construção de modelos challenger e comparação via ensemble.
- Experiment record de cada rodada de comparação champion-challenger.
- Quantificação de incerteza por CVaR/distribuição de simulação, complementando os IC dos Passos 5 e 6.
- Métricas de promoção champion-challenger em formato consumível pela observabilidade da Tribo 5.
