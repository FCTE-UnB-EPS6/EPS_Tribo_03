-- ============================================================
-- Repeatable: esqueleto da referencia_externa (§3.5)
-- ============================================================
-- As 4 fontes do §1 do documento, com o escopo de comparação copiado
-- literalmente da coluna "Uso pretendido na Tribo 3" da tabela do §1.
--
-- versao_tabua, data_consulta e resultado_benchmark ficam NULL de
-- propósito: só existem depois que alguém de fato baixar a tábua e
-- rodar o benchmark. Nada aqui é inventado.
--
-- Repeatable porque este é um catálogo curado à mão que o time vai
-- completar conforme os benchmarks forem executados.
--
-- ATENÇÃO: esta tabela nunca é fonte de linhas do dataset de entrada
-- (§4, último bullet) — serve só para registrar a comparação
-- metodológica.
--
-- ATENÇÃO 2: depois que os scripts scripts/benchmark_*.py rodarem e
-- preencherem versao_tabua/data_consulta/resultado_benchmark, NÃO editar
-- este arquivo sem necessidade — por ser repeatable, o Flyway reexecuta o
-- DELETE+INSERT abaixo (tudo NULL de novo) sempre que o checksum mudar,
-- apagando os resultados do Passo 3. Se precisar editar, rodar os
-- benchmark_*.py de novo em seguida.

DELETE FROM referencia_externa;

INSERT INTO referencia_externa
    (fonte, versao_tabua, escopo_comparacao, data_consulta, resultado_benchmark)
VALUES
('IBGE', NULL,
 'Tábuas de mortalidade da população brasileira geral, usadas como baseline demográfico e para checar plausibilidade das taxas qx sintéticas.',
 NULL, NULL),
('HMD', NULL,
 'Séries históricas de mortalidade de diversos países, usadas como referência para tendências e mortality improvement (base para comparação com Lee-Carter/CBD).',
 NULL, NULL),
('BR_EMS', NULL,
 'Tábuas biométricas do mercado segurador/previdenciário brasileiro (SUSEP/FenaPrevi), usadas como baseline específico do setor de previdência complementar.',
 NULL, NULL),
('SOA', NULL,
 'Tábuas e estudos de experiência atuarial internacionais, usados como referência metodológica adicional (quando aplicável ao contexto).',
 NULL, NULL);
