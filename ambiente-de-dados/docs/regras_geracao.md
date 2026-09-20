# Regras de geração e de qualidade — massa sintética v1

Declaração explícita do que o gerador reproduz, exigida pelo §6 do
documento de referência ("o gerador deve declarar explicitamente quais
distribuições, dependências, eventos raros e inconsistências
intencionais reproduz").

## Parâmetros da rodada padrão

| Parâmetro | Valor | Onde muda |
| --- | --- | --- |
| Volume | 300 participantes | `N_PARTICIPANTES` no `.env` |
| Seed | 42 | `SEED` no `.env` |
| Data de referência | data de hoje | `DATA_REFERENCIA` no `.env` (AAAA-MM-DD) |
| Biblioteca | Faker (pt_BR) + `random.Random` | — |

**Reprodutibilidade (§6):** mesma `SEED` + mesma `DATA_REFERENCIA` + mesma tábua de
calibração = dataset idêntico, ids inclusive. Os UUIDs saem de `dominio.novo_uuid(rng)`,
e não de `uuid.uuid4()`, justamente porque `uuid4` ignora a seed. Se `DATA_REFERENCIA`
ficar vazia o gerador usa a data de hoje — reproduzir um lote antigo exige fixá-la. A
tábua entra pelos arquivos versionados em `docs/referencias/`, não pela rede: nenhuma
etapa da geração faz requisição HTTP, então nada muda debaixo do dataset entre duas
execuções.

## Calibração com dado real

A **estrutura** da massa é sintética; os **parâmetros** que governam a trajetória de
cada participante vêm de fonte pública real. Os dois blocos abaixo são distintos de
propósito — citar o segundo como "dado calibrado" seria falso.

### CALIBRADO — mortalidade por idade e sexo

| Item | Valor |
| --- | --- |
| Fonte | IBGE — Tábua Completa de Mortalidade 2024 |
| Arquivos | `docs/referencias/ibge_2024_homens.xlsx`, `ibge_2024_mulheres.xlsx` |
| Cobertura | qx por idade exata, 0 a 90 anos, separado por sexo |
| Fator de seleção | **0,85× o qx do IBGE** (ver abaixo) |
| Onde muda | `scripts/calibracao.py` |

O fator de seleção é uma premissa **declarada**, não estimada a partir de experiência
própria: participante de fundo fechado tem mortalidade abaixo da população geral
(renda, acesso a saúde, vínculo formal). Declará-lo explicitamente é o que impede que
calibrar com o IBGE e validar contra o IBGE vire um teste circular — ver "Limitações".

### PREMISSA — decrementos que não são mortalidade

Nenhum destes foi extraído de fonte; são ordem de grandeza plausível e nada mais. As
fontes ideais seriam AEPS/PREVIC (aposentadoria) e RAIS/CAGED (desligamento).

| Decremento | Taxa anual | Nota |
| --- | --- | --- |
| Desligamento (saída do plano) | 3% | Saída do **plano** é mais rara que a rotatividade do emprego — quem troca de empregador frequentemente segue como autopatrocinado |
| Aposentadoria | 30% após elegível | Elegibilidade aos 65 (M) / 62 (F) anos |
| Invalidez (→ pensionista) | 0,2% | — |

## Distribuições amostradas

- **plano_tipo**: uniforme entre BD, CD, CV
- **submassa**: uniforme entre "Plano A", "Plano B", "Plano C"
- **sexo**: uniforme M/F
- **status_atual**: **não é sorteado** — emerge da simulação ano a ano (ver abaixo)
- **data_ingresso**: uniforme nos últimos 30 anos, até 30 dias antes da data de referência
- **data_nascimento**: derivada da idade **de entrada** (uniforme entre 18 e 55 anos) e da
  data de ingresso. A idade *atual* não é sorteada — é consequência de quando a pessoa
  entrou e de quanto tempo sobreviveu.
- **cpf_sintetico**: `Faker.cpf()` — sintético, nunca CPF real
- **valor_contribuicao**: uniforme entre R$ 200 e R$ 2.500
- **valor_beneficio**: uniforme entre R$ 1.000 e R$ 5.000, só para aposentado/pensionista
- **status_pagamento**: em dia 80%, atraso 15%, quitado 5%

## Simulação ano a ano

`status_atual` não é mais um sorteio único com peso global. Para cada participante, o
gerador percorre um ano civil por vez, do ingresso até a data de referência, e em cada
ano sorteia os decrementos com a taxa da **idade daquele ano**:

1. **Óbito primeiro** — probabilidade `qx(idade, sexo) × fator de seleção`, onde o qx vem
   da tábua do IBGE. Se morre, a exposição encerra ali.
2. Se continua **ativo**, na ordem: desligamento (encerra a exposição), aposentadoria (só
   se já elegível pela idade), invalidez.
3. Sem saída, o ano fecha como censura e a simulação segue.

Ano parcial (o de ingresso e o corrente) escala as taxas anuais pela fração de ano
efetivamente exposta — senão quem entrou em dezembro correria o risco do ano inteiro.

**Aposentadoria e invalidez mudam o estado mas não encerram a exposição**: quem se
aposenta continua exposto ao risco de morte dentro do plano, e continua podendo morrer
nos anos seguintes da simulação.

Por que isso importa: um qx real vai de ~0,2% aos 25 anos a ~10% aos 85. Um sorteio
único com `obito = 5%` global não tem como respeitar a idade — era a origem dos desvios
de ordem de grandeza contra as referências externas registrados no `DATASET_CARD.md`.

As linhas de `exposicao` são **subproduto** dessa simulação, não uma derivação posterior
do status já decidido. Encaixa no desenho que já existia: `exposicao` sempre foi uma
linha por ano civil.

## Dependências entre entidades (não amostradas)

- `evento` só existe para quem não é "ativo". Mapa status → tipo_evento:
  aposentado→aposentadoria, desligado→desligamento, óbito→óbito,
  pensionista→invalidez (simplificação).
- **`data_desligamento` só é preenchida para `desligado` e `obito`.** Aposentar
  não é desligar: o §3.1 define o campo como "preenchida se houver
  desligamento", e preenchê-lo para aposentados truncaria a exposição ao risco
  e enviesaria o qx para baixo.
- `exposicao`: uma linha por ano civil entre o ingresso e o fim da exposição.
  O fim é o desligamento/óbito para quem sai, e a data de referência para quem
  permanece no plano — inclusive aposentados e pensionistas, que continuam
  expostos ao risco de morte. Essas linhas saem direto da simulação.
- `idade_exata` é calculada de fato — `(data_base - data_nascimento) / 365.25`.
- `contribuicao_beneficio`: até 6 competências mensais antes do fim do vínculo.
- Um snapshot por participante (`versao_registro = 1`). Retificação bitemporal
  não é simulada nesta rodada — o schema suporta, o gerador não exercita.

## Imperfeições injetadas (§5.1)

5% dos participantes recebem uma imperfeição, com uma garantia adicional: a
primeira rodada percorre os 9 tipos uma vez cada. Com sorteio puro e poucos
alvos, algum tipo sairia com zero injeções e o precision/recall dele viraria
NaN no relatório.

| # | Tipo | O que é injetado | Tabela | Dimensão (§3.7) | Regra |
| --- | --- | --- | --- | --- | --- |
| 1 | `idade_invalida` | data_nascimento 140 anos atrás (idade > 130) | participante | validade | R01 |
| 2 | `datas_fora_ordem` | desligamento 400 dias antes do ingresso, e o evento junto | participante + evento | consistência | R02 |
| 3 | `grafia_divergente` | "Plano A" → "PLANO_A" / "plano a" / "P. A" | participante | consistência | R03 |
| 4 | `duplicidade` | mesmo CPF sintético em dois participante_id | participante | unicidade | R04 |
| 5 | `nulo` | data_nascimento ausente (SQL NULL) | participante | completude | R05 |
| 6 | `outlier` | contribuição negativa ou benefício absurdo | contribuicao_beneficio | acurácia | R06 |
| 7 | `orfao` | evento apontando para participante_id inexistente | evento | consistência | R07 |
| 8 | `atraso_anomalo` | data_conhecimento > 1 ano após data_evento | evento | temporalidade | R08 |
| 9 | `unidade_trocada` | valor em centavos, ou data em DD/MM/AAAA | contribuicao / participante | materialidade | R09 |

Notas de fidelidade ao documento:

- O §5.1 chama a dimensão do tipo 7 de "integridade referencial", mas o enum
  `dimensao_qualidade_enum` do §3.7 não tem esse valor. Mapeado para
  `consistencia`, o mais próximo dentro do conjunto fechado do documento.
- Duplicidade é modelada por CPF, não por `participante_id`: V1 tem
  `UNIQUE (participante_id, versao_registro)`, e duplicar o id derrubaria a
  promoção inteira em vez de exercitar a regra.
- `valor_injetado` é NOT NULL no gabarito, então a injeção de ausência é
  registrada com o token `<NULL>`. No dado de trabalho o campo fica NULL de
  verdade.

## As 9 regras de qualidade

O escopo exige no mínimo 5; há uma por tipo injetado, porque um tipo sem
detector apareceria como falso negativo permanente e tornaria o recall
ininterpretável.

**Rejeitam a linha** (violação dura): R01 idade fora de faixa, R04 duplicidade,
R05 campo obrigatório ausente, R07 órfão — mais falha de cast, valor fora do
domínio de um enum e valor que estouraria o DECIMAL da coluna.

**Só reduzem o score** (a linha é promovida assim mesmo): R02, R03, R06, R08,
R09. Rejeitar tudo deixaria as tabelas finais limpas demais e o dataset
perderia a função descrita no §5.

**Tratamento aplicado na promoção:** R03 normaliza a grafia da submassa para a
forma canônica; R09 converte a data não-ISO para ISO. Valor em centavos é
sinalizado mas **não** corrigido automaticamente — não há como distinguir com
segurança um valor em centavos de um valor legitimamente alto.

**Cascata:** se um participante é rejeitado, seus eventos/exposições/
contribuições também são, com o motivo `R99_pai_rejeitado`. Sem isso eles
virariam órfãos que ninguém injetou, poluindo a precisão da R07.

## Convenção do `data_quality_score.referencia_id`

O campo é livre (`VARCHAR(200)`). Sem convenção fixa a tabela fica ilegível em
poucas semanas:

| Granularidade | Formato | Exemplo |
| --- | --- | --- |
| `variavel` | `tabela.campo` | `participante.data_nascimento` |
| `participante` | UUID do participante | `9f3c…` |
| `submassa_plano` | nome da submassa | `Plano A` |
| `data_base` | data ISO (fim do ano civil) | `2024-12-31` |

O score é sempre `1 - violações/avaliadas` dentro do grupo. As regras devolvem
células (registro × campo), o que permite derivar as 4 granularidades do §3.7
com um agregador só.

## Limitações conhecidas

- Retificação bitemporal não é simulada (um snapshot por participante).
- `referencia_externa` já está populada para as 4 fontes do §1 (`versao_tabua`,
  `data_consulta` e `resultado_benchmark` preenchidos pelos scripts
  `benchmark_*.py` — ver Passo 3 no `DATASET_CARD.md`). Atenção: como
  `R__referencia_externa.sql` é uma migration repeatable que faz
  `DELETE`+`INSERT` com tudo `NULL`, reaplicá-la depois de editar o arquivo
  apaga esses resultados — rodar os `benchmark_*.py` de novo nesse caso.
- **Circularidade na validação A/E.** A mortalidade da massa é calibrada com a tábua do
  IBGE. Logo, comparar o qx dessa massa contra o **mesmo** IBGE não testa realidade
  nenhuma — testa só se a simulação reproduziu o que ela mesma recebeu como insumo. O
  `benchmark_ibge.py` continua útil como *diagnóstico* (a simulação pegou o nível certo?),
  mas **não** conta como validação. A validação independente é do Passo 5, contra a
  **BR-EMS**, que é o mesmo universo demográfico brasileiro. A SOA RP-2014 é mortalidade
  de planos de pensão americanos: resolve a circularidade, mas serve só como referência
  internacional complementar, nunca como substituto da BR-EMS.
- As taxas de desligamento, aposentadoria e invalidez são **premissa declarada**, não dado
  calibrado. Só a mortalidade tem fonte real nesta rodada.
- A calibração usa **apenas o nível** do qx, de um único ano (2024) — nenhuma tendência de
  melhoria de mortalidade é simulada. Isso é proposital: se o gerador embutisse tendência,
  o Passo 6 estaria detectando a própria premissa em vez de detectar um padrão.
- Tábua biométrica (qx/lx/dx com intervalos de confiança, §2) está fora desta
  rodada.
- O precision/recall dá 1.00 em todos os tipos porque a base sintética é limpa
  fora do que se injeta e as regras foram desenhadas para não se sobrepor. Isso
  mede que o pipeline pega exatamente o que foi plantado — **não** prevê o
  desempenho dele numa base real.
- `dicionario_dados.responsavel` está preenchido com "Tribo 3" em todos os
  campos; trocar pela dupla responsável quando o time definir.
