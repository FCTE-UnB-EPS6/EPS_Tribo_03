# Model Card — Modelo Individual de Sobrevivência

## Propósito e estado da entrega

Estimar sobrevivência até óbito desde o ingresso no plano, como insumo analítico
para risco coletivo. O MVP não estima transições para invalidez, aposentadoria ou
desligamento. **Nunca usar para decisão automática sobre direitos individuais.**

Implementação revisada; integração e avaliação sobre a rodada oficial do Postgres
**pendentes**. Cox permanece como baseline por simplicidade, sem superioridade
preditiva declarada. Os números antigos correspondem a experimentos reproduzidos
com o gerador local e não validam o modelo na massa oficial.

## Dados

População-alvo do experimento: participantes sintéticos das tabelas curadas do
Passo 1. Extração atual por ID, eventos agregados e exposição agregada para auditoria.
A identificação de lote/versão é declarada pelo operador; o hash da extração
identifica seu conteúdo e não comprova, sozinho, qual comando gerou o banco.

| Campo | Uso |
|---|---|
| participante_id, data_ingresso, data_fim, data_referencia | Rastreabilidade e corte; não entram como preditores |
| tempo_observado, evento | Duração em anos e indicador de óbito dentro da janela |
| idade_ingresso | Idade calculada na data de ingresso |
| sexo, plano_tipo, submassa | Categorias preservadas para validação por grupo |
| sexo_M, plano_BD, plano_CD, submassa_A, submassa_B | Codificação de covariáveis; F, CV e Plano C são referências |
| exposicao_oficial_anos, diferenca_exposicao_anos | Diagnóstico de coerência, não preditores |

Datas ausentes/inválidas, ingresso sem acompanhamento, óbito sem data,
nascimento após ingresso e duração não positiva são excluídos com motivos.
IDs duplicados interrompem a construção. Não se inventa um óbito na referência
nem se substitui tempo negativo por 0,01 ano. Óbitos futuros não são eventos na
janela. Óbito e saída empatados contam como óbito; saída anterior censura.
Aposentadoria e invalidez não encerram exposição ao risco de morte.

## Modelos e seleção de covariáveis

- Cox PH com penalizador ridge 0,01; HR e Schoenfeld no treino.
- RSF com 100 árvores, `min_samples_split=10`, `min_samples_leaf=5`,
  `max_features=sqrt`, seed registrada.
- Lista de covariáveis definida pelo domínio; Pearson/Spearman são diagnósticos
  documentados, não um seletor automático. Constantes são removidas apenas com
  base no treino e a mesma lista é aplicada aos dois modelos. Pares com |r|>0,7
  ficam no registro para inspeção antes da conclusão científica.

O teste de Schoenfeld pode não detectar violação com poucos eventos; ausência de
significância não confirma a hipótese PH.

## Validação e métricas

Um corte de calendário explícito separa ingressos antigos e novos. O treino
limita desfechos ao corte; o teste usa o acompanhamento até a referência.
O snapshot cadastral é atual: não há reconstrução completa dos registros segundo
`data_conhecimento`, nem garantia de que plano/submassa eram iguais no ingresso.
Essa limitação impede apresentar a avaliação como um backtest prospectivo integral.

| Métrica | Interpretação |
|---|---|
| C-index de teste | Discriminação fora do treino; maior risco previsto = maior escore |
| C-index de treino | Diagnóstico de ajuste/otimismo, não evidência de generalização |
| Brier no horizonte e IBS | Erro probabilístico com censura (IPCW), combina calibração e discriminação |
| Erro de calibração global | Absoluto entre média prevista de óbito e 1−KM no horizonte; menor é melhor |
| Curva de calibração por tercis | Previsto versus observado por KM com IC95%; complemento ao erro global |
| AIC parcial | Ajuste do Cox, não calibração nem comparação direta com RSF |
| Log-rank global | Comparação descritiva das curvas KM por fator, não validação do Cox |

Horizonte padrão: 5 anos, substituível antes da rodada. Grade IBS: 30 pontos de
`max(0,01, menor tempo do teste)` até o horizonte, idêntica nos dois modelos e
registrada. Fora do suporte de treino/teste ou com pesos IPCW inválidos, Brier/IBS
ficam indisponíveis com motivo. Tempos de teste além de `tau` são censurados
administrativamente para a chamada Brier; `tau` é estritamente posterior ao
horizonte, preservando os desfechos de interesse. C-index usa o teste completo.

Calibração KM requer pelo menos 20 pessoas, 2 óbitos até o horizonte e 5 pessoas
acompanhadas até ele; C-index exploratório requer 2 eventos e pares comparáveis.
São limites operacionais mínimos, não garantias de precisão estatística. Grupos
sem suporte são registrados, não omitidos da tabela. Os tercis são definidos pelas
previsões somente para diagnóstico, sem reajustar modelos ou selecionar hiperparâmetros.

Validação por sexo, BD/CD/CV, Plano A/B/C e idade ao ingresso (até 30, >30 até 45,
>45): C-index e calibração direta no teste. KM e log-rank descritivos por sexo,
plano e submassa são entregues separadamente.

## Critério de comparação

Parâmetros definidos antes de analisar a rodada oficial:

- Ganho de C-index do RSF estritamente maior que 0,02.
- Redução do erro de calibração global estritamente maior que 0,005 (0,5 ponto percentual).
- IBS do RSF não superior ao do Cox.
- Pelo menos 10 eventos no teste e métricas disponíveis para ambos.
- IC95% percentil dos dois ganhos com limite inferior positivo: bootstrap pareado
  do teste, 200 amostras, ao menos 80% válidas, mesma seed registrada.

Esses limiares são convenções do experimento, não padrões atuariais. O bootstrap
é condicional aos modelos ajustados: não cobre incerteza de treino, múltiplas
rodadas ou generalização externa. Um resultado aprovado demonstra ganho apenas
nesse holdout. Ausência de métricas ou suporte gera **inconclusivo**; Cox é mantido
por simplicidade. Ganho pontual de C-index sozinho não promove o challenger.

## Limitações e rastreabilidade

Dados sintéticos não demonstram validade em pessoas reais. Poucos óbitos limitam
precisão, estabilidade dos coeficientes e testes por subgrupo. Censura independente
é uma hipótese necessária; 97% censurados não significa 97% sobreviventes em um
horizonte definido. Calibração global pode ocultar erros opostos entre indivíduos;
curvas e avaliações por grupo precisam ser lidas junto da métrica.

Versão do código, hashes dos scripts/dataset, bibliotecas, referência, exclusões,
divisão, hiperparâmetros, métricas e motivos ficam nos manifestos e no
[experiment record](experiment_record.md). Autores: Caio Brandão Santos e Pedro
Lucas Figueiredo Santana.

## Referências técnicas

- [C-index e direção do risco — scikit-survival](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.metrics.concordance_index_censored.html).
- [Brier e pesos IPCW — scikit-survival](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.metrics.brier_score.html).
