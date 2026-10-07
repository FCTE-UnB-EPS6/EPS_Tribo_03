# Model card — Sobrevivência individual

Versão dos modelos: 0.2.1. Versão das saídas: 0.2.1.
Responsáveis: Caio Brandão Santos e Pedro Lucas Figueiredo Santana.
[SL-02 / issue #34](https://github.com/FCTE-UnB-EPS6/estudos-populacionais/issues/34).

## Propósito e dados

Estimar sobrevivência desde o ingresso até óbito para análises de risco
coletivo, a partir dos participantes sintéticos curados pelo Passo 1.
`main.py` lê `participante`, `evento` e `exposicao` no Postgres em
uma transação somente leitura, sem CPF e sem modificar a fonte.

Óbito válido dentro do acompanhamento é evento. Desligamento anterior censura;
aposentadoria e invalidez não encerram automaticamente o acompanhamento.
Inconsistências são excluídas com motivo, sem imputar óbitos ou durações.
Ausência ou valor inválido de exposição oficial também exclui o registro;
o motivo permanece na auditoria e não é preenchido a partir de datas.
Datas, IDs e exposição oficial são usados para rastreabilidade e auditoria.

**A estimativa individual é insumo para gestão de risco coletivo, nunca decisão automática sobre direitos individuais.**

## Métodos

KM é o baseline descritivo por sexo, idade ao ingresso, plano e submassa.
Cox PH usa penalização ridge 0,01. RSF usa 100 árvores, split mínimo 10,
folha mínima 5, max_features sqrt e seed 42.

Covariáveis: idade_ingresso, sexo_M, plano_BD, plano_CD, submassa_A e submassa_B.
Referências: F, CV e Plano C. Apenas constantes no treino são removidas.
Pearson, Spearman e Cramér V são calculados no treino; inclusão, remoção e
justificativas são registradas por covariável. Correlação não prova
independência; não se usa seleção automática baseada no holdout nem cópula.

Treino: ingressos anteriores ao corte, com desfechos censurados no corte.
Teste: ingressos a partir do corte. O cadastro é um snapshot atual; não se
reconstrói o conhecimento bitemporal que existia no passado.

Discriminação: C-index. Calibração: média prevista versus 1−KM, com IC95%.
Brier e IBS usam IPCW do treino dentro do suporte comum.
Subgrupos: sexo, plano, submassa e faixas fixas de idade. Falta de suporte
gera valor ausente e motivo, nunca uma métrica inventada.

A comparação preserva Cox se não houver ganho conjunto: C-index >0,02,
redução de erro de calibração >0,005, IBS não pior, pelo menos 10 eventos
no teste e IC95% positivos no bootstrap pareado. Não demonstra ganho externo.

## Resultados e limites

Rodada no Postgres local do autor em 07/10/2026: geração com 3.000
participantes, seed 42, referência 2026-10-07, corte 2016-01-01 e horizonte
5 anos. Foram extraídos 2.960 registros; 23 excluídos (0,78%) e 2.937 usados,
com 140 óbitos. Treino temporal: 1.916 participantes/40 óbitos até o corte;
teste: 1.021 participantes/20 óbitos, sendo 14 até cinco anos.

| Métrica no teste | Cox PH | Random Survival Forest |
|---|---:|---:|
| C-index | 0,62320 | 0,47862 |
| Brier em 5 anos | 0,01571 | 0,01621 |
| IBS | 0,00945 | 0,00965 |
| Erro absoluto de calibração global | 0,00643 | 0,00706 |

Cox foi mantido: RSF não atende aos critérios de ganho conjunto. C-index
de treino/teste do RSF: 0,96560/0,47862, compatível com sobreajuste.
Probabilidade média de óbito em cinco anos no Cox: 1,196%; observada por
KM: 1,839% (IC95% 1,071%–3,147%). O erro de 0,643 ponto percentual não
constitui, sozinho, uma aprovação de calibração individual.

As 22 avaliações por subgrupo produziram as métricas exigidas, dentro dos
mínimos operacionais do código; esses mínimos não garantem alta precisão.
Schoenfeld no treino não detectou violação a 5% (menor p: 0,056).
KM e Cox descritivo recuperaram as direções pontuais de idade/sexo.
HR por ano de idade ao ingresso: 1,0631 (IC95% 1,0472–1,0792);
HR M/F: 1,5343 (IC95% 1,1295–2,0841).

Os motivos das 23 exclusões foram conferidos e mantidos: 17 registros com
saída anterior ao ingresso/duração não positiva, cinco sem exposição oficial
e um óbito sem data. Quatro dos 17 também têm óbito anterior ao ingresso.
Nenhuma exposição ausente ou divergência acima de 0,03 ano na base usada.
Os hashes e a revisão estão no experiment record; as saídas completas ficam
em `data/resultado/`. Os números são da execução real informada pelo autor,
não de fixtures.

`padrao_mortalidade.json` compara sexo e idade por KM e HR Cox descritivo.
Direção pontual e IC95% são distintos. Idade ao ingresso não é idade atingida;
a checagem não recupera qx exato nem valida uma população real.
Poucos eventos, grupos raros, composição da massa e hipóteses PH/censura
independente limitam a interpretação.

A CLI aceita apenas extração do Postgres ou snapshot rastreado dessa extração.
A fixture local fica restrita aos testes. O hash identifica o conteúdo e a
versão do código; a identificação da carga é declarada pelo operador.

## Entrega

Os bundles temporais Cox/RSF, atributos em ordem, dados, divisão temporal,
estimativas, métricas, cards e manifesto são produzidos pelo mesmo comando.
A leitura dos bundles e a reprodução das previsões são verificadas nos testes.
O [README](../README.md) explica os arquivos e o consumo pelos Passos 7/8.
Execução completa não equivale a aprovação científica ou parecer de gate T6.
