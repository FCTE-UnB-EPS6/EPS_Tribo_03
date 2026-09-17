# Premissas e regras demonstrativas

Versão: `0.1.0`

Data de referência: 2026-09-13

Status: sintético, para desenvolvimento; sem calibração ou aprovação atuarial.

Responsáveis: Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira.

## Artefatos e utilização

- [Premissas](../config/assumptions.demo.v0.1.0.json): conjunto `demo-economic`, versão `0.1.0`.
- [Regras](../config/scenario_rules.demo.v0.1.0.json): conjunto `demo-additive`, versão `0.1.0`.
- [Requisição completa](../examples/generate.demo.v0.1.0.json): exemplo para o futuro endpoint de geração.
- [Contrato econômico](SCENARIO_CONTRACT.md): interface `0.1.0` que estes arquivos seguem.

Os arquivos usam JSON para permitir leitura e conferência com a biblioteca padrão
do Python, sem dependência adicional de YAML. O formato substitui o YAML sugerido
no planejamento; a semântica das regras permanece a do contrato.

O arquivo de premissas reúne identidade, versão, unidade, base, valores e fontes.
O exemplo acrescenta a versão do contrato, a data-base, o horizonte e a referência
exata das regras. As referências a `docs/ASSUMPTIONS.md` nos arquivos são relativas
à pasta `cenarios-economicos/`. O exemplo é uma entrada, não evidência de execução:
o núcleo, a aplicação, a persistência e a API HTTP estão implementados e testados localmente.

## Valores-base e origem

Todas as taxas são nominais efetivas anuais em fração decimal. Os números foram
escolhidos para demonstrar o contrato e a aplicação dos ajustes; não foram extraídos
de bases econômicas, não são projeções de mercado e não usam os benchmarks biométricos.

| Variável | Valor no arquivo | Leitura | Interpretação |
|---|---|---|---|
| `inflation` | `0.04` | 4% a.a. | Índice de preços fictício, sem vinculação a um índice observado |
| `discount_rate` | `0.08` | 8% a.a. | Desconto nominal constante, definido separadamente do retorno |
| `salary_growth` | `0.045` | 4,5% a.a. | Crescimento salarial nominal total, já incluindo inflação |
| `asset_return` | `0.09` | 9% a.a. | Retorno nominal bruto de carteira fictícia, sem dedução de administração, transações ou tributos |

Salário e retorno são opcionais no contrato, mas estão presentes neste conjunto
para exercitar as quatro variáveis. Para demonstrar sua ausência, criar outro
conjunto ou nova versão, removendo tanto os valores quanto suas fontes; não
alterar o conteúdo associado ao mesmo ID e versão. Ausência não significa zero.

A data-base do exemplo é 2026-09-13 e seu horizonte é de dez períodos anuais,
até 2036-09-13. Trata-se de escolha de demonstração, não de horizonte suficiente
para avaliar todas as obrigações do plano. Cada taxa permanece constante nos dez
períodos. Datas de referência das fontes e data-base têm funções diferentes.

## Ajustes e justificativas

Aplicar `taxa_do_cenario = taxa_base + ajuste`. A tabela abaixo apresenta os
ajustes em pontos percentuais; os arquivos armazenam frações decimais.
Por exemplo, `0.02` corresponde a +2 pontos percentuais.

| Variável | Base | Adverso | Favorável |
|---|---|---|---|
| Inflação | 0 p.p. | +2 p.p. | -1 p.p. |
| Desconto | 0 p.p. | -2 p.p. | +1 p.p. |
| Crescimento salarial | 0 p.p. | +1 p.p. | -0,5 p.p. |
| Retorno dos ativos | 0 p.p. | -3 p.p. | +2 p.p. |

Base preserva as entradas. Adverso combina inflação e crescimento salarial maiores
com desconto e retorno menores; Favorável aplica a direção oposta. As magnitudes
são escolhas sintéticas, inclusive sua assimetria. Não representam percentis,
intervalos de confiança, correlações estimadas ou choques calibrados.

Todos os cenários usam `target_metric: illustrative_only`. A classificação só
poderá ser associada a um efeito verificado sobre passivo, déficit ou solvência
após definição da métrica e execução pelo consumidor. Não há regra que vincule
automaticamente inflação a benefícios, nem igualdade entre desconto e retorno.

## Gabarito aritmético para implementação

Esta tabela é calculada diretamente das premissas e dos ajustes, e utilizada como gabarito independente nos testes do núcleo. Os valores esperados são iguais em todos os períodos.

| Campo | Base | Adverso | Favorável |
|---|---|---|---|
| `inflation` | `0.04` | `0.06` | `0.03` |
| `discount_rate` | `0.08` | `0.06` | `0.09` |
| `salary_growth` | `0.045` | `0.055` | `0.04` |
| `asset_return` | `0.09` | `0.06` | `0.11` |

A implementação deve preservar as quatro chaves, gerar três cenários com dez
períodos e aplicar aritmética decimal. O exemplo completo repete os valores e
fontes do arquivo de premissas para ser uma requisição autossuficiente.

## Domínios e plausibilidade

O domínio técnico adotado é taxa finita maior que `-1`, com até oito casas
decimais, antes e depois do ajuste. Os arquivos demonstrativos satisfazem essas
restrições. O limite de horizonte do contrato é de 1 a 120 anos.

**Faixas de plausibilidade econômica ainda não estão definidas.** Não há base
empírica selecionada para justificá-las nesta etapa. Os valores da tabela não
constituem mínimos ou máximos aceitos pelo sistema. Antes de usar premissas
externas, documentar por variável a fonte, o período de referência, a justificativa
dos limites e se sua violação deve gerar aviso ou rejeição. Alterações nas regras
de validação exigirão atualização explícita do contrato.

## Versionamento e pendências

Preservar estes arquivos como versão `0.1.0`. Mudanças de valores, fontes ou
ajustes exigem nova versão e novo arquivo; atualizar o exemplo para referenciar
o par pretendido. Data-base e horizonte podem variar sem alterar a versão das
premissas. A futura execução deverá preservar os dois snapshots e a versão do
gerador, além de seus próprios identificadores.

Próximas atividades:

- Preparar a demonstração no servidor de implantação; containerização validada localmente.
- Alinhar calendário, horizonte, opcionais e métrica-alvo com os consumidores.
- Selecionar fontes externas e critérios de plausibilidade quando houver uso além da demonstração.
- Registrar o processo de revisão das premissas e as decisões entre duplas.

Nenhuma das pendências de alinhamento foi considerada concluída pela criação
destes arquivos.
