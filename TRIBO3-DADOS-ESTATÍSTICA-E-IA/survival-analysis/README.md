# Modelo individual de sobrevivência — SL-02

Responsáveis: Caio Brandão Santos (@caiobsantos) e Pedro Lucas Figueiredo Santana (@pedrolucas12).
[Issue #34](https://github.com/FCTE-UnB-EPS6/estudos-populacionais/issues/34).

`main.py` é a única entrada da aplicação. Ela consulta as tabelas finais do
Passo 1 no Postgres, prepara o dataset, roda Kaplan-Meier, Cox e Random Survival
Forest, avalia os modelos e salva os resultados. Não escreve no banco.

**A estimativa individual é insumo para gestão de risco coletivo, nunca decisão automática sobre direitos individuais.**

## Executar no banco do Passo 1

Primeiro, o Passo 1 precisa ter concluído a promoção de staging para as tabelas
finais. Reiniciar um contêiner não atualiza uma carga antiga. Use a mesma data
de referência que foi usada para gerar a carga; não escolha outra data para
melhorar as métricas.

Na pasta `survival-analysis`, ative o ambiente já existente:

~~~bash
source .venv/bin/activate
python -m pip install -r requirements.txt
~~~

Se ainda não houver ambiente, crie-o com `python3.12 -m venv .venv`.
No PowerShell, a ativação é `.venv\Scripts\Activate.ps1`.

Para reproduzir a avaliação registrada nos cards, use a carga do Passo 1
com `N_PARTICIPANTES=3000`, `SEED=42` e `DATA_REFERENCIA=2026-10-07`.
O próprio dataset card do Passo 1 recomenda aumentar o volume para análises
atuariais. O lote de 300 é útil para qualidade de dados, mas nesta avaliação
não deu suporte para calibração/subgrupos. O aumento foi decidido por falta
de eventos, mantendo seed, referência, corte, horizonte e limiares.

Se o banco sintético local puder ser apagado, na pasta `ambiente-de-dados`
use o mesmo projeto Compose que criou o contêiner existente. Os comandos
abaixo substituem os volumes locais desse projeto; não modificam o código
nem o banco de colegas. Execute um por vez e pare em caso de erro.

~~~bash
export COMPOSE_PROJECT_NAME="$(docker inspect tribo3-db --format '{{ index .Config.Labels "com.docker.compose.project" }}')"
docker compose down -v
docker compose up -d db
docker compose run --rm migrate
docker compose build seed
docker compose run --rm --no-deps \
  -e N_PARTICIPANTES=3000 -e SEED=42 -e DATA_REFERENCIA=2026-10-07 \
  -v "$PWD/docs/referencias:/docs/referencias:ro" seed
~~~

A montagem disponibiliza as tábuas ao contêiner sem editar o Compose do
Passo 1. Se a carga acima já foi realizada, use o banco existente.
De volta à pasta `survival-analysis`, execute:

~~~bash
python main.py \
  --data-referencia 2026-10-07 \
  --identificacao-fonte "Passo1_N3000_seed42_ref2026-10-07" \
  --data-corte 2016-01-01 \
  --horizonte 5
~~~

A saída padrão é `data/resultado/`, ignorada pelo Git. Todas as validações
acontecem nesse comando; não há scripts separados de treinamento a executar.
Use `--saida CAMINHO` se precisar guardar outra execução.

Para repetir na mesma pasta, acrescente `--sobrescrever`. Essa opção substitui
somente uma pasta de resultados concluídos, reconhecida pelo manifesto, e
recusa arquivos adicionais ou um snapshot de entrada dentro da mesma pasta.
Ela não apaga outras pastas de dados nem modifica o Postgres.

A conexão padrão é `localhost:5433`, banco/usuário `tribo3` e senha local
`tribo3_dev`. Se seu Compose usa valores diferentes, configure `PGHOST`,
`PGPORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` no terminal.
A aplicação não carrega um arquivo `.env` automaticamente.

## Conferir os resultados

Comece por `data/resultado/fechamento.json`. Ele registra as etapas executadas,
os cinco critérios da issue #34, o ambiente e as limitações encontradas.

| Saída | Conteúdo |
|---|---|
| `dataset_survival.csv` e arquivos associados | Dataset, procedência, extração bruta e exclusões justificadas |
| `km/` | Curvas KM por sexo, idade, plano e submassa; log-rank |
| `avaliacao/resultado.json` | Discriminação, calibração, Brier/IBS, parâmetros e comparação Cox/RSF |
| `avaliacao/metricas_subgrupos.csv` | Métricas e motivos de insuficiência por grupo |
| `avaliacao/dependencia_covariaveis.json` | Pearson, Spearman, Cramér V e decisões por covariável |
| `avaliacao/divisao_temporal.csv` | Participantes de treino/teste e desfechos censurados no corte |
| `avaliacao/modelos/` | Cox/RSF treinados e estimativas individuais no teste |
| `cox_descritivo/` e `padrao_mortalidade.json` | Coeficientes, Schoenfeld e checagem de idade/sexo na massa completa |
| `model_card.md` e `experiment_record.md` | Cards preenchidos automaticamente com os números dessa execução |
| `manifesto_artefatos.json` | Versão e hashes das saídas para conferir integridade |

Código 0 significa execução sem alertas automáticos; código 2 **com fechamento**
significa execução concluída com alertas para revisão. Exclusões também
produzem esse código: após conferir os motivos, registre a revisão no
experiment record, vinculada ao hash do dataset e da auditoria. Um alerta
não implica falha de execução ou necessidade de reinserir registros.
Código 1 indica falha de execução,
registrada em `falha_execucao.json`, com o erro exibido no terminal. Erro de
argumentos também retorna 2, mas não produz um fechamento.

Os limiares são definidos no código e permanecem fixos. Poucos óbitos podem
impedir métricas por grupo ou a confirmação de idade/sexo. Isso é registrado
explicitamente. Não se altera seed, corte, horizonte ou limiar para produzir
uma aprovação. RSF não precisa superar Cox para que a comparação seja executada.

## Testar

~~~bash
python -m unittest discover -s tests -v
~~~

Para incluir o contrato e o fluxo completo no seu Postgres carregado:

~~~bash
PASSO2_TESTAR_POSTGRES=1 DATA_REFERENCIA=2026-10-07 \
  python -m unittest discover -s tests -v
~~~

Os testes de Postgres são somente leitura e usam uma pasta temporária para
os resultados, removida ao terminar. Não criam outro banco no seu Docker.
Os demais testes usam dados controlados; a consulta é substituída, mas os
ajustes KM/Cox/RSF, cálculos, gráficos e arquivos de modelo são executados.

O workflow `Modelo de sobrevivência` testa a branch com Postgres 16, aplica
as migrations existentes, carrega o gerador e a curadoria do Passo 1 e publica
os resultados como artefato do CI. Usa 3.000 participantes e exige
que os critérios automáticos tenham suporte, sem emitir aceite humano.
Ele usa um banco temporário do runner do
GitHub, sem acessar o banco local de ninguém. O teste local não substitui o
resultado de uma execução desse workflow.

## Consumo pelos Passos 7 e 8

A entrega é a pasta `data/resultado/` completa, ou o artefato `survival-SHA`
do CI. Ela contém dados, separação temporal, modelos, previsões, métricas e
cards. Os arquivos de execução não são adicionados automaticamente ao Git.

Cada `cox.joblib`/`rsf.joblib` é um dicionário com `modelo`,
`covariaveis` na ordem usada no treino, `versao_modelo`, `data_corte` e
`finalidade`. Os modelos foram ajustados somente no treino temporal.
O Cox da pasta `cox_descritivo` é uma análise separada da massa completa.

~~~python
from pathlib import Path
import hashlib
import json
import joblib
import pandas as pd
from scripts.avaliacao import dividir_temporal

pasta = Path("data/resultado")
manifesto = json.loads((pasta / "manifesto_artefatos.json").read_text())
arquivo = pasta / "avaliacao/modelos/cox.joblib"
assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == manifesto["arquivos"]["avaliacao/modelos/cox.joblib"]
bundle = joblib.load(arquivo)
dataset = pd.read_csv(pasta / "dataset_survival.csv")
treino, teste = dividir_temporal(dataset, bundle["data_corte"])
X = teste[bundle["covariaveis"]]
risco = bundle["modelo"].predict_partial_hazard(X)
~~~

O RSF recebe `X.to_numpy()`; o Cox recebe DataFrame com nomes. Carregue
joblib apenas de arquivos produzidos pela equipe e conferidos no manifesto.
Hashes conferem integridade, não tornam um arquivo de origem desconhecida seguro.

`estimativas_teste.csv` contém o ID sintético, escores de risco,
probabilidades de óbito/sobrevivência e horizonte por modelo.
Escores de risco não são probabilidades. Valores ausentes indicam horizonte
sem suporte; o motivo fica no resultado JSON. A falta de suporte IPCW para
Brier não apaga uma previsão suportada pelo modelo.

A [#53](https://github.com/FCTE-UnB-EPS6/estudos-populacionais/issues/53)
consome esses objetos para SHAP/ALE, leitura dos coeficientes e análise de
vieses/reidentificação. A
[#54](https://github.com/FCTE-UnB-EPS6/estudos-populacionais/issues/54)
trata novos challengers, ensemble, CVaR e promoção após a explicabilidade.
Essas atividades pertencem à dupla consumidora. Este módulo entrega os
artefatos de entrada e não altera o contrato do Passo 6.

[Model card](docs/model_card.md) · [Experiment record](docs/experiment_record.md)
