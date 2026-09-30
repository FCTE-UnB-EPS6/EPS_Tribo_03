"""Parâmetros calibrados com dado público real — insumo do gerador (Passo 1).

Único lugar onde vivem os números que governam a trajetória de um
participante. Antes esses números eram pesos globais fixos no
gerar_dataset.py (ativo 55%, aposentado 20%, ..., obito 5%), que ignoravam
a idade por completo: um qx real vai de ~0,1% aos 25 anos a ~15% aos 85.

Duas categorias bem diferentes convivem aqui, e a distinção está declarada
nos docs de propósito:

  CALIBRADO  mortalidade por idade/sexo — vem da Tábua Completa de
             Mortalidade do IBGE 2024, arquivo real já versionado em
             docs/referencias/.
  PREMISSA   desligamento, aposentadoria e invalidez — constantes
             declaradas, NÃO extraídas de fonte. São ordem de grandeza
             plausível, nada mais.

Sem rede e sem banco: tudo sai de arquivo versionado no repositório, para
que "mesma seed = mesmo dataset" continue valendo (§6).
"""

from pathlib import Path

# O parser do xlsx do IBGE já existe no Passo 3 e é reusado como está --
# duplicar aqui significaria duas cópias das quirks do arquivo (dados na
# linha 7, qx em "por mil"). O import é de mão única: o Passo 1 lê o
# parser do Passo 3, o Passo 3 nunca importa o gerador.
from benchmark_ibge import PASTA_REFERENCIAS, carregar_ibge

# ---------- CALIBRADO: mortalidade ----------

VERSAO_TABUA = "IBGE — Tábua Completa de Mortalidade 2024"

ARQUIVOS_QX = {
    "M": "ibge_2024_homens.xlsx",
    "F": "ibge_2024_mulheres.xlsx",
}

# Fator de seleção declarado sobre o qx populacional do IBGE.
#
# Participante de fundo de previdência fechado tem mortalidade abaixo da
# população geral (efeito de seleção: renda, acesso a saúde, vínculo
# formal). Declarar o fator explicitamente é o que evita a circularidade
# do risco 02: se o gerador usasse o qx do IBGE cru e o Passo 5 validasse
# o A/E contra o mesmo IBGE, a comparação não testaria realidade nenhuma
# -- só testaria se o código simulou certo o que ele mesmo recebeu.
#
# É uma premissa declarada, não um fator estimado a partir de experiência
# própria. A validação independente é do Passo 5, contra a BR-EMS.
FATOR_SELECAO = 0.85

# ---------- PREMISSA: decrementos que não são mortalidade ----------
# O plano de dados reais aponta AEPS/PREVIC (aposentadoria) e RAIS/CAGED
# (desligamento) como fontes ideais. Nenhuma das duas foi extraída nesta
# rodada, então os valores abaixo ficam como premissa explícita -- não
# são dado calibrado e não devem ser citados como tal.

# Saída do PLANO, que é mais rara do que a rotatividade do emprego: o
# participante que troca de empregador muitas vezes mantém o vínculo como
# autopatrocinado ou vinculado. 8%/ano (ordem de grandeza da rotatividade
# do CAGED) esvaziaria o plano — a massa simulada virava 60% desligado e
# quase ninguém chegava à idade de aposentadoria.
TAXA_DESLIGAMENTO_ANUAL = 0.03
TAXA_INVALIDEZ_ANUAL = 0.002        # ativo -> pensionista (via invalidez)
TAXA_APOSENTADORIA_ANUAL = 0.30     # por ano, depois de elegível
IDADE_APOSENTADORIA = {"M": 65, "F": 62}


def carregar_tabua_qx():
    """Lê a tábua do IBGE e devolve {sexo: {idade: qx}}.

    Carregada uma vez por execução e passada adiante: são 2 leituras de
    xlsx, caras demais para repetir por participante.
    """
    tabua = {}
    for sexo, arquivo in ARQUIVOS_QX.items():
        caminho = PASTA_REFERENCIAS / arquivo
        if not Path(caminho).exists():
            raise FileNotFoundError(
                f"Tábua de calibração ausente: {caminho}. "
                "Os arquivos do IBGE são versionados em docs/referencias/ "
                "(ver Passo 3 no DATASET_CARD.md)."
            )
        df = carregar_ibge(arquivo)
        tabua[sexo] = dict(zip(df["idade"], df["qx"]))
        if not tabua[sexo]:
            raise ValueError(f"Tábua {arquivo} foi lida vazia — layout mudou?")
    return tabua


def qx_anual(tabua, idade, sexo):
    """Probabilidade de morte no próximo ano, já com o fator de seleção.

    Idade fora do intervalo da tábua reusa a ponta mais próxima em vez de
    falhar: a tábua do IBGE começa em 0 e termina no grupo aberto do topo,
    e um participante que ultrapasse esse topo continua exposto ao risco.
    Truncar em 0.999999 evita um qx >= 1, que tornaria a morte certa e
    quebraria a comparação A/E do Passo 5.
    """
    por_idade = tabua[sexo]
    idade = int(idade)
    if idade not in por_idade:
        idade = min(max(idade, min(por_idade)), max(por_idade))
    return min(por_idade[idade] * FATOR_SELECAO, 0.999999)


def descrever_calibracao():
    """Bloco de procedência impresso pelo gerador e colado nos docs."""
    return (
        "Calibração da massa (estrutura sintética, parâmetros reais):\n"
        f"  CALIBRADO  mortalidade qx por idade/sexo — {VERSAO_TABUA}\n"
        f"             arquivos: {', '.join(sorted(ARQUIVOS_QX.values()))}\n"
        f"             fator de seleção declarado: {FATOR_SELECAO}x o qx do IBGE\n"
        "  PREMISSA   desligamento "
        f"{TAXA_DESLIGAMENTO_ANUAL:.0%}/ano, invalidez "
        f"{TAXA_INVALIDEZ_ANUAL:.1%}/ano,\n"
        f"             aposentadoria {TAXA_APOSENTADORIA_ANUAL:.0%}/ano a partir de "
        f"{IDADE_APOSENTADORIA['M']} (M) / {IDADE_APOSENTADORIA['F']} (F) anos\n"
        "  ATENÇÃO    calibrado com IBGE — a validação A/E do Passo 5 deve usar\n"
        "             BR-EMS como referência principal, não o IBGE (circularidade)."
    )
