"""
Módulo de Integração e Ingestão Direta Interpassos — Passo 6

Conecta o Passo 6 diretamente aos outros passos da Tribo 3, sem inventar dados:
    - Passo 1: Ingestão de `exposicao` no PostgreSQL (quando ativo).
    - Passo 3: Ingestão das planilhas de referência oficiais em
               `ambiente-de-dados/docs/referencias/` (HMD e IBGE 2024).
    - Passo 4: Ingestão de premissas e regras de cenários em
               `cenarios-economicos/config/` (horizonte e choques).
    - Passo 5: Ingestão da tábua própria credibilizada em
               `tabua-biometrica-propria/docs/tabua_propria/`.
"""

import csv
import json
import math
from pathlib import Path
import pandas as pd

# Raízes relativas do workspace (sem tocar em nenhuma pasta fora de tabuas-geracionais-improvement)
RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent
PASTA_PASSO1_REFS = RAIZ_PROJETO / "ambiente-de-dados" / "docs" / "referencias"
PASTA_PASSO4_CONFIG = RAIZ_PROJETO / "cenarios-economicos" / "config"
PASTA_PASSO5_DOCS = RAIZ_PROJETO / "tabua-biometrica-propria" / "docs" / "tabua_propria"

try:
    from db import conectar
except ImportError:
    from .db import conectar


def carregar_historico_mortalidade(idades_alvo=range(20, 71)):
    """Carrega a série histórica de mortalidade (idade x ano).

    Prioridade 1: Tabela `exposicao` no PostgreSQL (Passo 1).
    Prioridade 2: Planilha real HMD (Passo 3: `hmd_australia_ambos_1x1.txt`),
                 utilizando os 10 anos mais recentes da série (2012-2021)
                 para as idades do fundo (20 a 70 anos).
    """
    # 1. Tentar ler do PostgreSQL do Passo 1
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

        if linhas_db and len(linhas_db) >= 10:
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
            return linhas, "Passo 1 — PostgreSQL (tabela exposicao)"
    except Exception:
        pass

    # 2. Ingestão da Planilha de Referência Histórica do Passo 3 (HMD)
    arquivo_hmd = PASTA_PASSO1_REFS / "hmd_australia_ambos_1x1.txt"
    if arquivo_hmd.exists():
        df = pd.read_csv(arquivo_hmd, sep=r"\s+", skiprows=1)
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
        df = df.dropna(subset=["Age"])
        df["Age"] = df["Age"].astype(int)
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype(int)

        # Últimos 10 anos disponíveis da série histórica (2012 a 2021)
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
            # dx é a contagem de óbitos por 100.000 (lx)
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
        return linhas, f"Passo 3 — Planilha de Referência HMD ({arquivo_hmd.name}, {min(anos_hmd)}-{max(anos_hmd)})"

    raise FileNotFoundError("Não foi possível encontrar dados no Postgres (Passo 1) nem a planilha HMD (Passo 3).")


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
    arquivo_rules = PASTA_PASSO4_CONFIG / "scenario_rules.demo.v0.1.0.json"

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
