# Decisões: Passo 7 / SL-07

Registro das decisões técnicas, das alternativas consideradas e dos motivos. Cada decisão tem data e quem decidiu. Mudou de ideia? Acrescente uma decisão nova que substitui a antiga, sem apagar a anterior.

---

### D0. Entregar a SL-07 em 3 etapas, começando pelo Passo 6 (05/10/2026, dupla D3.7)

- **Decisão:** um PR por modelo de origem. Etapa 1 = Lee-Carter (Passo 6), Etapa 2 = tábua própria (Passo 5), Etapa 3 = Cox/RSF (Passo 2).
- **Alternativa:** uma entrega única com os três passos.
- **Motivo:** só o Passo 6 está pronto e tem contrato para o Passo 7. Os Passos 5 e 2 ainda não rodaram nos dados reais ou calibrados. PRs pequenos são revisados mais rápido.

### D1. Explicar o Lee-Carter pelos parâmetros + ALE + SHAP (05/10/2026, dupla D3.7)

- **Decisão:** gráficos de alpha_x, beta_x e kappa_t, mais ALE e SHAP de q(x,t) com as entradas idade e ano.
- **Alternativas:** (a) só SHAP; (b) só os parâmetros, sem ALE/SHAP.
- **Motivo:** o Lee-Carter é interpretável por construção, então os parâmetros são a explicação principal. ALE e SHAP traduzem esses parâmetros em efeito sobre q(x,t), que é o número que a Tribo 1 mostra no dashboard, e seguem o pedido da SL-07 (RF02).

### D2. SHAP calculado por fórmula exata, conferido contra a biblioteca `shap` (05/10/2026, dupla D3.7)

- **Decisão:** com só 2 entradas (idade e ano), os valores de Shapley são calculados pela fórmula fechada (média das 2 ordens possíveis), com fundo = grade histórica 2015-2024. Um teste confere que o resultado é igual ao de `shap.explainers.Exact`.
- **Alternativa:** chamar `shap.explainers.Exact` direto no script.
- **Motivo:** mesmo resultado (diferença < 1e-12 no teste), mas 0,9 s em vez de cerca de 27 s por rodada, e a fórmula pode ser explicada em 2 linhas. Fundo = período **observado**, para que o valor base seja "a mortalidade média que de fato vimos".

### D3. Monotonia de q por idade checada só a partir dos 30 anos (05/10/2026, Leticia)

- **Decisão:** a checagem `q_cresce_com_idade` (que bloqueia) vale para idades ≥ 30. Abaixo disso, quedas viram o alerta `corcova_de_acidentes`.
- **Alternativas:** (a) checar de 20 a 70 e bloquear; (b) checar de 20 a 70 só como alerta; (c) perguntar à tribo antes.
- **Motivo:** nos dados reais, q aos 25-26 anos é menor que aos 24-25 em alguns anos (2015-2018 e 2022). É a "corcova de acidentes", um padrão demográfico conhecido (mortes por causas externas em adultos jovens), e não um erro. A Issue fala em "idades adultas"; 30 anos é o ponto em que a curva passa a crescer sem exceção nos dados.

### D4. Salto do kappa_t vira alerta, sem bloquear (05/10/2026, Leticia)

- **Decisão:** variação anual de kappa_t maior que 3 × |drift| gera o alerta `salto_kappa`.
- **Alternativa:** bloquear a publicação.
- **Motivo:** o salto de 2022 é um achado de model risk sobre os dados do Passo 6, não um erro desta explicação. Bloquear impediria a Etapa 1 sem resolver nada. O limite de 3 × |drift| é simples de explicar ("a variação daquele ano foi mais de 3 vezes o ritmo médio") e, nos dados atuais, separa bem os anos normais (cerca de 1,0) dos saltos (6,3 e 4,3).

### D5. Reproduzir os limites de q do Passo 6 (05/10/2026, dupla D3.7)

- **Decisão:** q(x,t) é recalculado com o mesmo corte do Passo 6 (`projetar_lee_carter`: q entre 0,000001 e 0,999). Se algum valor bater no limite, gera o alerta `q_no_limite_de_corte`.
- **Alternativa:** usar a fórmula sem corte.
- **Motivo:** a explicação precisa ser do modelo que o Passo 6 realmente usa. Um teste compara nossa fórmula com a função do Passo 6.
- **Precisada pela D8:** a igualdade vale na projeção; nos anos históricos há uma diferença consciente.

### D6. Experiment record em `.md` no formato MLflow (05/10/2026, dupla D3.7)

- **Decisão:** registrar as rodadas em `experiment_record_lee_carter.md`, com os blocos params/metrics/tags/artifacts.
- **Alternativa:** servidor MLflow.
- **Motivo:** ainda não há servidor MLflow combinado com a Tribo 5. O formato igual facilita a migração depois.

### D7. Saídas sobrescritas a cada rodada; histórico pelo Git (05/10/2026, dupla D3.7)

- **Decisão:** o script grava sempre em `docs/lee_carter/` com os mesmos nomes. Cada rodada oficial é commitada e ganha uma entrada nova no experiment record com o SHA do commit.
- **Alternativa:** uma pasta nova por rodada.
- **Motivo:** evita acumular cópias de PNG no repositório; o Git já guarda cada versão. O JSON traz `rodada.id` e `rodada.commit`, então nenhuma rodada se perde.

### D8. Anos históricos usam o kappa_t ajustado; precisa a D5 (05/10/2026, dupla D3.7)

- **Decisão:** a D5 vale para a projeção (anos após o último ano histórico), em que nossa fórmula é idêntica à do Passo 6. Nos anos históricos usamos o kappa_t ajustado de cada ano. `projetar_lee_carter` usa kappa_T para qualquer ano ≤ T.
- **Alternativa:** copiar o comportamento do Passo 6 também nos anos históricos.
- **Motivo:** com kappa_T fixo, os 10 anos históricos teriam o mesmo q, e o ALE e o SHAP de "ano" não mostrariam a trajetória observada nem o salto de 2022. A diferença fica documentada pelo teste `test_qx_historico_difere_do_passo6_de_proposito`.

### D9. `estrutura_consistente` substitui `q_entre_0_e_1` (05/10/2026, dupla D3.7)

- **Decisão:** a checagem `q_entre_0_e_1` sai. Entra `estrutura_consistente`, que confere: tamanhos de alpha_x, beta_x e kappa_t contra idades e anos; idades crescentes; anos consecutivos. Se ela falhar, as demais checagens não são calculadas e o relatório sai BLOQUEADO. A faixa de q passa a aparecer no detalhe de `valores_finitos`.
- **Alternativa:** manter as duas.
- **Motivo:** `q_entre_0_e_1` nunca falhava, porque q já sai cortado em [0,000001; 0,999]. Uma entrada malformada, por outro lado, derrubava o script com exceção em vez de gerar o relatório BLOQUEADO.

### D10. Alerta `beta_negativo` (05/10/2026, dupla D3.7)

- **Decisão:** beta_x < 0 em alguma idade gera um alerta, sem bloquear.
- **Alternativa:** bloquear.
- **Motivo:** beta negativo quer dizer mortalidade projetada subindo naquela idade. É um diagnóstico clássico do Lee-Carter e pode aparecer em séries curtas sem ser erro de cálculo. Segue a mesma lógica da D4: o achado é sobre o modelo de origem e vai para a dupla do Passo 6.

### D11. Controle de alterações locais e limpeza das saídas (05/10/2026, dupla D3.7)

- **Decisão:** (a) `rodada.commit_com_alteracoes_locais` olha `scripts/`, `schemas/` e `requirements.txt` desta pasta, `scripts/` e `contracts/` do Passo 6 e a série do IBGE (`ambiente-de-dados/docs/referencias/ibge_historico/`), mas não `docs/`. (b) Cada rodada apaga os PNGs da rodada anterior antes de gerar os novos.
- **Alternativa:** olhar só esta pasta inteira, como antes.
- **Motivo:** (a) uma mudança no Passo 6 ou nos dados muda o resultado e não era detectada; já preencher o experiment record ou ter saídas de uma rodada anterior marcava a rodada como "suja" sem motivo. (b) Sem a limpeza, uma rodada BLOQUEADA deixava os gráficos aprovados da rodada anterior ao lado de um JSON que não lista gráfico nenhum.

### Pendente para a dupla decidir

- **Limite do `salto_kappa`:** hoje é 3 × |drift| (D4). O drift depende só das pontas da série (MR2), e com drift perto de zero qualquer variação vira salto. Uma alternativa mais robusta é 3 × mediana(|Δkappa_t|). Não foi trocado porque muda os números já registrados na rodada 1.
- **Alerta `corcova_de_acidentes`** olha só os anos históricos, enquanto `q_cresce_com_idade` olha 2015-2054. Alinhar os dois pode mudar a contagem de 7 casos.
