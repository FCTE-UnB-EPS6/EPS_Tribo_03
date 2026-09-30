# EPS_Tribo_03 — Dados, Estatística e IA

Projeto da Tribo 3 (curso de atuária/previdência complementar, EPS6) cobrindo
os 8 passos do roteiro em `organizacao/Tribo3_Roteiro_Passos.md`: massa de
dados, modelagem de sobrevivência, benchmark externo, cenários econômicos,
tábua biométrica própria, tábuas geracionais, explicabilidade e ensemble.

Desde set/2026 o projeto migrou de dados 100% sintéticos para uma massa de
**estrutura sintética com parâmetros calibrados por fonte pública real**
(IBGE, Banco Central, BR-EMS). Ver `plano-dados-reais-tribo3.pdf` na raiz
para a arquitetura completa da migração, o catálogo de fontes e o registro
de execução atualizado por passo.

## Estrutura

| Pasta | Passo | Dupla | O que faz |
| --- | --- | --- | --- |
| `ambiente-de-dados/` | 1 (+ 3) | Júlia Takaki Neves e Jefferson Sena Oliveira | Schema Postgres, gerador de massa sintética calibrado com qx real do IBGE, pipeline de qualidade, benchmarks externos (IBGE/HMD/BR-EMS/SOA) |
| `survival-analysis/` | 2 | Caio Brandão Santos e Pedro Lucas Figueiredo Santana | Kaplan-Meier, Cox PH, Random Survival Forest sobre `participante`/`exposicao` |
| `cenarios-economicos/` | 4 | Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira | API de geração de cenários econômicos; coletores reais de Bacen SGS e Ibovespa, artefato de calibração versionado |
| `tabua-biometrica-propria/` | 5 | Maria Clara Oleari de Araujo e Guilherme Coelho Mendonça | Taxas brutas, suavização, credibility, IC, comparação A/E (BR-EMS principal) e consolidação da tábua própria |
| `tabuas-geracionais-improvement/` | 6 | Danielle Soares da Silva e Maria Eduarda Quaresma de Andrade | Detecção de tendência (Mann-Kendall), Lee-Carter, projeção geracional sobre série histórica real do IBGE |
| — (não iniciado) | 7 | Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega | Explicabilidade (SHAP/ALE) e model risk |
| — (não iniciado) | 8 | Leticia Arisa Kobayashi Higa e Victor Pontual Guedes Arruda Nóbrega | Ensemble, calibração e diagnóstico probabilístico |

`docs/` guarda o relatório de atividades histórico (snapshot anterior ao
pivô de dados reais) e `organizacao/` guarda o escopo e o roteiro originais
do curso.

## Ordem de execução

O Passo 1 é pré-requisito de fato para os Passos 2, 5 e 6 (todos consomem a
massa calibrada). O Passo 4 não depende de nada e pode rodar em paralelo.
Os Passos 7/8 dependem dos modelos das fases anteriores já re-treinados.
Detalhe completo em `plano-dados-reais-tribo3.pdf`, seção "Ordem de
execução e responsáveis".

## Por onde começar

Cada pasta tem seu próprio `README.md` com "Primeira vez", como rodar os
scripts e como rodar os testes. `ambiente-de-dados/` é o ponto de partida —
os demais passos leem as tabelas ou os arquivos que ele produz.
