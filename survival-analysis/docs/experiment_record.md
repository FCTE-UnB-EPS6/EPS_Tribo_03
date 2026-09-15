# Experiment Record — Modelo Individual de Sobrevivência

## Estado da integração oficial

**Pendente: rodada sobre as tabelas finais do Postgres do Passo 1.** Em 12/09/2026,
a tentativa de conexão ao endereço padrão `localhost:5433` foi recusada. Não há
instância/exportação do banco do grupo disponível neste ambiente. O script
interrompeu, sem gerar dados locais em substituição e sem publicar métricas oficiais.

Código do Passo 1 consultado: branch `feat/ambiente-de-dados`, commit `a36946f`.
Código original do Passo 2 revisado: `02e4ada` na branch
`docs/relatorio-atividades-tribo3`. As correções continuam nessa mesma branch.

## Registro histórico — resultados locais anteriores à correção

Os resultados publicados em 10/09 foram reproduzidos com o gerador local antigo.
O log e o CSV originais não estavam disponíveis; por isso a evidência identifica
fortemente a massa local, sem auditar historicamente o comando executado. Os
números **não devem ser atribuídos à extração oficial do Passo 1**.

| Resultado antigo | Valor | Interpretação correta |
|---|---:|---|
| Participantes / óbitos | 300 / 9 | Massa local antiga, seed 42, referência 31/08/2026 |
| KM em 5 / 10 anos | 0,9800 / 0,9744 | Descrição daquela massa |
| Log-rank por sexo | p=0,9244 | Não detectou diferença; poder limitado |
| Cox C-index | 0,7389 | No próprio treino, não validação |
| Cox AIC parcial | 98,77 | Ajuste, não calibração |
| RSF C-index treino / teste | 0,9881 / 0,5660 | Split aleatório 70/30, diferente da avaliação do Cox |
| RSF IBS | 0,0227 | Erro probabilístico, não medida exclusiva de calibração |
| Comparação chamada temporal | Cox 0,4033 / RSF 0,4881 | Inválida: ordenação por duração e risco do Cox invertido |

As médias dos folds publicados não foram reproduzidas exatamente na revisão;
sem versões/saída original, a divergência permanece aberta. A decisão escrita
mantinha Cox enquanto a função antiga promoveria RSF com esses valores. Essa
comparação foi substituída. Ausência de significância em Schoenfeld não confirma
riscos proporcionais. A fração censurada não é uma probabilidade de sobrevivência
em qualquer horizonte. O código antigo e os registros completos permanecem no
histórico Git, sem reescrita dos commits do colega.

## Rodada de verificação do software — 12/09/2026

**Finalidade: testar a implementação, não validar cientificamente a massa da tribo.**

| Campo | Valor |
|---|---|
| Fonte | Fixture sintética local revisada, independente do Passo 1 |
| Quantidade / seed / referência | 2.000 / 42 / 2026-08-31 |
| Óbitos totais / exclusões | 103 / 0 |
| Corte de ingresso | 2016-01-01, com desfechos de treino censurados nessa data |
| Horizonte | 5 anos |
| Treino / teste | 989 / 1.011 participantes |
| Óbitos treino após corte / teste | 27 / 52 |
| Óbitos teste até 5 anos / acompanhados até 5 anos | 44 / 369 |
| Covariáveis | idade_ingresso, sexo_M, plano_BD, plano_CD, submassa_A, submassa_B |
| Cox | penalizer=0,01 |
| RSF | 100 árvores, split=10, leaf=5, max_features=sqrt, seed=42 |
| Bootstrap | 200 reamostragens pareadas válidas de 200 |

| Métrica no mesmo teste | Cox PH | RSF |
|---|---:|---:|
| C-index | 0,514269 | 0,483166 |
| C-index treino (diagnóstico) | 0,577844 | 0,971513 |
| Brier aos 5 anos | 0,046449 | 0,047606 |
| IBS na grade comum registrada | 0,033995 | 0,034457 |
| Probabilidade média prevista de óbito em 5 anos | 0,013926 | 0,017350 |
| Probabilidade observada por KM em 5 anos | 0,055916 | 0,055916 |
| Erro absoluto de calibração global | 0,041990 | 0,038566 |

IC95% observado por KM: [0,041455; 0,075219]. IC95% bootstrap do ganho de C-index
(RSF − Cox): [−0,125813; 0,059258]. IC95% da redução de erro de calibração
(Cox − RSF): [0,001472; 0,005364].

**Veredito automatizado: `sem_ganho_conjunto`; Cox mantido como baseline.** RSF
não atingiu os limiares conjuntos. Estes valores servem para verificar o código,
não para escolher o modelo da rodada oficial. Schoenfeld no treino dessa fixture
sinalizou sexo_M (p=0,0223); a sinalização é registrada, não ocultada.

A fixture local padrão de 300 registros gerou 12 óbitos. Com corte em 2010-01-01,
o fluxo retornou `inconclusivo` por menos de dois eventos no treino após censura,
sem tentar inventar uma métrica. A fixture foi corrigida e não reproduz mais a
sequência aleatória nem a distribuição de ingresso do gerador local antigo.

### Comandos reproduzíveis

Dentro de `survival-analysis/`, após instalar `requirements.txt`:

```bash
python -m unittest discover -s tests -v
python scripts/construir_dataset.py --fonte local --data-referencia 2026-08-31 --n-participantes 2000 --saida data/teste_integracao/dataset_survival.csv
python scripts/kaplan_meier.py --dataset data/teste_integracao/dataset_survival.csv
python scripts/cox_ph.py --dataset data/teste_integracao/dataset_survival.csv
python scripts/comparar_modelos.py --dataset data/teste_integracao/dataset_survival.csv --data-corte 2016-01-01 --horizonte 5
```

Ambiente: Python 3.12; lifelines 0.30.0; scikit-survival 0.25.0; scikit-learn 1.6.1;
NumPy 2.2.6; pandas 2.2.3; SciPy 1.15.3; matplotlib 3.10.3; psycopg2-binary 2.9.10.
As dependências foram fixadas após detectar incompatibilidade do IBS entre
scikit-survival 0.25.0 e NumPy 2.5.3 (`np.trapz` removido).

Os manifestos de execução registram hashes do dataset e dos scripts, versões e
estado do Git, permitindo distinguir uma execução feita antes do commit final.

## Como registrar a rodada oficial

Ao disponibilizar o banco, executar os comandos do README, inspecionar
`dataset_survival.exclusoes.csv` e o diagnóstico de exposição e adicionar uma
rodada abaixo, sem substituir resultados locais por números sem procedência.
Registrar identificação/commit do Passo 1, referência, hash, contagens, exclusões,
corte, horizonte, suporte por grupo, métricas, veredito e limitações. O JSON gerado
é a fonte dos números e já contém as versões dos scripts/bibliotecas.

Não aumentar artificialmente a taxa de óbitos nem procurar cortes favoráveis
para fazer o challenger passar. Se os eventos forem insuficientes, registrar
essa limitação. Riscos competitivos não são requisito desta entrega.

**A estimativa individual é insumo analítico para risco coletivo, nunca decisão
automática sobre direitos individuais.**
