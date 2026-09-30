"""
Módulo de Integração e Ingestão Direta Interpassos — Passo 6

Conecta o Passo 6 diretamente aos outros passos da Tribo 3, sem inventar dados:
    - Passo 1: série histórica real do IBGE (2015-2024, via
               extrator_ibge_historico.py) como challenger nacional; a
               tabela `exposicao` no PostgreSQL só entra como último
               recurso estrutural (ver nota em carregar_historico_mortalidade).
    - Passo 3: Ingestão da planilha de referência oficial HMD (Austrália)
               em `ambiente-de-dados/docs/referencias/` -- challenger
               internacional.
    - Passo 4: Ingestão de premissas e regras de cenários em
               `cenarios-economicos/config/` (horizonte e choques).
    - Passo 5: Ingestão da tábua própria credibilizada em
               `tabua-biometrica-propria/docs/tabua_propria/`.

ATUALIZADO nesta rodada: a prioridade de `carregar_historico_mortalidade()`
mudou. Antes, a tabela `exposicao` do Postgres vinha primeiro. Isso é
metodologicamente errado desde que o Passo 1 passou a calibrar a massa
sintética com uma ÚNICA tábua (IBGE 2024, sem variação ano a ano -- ver
`ambiente-de-dados/scripts/calibracao.py`): não existe tendência real
nenhuma dentro da massa sintética, então qualquer "queda de mortalidade"
que o Mann-Kendall ou o Lee-Carter detectassem ali seria ruído amostral,
não sinal real -- o oposto do que este Passo 6 precisa testar. A série
histórica real do IBGE (nova, `extrator_ibge_historico.py` do Passo 1)
agora é a prioridade 1; o Postgres vira último recurso, só para não
travar testes estruturais quando nem IBGE nem HMD estiverem disponíveis,
e o rótulo de origem devolvido avisa explicitamente da limitação.
"""

import csv
import json
import math
from pathlib import Path
import sys
import pandas as pd

# Adiciona scripts/ ao sys.path para imports limpos tanto standalone quanto em pacote
PASTA_SCRIPTS = Path(__file__).resolve().parents[1]
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

# Raízes relativas do workspace (sem tocar em pastas fora de tabuas-geracionais-improvement)
RAIZ_PROJETO = Path(__file__).resolve().parents[3]
PASTA_PASSO1_REFS = RAIZ_PROJETO / "ambiente-de-dados" / "docs" / "referencias"
PASTA_PASSO4_CONFIG = RAIZ_PROJETO / "cenarios-economicos" / "config"
PASTA_PASSO5_DOCS = RAIZ_PROJETO / "tabua-biometrica-propria" / "docs" / "tabua_propria"

ARQUIVO_IBGE_HISTORICO = PASTA_PASSO1_REFS / "ibge_historico" / "serie_historica_qx.csv"

# Radix de exposição para converter qx pronto (IBGE) em obitos/exposição
# "central" comparáveis aos outros dois caminhos -- mesma convenção que o
# caminho do HMD já usa com a coluna Lx (radix de 100 mil).
RADIX_EXPOSICAO_IBGE = 100_000

try:
    from dados.db import conectar
except ImportError:
    from .db import conectar


def _carregar_ibge_historico(idades_alvo):
    """Série histórica real do IBGE (2015-2024), gerada por
    `ambiente-de-dados/scripts/extrator_ibge_historico.py`. Challenger
    nacional: mesma fonte que calibra o Passo 1, mas em série (tendência
    ano a ano), nunca o nível único usado para simular a massa -- não é
    circular pelo mesmo motivo que o Risco 02 do plano de dados reais
    resolve para o Passo 5 (fonte de nível != fonte de tendência).

    qx já vem pronto por ano/idade; obitos/exposição são derivados com um
    radix de 100 mil (mesma convenção do caminho HMD) só para os demais
    módulos (que recalculam mx = obitos/exposição) terem os mesmos campos.
    """
    if not ARQUIVO_IBGE_HISTORICO.exists():
        return None

    df = pd.read_csv(ARQUIVO_IBGE_HISTORICO)
    df = df[(df["sexo"] == "Ambos") & (df["idade"].isin(idades_alvo))]
    if df.empty:
        return None

    linhas = []
    for _, row in df.iterrows():
        qx = min(float(row["qx"]), 0.999999)
        mx = -math.log(1.0 - qx) if qx < 1.0 else 20.0
        obitos = round(qx * RADIX_EXPOSICAO_IBGE)
        linhas.append({
            "ano": int(row["ano"]),
            "idade": int(row["idade"]),
            "obitos": obitos,
            "linhas_exposicao": RADIX_EXPOSICAO_IBGE,
            "exposicao_central": float(RADIX_EXPOSICAO_IBGE),
            "mx": round(mx, 7),
            "qx": round(qx, 7),
        })
    return linhas


def _carregar_hmd_historico(idades_alvo):
    """Planilha real do HMD (Austrália) -- challenger internacional,
    últimos 10 anos disponíveis da série (2012-2021)."""
    arquivo_hmd = PASTA_PASSO1_REFS / "hmd_australia_ambos_1x1.txt"
    if not arquivo_hmd.exists():
        return None, None

    df = pd.read_csv(arquivo_hmd, sep=r"\s+", skiprows=1)
    df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    df = df.dropna(subset=["Age"])
    df["Age"] = df["Age"].astype(int)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype(int)

    anos_hmd = sorted(df["Year"].unique())[-10:]
    df_recorte = df[
        (df["Year"].isin(anos_hmd)) &
        (df["Age"].isin(idades_alvo))
    ].copy()

    linhas = []
    for _, row in df_recorte.iterrows():
        ano = int(row["Year"])
        idade = int(row["Age"])
        qx = float(row["qx"])
        mx = float(row["mx"])
        obitos = int(round(float(row.get("dx", 0))))
        exposicao = float(row.get("Lx", 100000.0))
        linhas.append({
            "ano": ano,
            "idade": idade,
            "obitos": obitos,
            "linhas_exposicao": int(exposicao),
            "exposicao_central": round(exposicao, 2),
            "mx": round(mx, 7),
            "qx": round(qx, 7),
        })
    return linhas, (anos_hmd[0], anos_hmd[-1])


def _carregar_postgres_historico():
    """Último recurso: tabela `exposicao` do Passo 1 (massa sintética).

    ATENÇÃO -- não é uma série histórica de verdade: o Passo 1 calibra
    com uma tábua ÚNICA (ver `ambiente-de-dados/scripts/calibracao.py`),
    sem variação ano a ano, então qualquer tendência que o Mann-Kendall
    ou o Lee-Carter detectarem aqui é ruído amostral do sorteio, não
    mortality improvement real. Só entra se IBGE e HMD não estiverem
    disponíveis, e o rótulo de origem devolvido por
    `carregar_historico_mortalidade()` avisa disso explicitamente -- não
    deve ser citado como evidência de tendência em nenhum relatório.
    """
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT ano_calendario,
                   FLOOR(idade_exata)::int AS idade,
                   COUNT(*) FILTER (WHERE tipo_saida = 'obito') AS obitos,
                   COUNT(*) AS linhas_exposicao,
                   SUM(tempo_exposto) AS exposicao_central
              FROM exposicao
             GROUP BY ano_calendario, FLOOR(idade_exata)
            HAVING SUM(tempo_exposto) > 0
             ORDER BY ano_calendario, idade
        """)
        linhas_db = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return None

    if not linhas_db or len(linhas_db) < 10:
        return None

    linhas = []
    for ano, idade, obitos, linhas_exp, exposicao in linhas_db:
        exp_c = float(exposicao) if exposicao else 0.0
        mx = (obitos / exp_c) if exp_c > 0 else 0.0
        qx = 1.0 - math.exp(-mx) if mx < 1.0 else 0.999
        linhas.append({
            "ano": int(ano),
            "idade": int(idade),
            "obitos": int(obitos),
            "linhas_exposicao": int(linhas_exp),
            "exposicao_central": round(exp_c, 5),
            "mx": round(mx, 7),
            "qx": round(qx, 7),
        })
    return linhas


def carregar_historico_mortalidade(idades_alvo=range(20, 71)):
    """Carrega a série histórica de mortalidade (idade x ano).

    Prioridade 1: série histórica real do IBGE (Passo 1, 2015-2024) --
                 challenger nacional, é dado real com tendência real.
    Prioridade 2: planilha real do HMD (Austrália) -- challenger
                 internacional, é dado real com tendência real.
    Prioridade 3 (ÚLTIMO RECURSO, sem tendência real -- ver
                 `_carregar_postgres_historico`): tabela `exposicao` do
                 Postgres.
    """
    linhas_ibge = _carregar_ibge_historico(idades_alvo)
    if linhas_ibge:
        anos = sorted({l["ano"] for l in linhas_ibge})
        return linhas_ibge, (
            f"Passo 1 — IBGE real, série histórica "
            f"({ARQUIVO_IBGE_HISTORICO.name}, {anos[0]}-{anos[-1]})"
        )

    linhas_hmd, periodo_hmd = _carregar_hmd_historico(idades_alvo)
    if linhas_hmd:
        return linhas_hmd, (
            f"Passo 3 — Planilha de Referência HMD "
            f"(hmd_australia_ambos_1x1.txt, {periodo_hmd[0]}-{periodo_hmd[1]})"
        )

    linhas_pg = _carregar_postgres_historico()
    if linhas_pg:
        return linhas_pg, (
            "Passo 1 — PostgreSQL (tabela exposicao) [ATENÇÃO: sem "
            "tendência real -- calibração usa tábua única, ver "
            "calibracao.py; não citar como evidência de mortality "
            "improvement]"
        )

    raise FileNotFoundError(
        "Não foi possível encontrar a série histórica do IBGE "
        f"({ARQUIVO_IBGE_HISTORICO}), a planilha HMD (Passo 3) nem dados "
        "no Postgres (Passo 1)."
    )


def carregar_tabua_base_passo5():
    """Carrega a tábua própria credibilizada (qx base) do Passo 5.

    Prioridade 1: CSV consolidado em `tabua-biometrica-propria/docs/tabua_propria/`.
    Prioridade 2: Planilha oficial IBGE 2024 em `ambiente-de-dados/docs/referencias/ibge_2024_ambos.xlsx`
                 (a mesma utilizada pelo Passo 5 para cálculo e benchmark).
    """
    # 1. Tentar ler CSV gerado pelo Passo 5
    arquivos_passo5 = sorted(PASTA_PASSO5_DOCS.glob("tabua_propria_*.csv"))
    if arquivos_passo5:
        ultimo_csv = arquivos_passo5[-1]
        tabua_base = {}
        with open(ultimo_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                idade = int(row["idade"])
                qx = float(row["qx_credibilizado"]) if row.get("qx_credibilizado") else float(row["qx_suavizado"])
                tabua_base[idade] = qx
        return tabua_base, f"Passo 5 — Tábua Própria ({ultimo_csv.name})"

    # 2. Ingestão da Planilha de Referência IBGE 2024 (Passo 3/5)
    arquivo_ibge = PASTA_PASSO1_REFS / "ibge_2024_ambos.xlsx"
    if arquivo_ibge.exists():
        df = pd.read_excel(arquivo_ibge, sheet_name=0, skiprows=6, usecols=[0, 1], header=None)
        df.columns = ["idade", "qx_milhar"]
        df["idade"] = pd.to_numeric(df["idade"], errors="coerce")
        df = df.dropna(subset=["idade"])
        df["idade"] = df["idade"].astype(int)
        df["qx"] = df["qx_milhar"] / 1000.0
        tabua_base = dict(zip(df["idade"], df["qx"]))
        return tabua_base, f"Passo 3/5 — Planilha Oficial IBGE 2024 ({arquivo_ibge.name})"

    raise FileNotFoundError("Não foi encontrada a tábua própria do Passo 5 nem a planilha do IBGE do Passo 3.")


def carregar_premissas_passo4():
    """Carrega parâmetros macroeconômicos e horizonte de projeção do Passo 4."""
    arquivo_assumptions = PASTA_PASSO4_CONFIG / "assumptions.demo.v0.1.0.json"

    horizonte_padrao = 30
    cenarios = {"base": 1.0, "adverso": 1.2, "favoravel": 0.85}

    if arquivo_assumptions.exists():
        with open(arquivo_assumptions, "r", encoding="utf-8") as f:
            data = json.load(f)
            desconto = data.get("assumptions", {}).get("discount_rate", 0.08)
    else:
        desconto = 0.08

    return {
        "horizonte_anos": horizonte_padrao,
        "taxa_desconto_passo4": desconto,
        "fatores_choque_cenarios": cenarios,
        "origem": "Passo 4 — Cenários Econômicos (assumptions & rules)",
    }
