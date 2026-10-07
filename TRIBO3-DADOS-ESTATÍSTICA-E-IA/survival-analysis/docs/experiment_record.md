# Experiment record — SL-02

Responsáveis: Caio Brandão Santos e Pedro Lucas Figueiredo Santana.
Revisão: 07/10/2026. Base: main `d2aa90a05772f002d75fe130e4cd291288e64363`.
[Issue #34](https://github.com/FCTE-UnB-EPS6/estudos-populacionais/issues/34).

## Execução e reprodução

Fonte: tabelas finais participante, evento e exposicao do Postgres local do
autor, recarregadas com o gerador e a curadoria existentes do Passo 1.
Carga: `Passo1_N3000_seed42_ref2026-10-07`; 3.000 participantes gerados,
seed 42, referência 2026-10-07. Corte: 2016-01-01. Horizonte: cinco anos.
Ambiente informado: Python 3.12.14 e versões fixadas em requirements.txt.

A massa inicial de 300 permitiu a execução, mas apenas três óbitos no teste,
um até cinco anos, impediram calibração/subgrupos. O volume foi aumentado
conforme a recomendação já documentada pelo Passo 1. Seed, referência,
corte, horizonte, modelos e limiares permaneceram iguais; não houve busca
por seed ou ajuste de parâmetros para fazer RSF vencer.

~~~bash
python main.py --data-referencia 2026-10-07 \
  --identificacao-fonte "Passo1_N3000_seed42_ref2026-10-07" \
  --data-corte 2016-01-01 --horizonte 5 --sobrescrever
~~~

O README documenta a carga local e o consumo. Uma execução produz dataset,
KM, Cox, RSF, dependências, validação temporal/subgrupos, modelos, previsões,
cards e manifesto em `data/resultado/`, sem logs ou rodadas versionados.

## Resultado no Postgres

Execução informada pelo autor: 2026-10-07T16:45:31–16:45:37Z.
Foram conferidos os JSONs de fechamento, avaliação e padrão de mortalidade,
e o CSV de motivos de exclusão enviados pelo autor. As cinco etapas
terminaram; os critérios automáticos produziram as evidências exigidas.
2.960 registros extraídos, 2.937 analíticos e 140 óbitos; treino/teste
1.916/1.021 participantes e 40/20 óbitos. Há 14 óbitos até cinco anos no teste.

Cox foi mantido, com C-index 0,62320, Brier 0,01571 e IBS 0,00945 no teste.
RSF: 0,47862, 0,01621 e 0,00965, respectivamente; sem ganho conjunto.
Todas as 22 avaliações por subgrupo produziram as métricas exigidas pelo
código. Não houve alerta de correlação alta ou violação PH no treino.
Idade/sexo tiveram direção esperada em KM/Cox descritivo. O model card
registra coeficientes, calibração e limites da interpretação.

## Conferência das exclusões

23 registros (0,78% dos extraídos) permaneceram excluídos:

| Motivo principal, sem contar a mesma pessoa duas vezes | Registros |
|---|---:|
| Desligamento anterior ao ingresso e duração não positiva | 13 |
| Óbito e desligamento anteriores ao ingresso e duração não positiva | 4 |
| Exposição oficial ausente | 5 |
| Status óbito sem data de óbito | 1 |
| Total | 23 |

Os motivos registrados justificam excluir esses registros para este modelo;
não se imputaram datas/exposições nem se reinseriram linhas. Esta conferência
revisa a auditoria recebida, sem reconsultar os registros brutos no banco do
autor. A base analítica registra zero exposições ausentes e zero diferenças
acima de 0,03 ano.

Hashes SHA-256 da rodada revisada:

- Dataset: `6c97afdd1bf93f930901414bbc6c15946e87125fcd5a6840fc4d3e05f5d481f3`.
- Auditoria de exclusões: `5900c846020ec61a0956b3924e7f5e43be875827bc0fec4b7370cfbbc823df73`.
- Extração bruta: `df402d7a01dc91f42329e48a33525c38f4ae816d637dfbf4db0f2ab948230b96`.

`fechamento.json` mantém `revisao_necessaria` porque qualquer exclusão gera
um alerta automático. Para esta rodada, a revisão dos motivos foi registrada
acima. Isso não apaga a auditoria nem aprova exclusões de futuras cargas.
O programa não emite parecer humano de merge ou gate T6.

## Validação do software e entrega

Comando: `python -m unittest discover -s tests -v`.
Nesta revisão: 47 testes, 45 aprovados e dois de Postgres pulados por falta
de servidor neste ambiente; os testes incluem a correção das mensagens.
Os testes controlados substituem somente a consulta SQL; modelos, métricas,
persistência, gráficos e leitura dos bundles são reais. Incluem censura,
contratos, exposição, integridade, previsões e preservação de arquivos ao
sobrescrever. Os dois testes opcionais de Postgres exigem servidor acessível:

~~~bash
PASSO2_TESTAR_POSTGRES=1 DATA_REFERENCIA=2026-10-07 \
  python -m unittest discover -s tests -v
~~~

A execução real acima é evidência de uso do Postgres; não foi recebido nesta
conferência o resumo final da suíte no computador do autor. O workflow usa
Postgres 16 e a carga de 3.000, testa o fluxo e exige suporte dos critérios.
Seu resultado no GitHub ainda precisa ser observado após o push.

A rodada recebida registra SHA `9cfef9327e8f30410c495c18ad7eb7a293d208fc`
e alterações locais, pois a correção de exposição ainda não estava commitada.
Os hashes dos scripts recebidos foram comparados com o código desta revisão.
Os ajustes finais de mensagens/documentação não alteram treino ou métricas.

Saídas e bundles permanecem na versão 0.2.1. A única entrada é `main.py`.
Modelos temporais, dados, covariáveis em ordem, previsões, métricas e manifesto
estão prontos para o consumo descrito no README. SHAP/ALE (#53) e
ensemble/CVaR (#54) são implementações dos consumidores. Revisão técnica e
T6 seguem a governança. Não se declara validação em população real.

A revisão altera apenas survival-analysis e seu workflow; nenhum arquivo
do gerador, migrations, curadoria ou módulos das outras duplas é alterado.

**A estimativa individual é insumo para gestão de risco coletivo, nunca decisão automática sobre direitos individuais.**
