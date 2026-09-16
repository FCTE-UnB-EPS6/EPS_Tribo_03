"""
Passo 5 — Comparação A/E (IBGE)

Etapa do fluxo do §3 que vem logo depois das taxas brutas (... exposição
ao risco -> eventos observados -> taxas brutas -> comparação A/E ->
suavização -> ...). Por isso usa taxas_brutas_qx (observado bruto), não o
qx suavizado/credibilizado — a suavização é a etapa seguinte, ainda não
tinha acontecido nesse ponto do fluxo original.

Esta etapa NÃO estava de fato bloqueada pelo Passo 3, ao contrário do que
foi documentado antes aqui. O que bloqueava era esperar a outra dupla
rodar `benchmark_ibge.py` de novo pra popular `referencia_externa` no
banco (linha da fonte IBGE) — mas os arquivos brutos do IBGE já estão
baixados e versionados em `ambiente-de-dados/docs/referencias/` desde que
o Passo 3 foi feito. Este script lê esses arquivos direto (mesma lógica de
parsing do `ambiente-de-dados/scripts/benchmark_ibge.py`), sem depender de
nenhuma linha em `referencia_externa` estar preenchida.

Isso não substitui o trabalho do Passo 3 — aquele grava o resultado no
banco pra outras duplas consultarem via `referencia_externa`; este só
remove a dependência de esperar por aquela rodada específica pro Passo 5
seguir em frente. Lê arquivo, não código, do diretório do Passo 1 — se a
outra dupla reorganizar `docs/referencias/`, este caminho pode quebrar.

A/E = óbitos observados / óbitos esperados (qx do IBGE x exposição
observada), por idade e sexo — precisa do join com `participante.sexo`
porque `exposicao` não carrega sexo diretamente, e a Tábua do IBGE só
existe por sexo (Ambos/Homens/Mulheres), não por submassa.

Espera os mesmos arquivos que benchmark_ibge.py, em
ambiente-de-dados/docs/referencias/:
    ibge_2024_ambos.xlsx
    ibge_2024_homens.xlsx
    ibge_2024_mulheres.xlsx

Uso:
    python comparacao_ae.py
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
import csv

import pandas as pd

from db import conectar

PASTA_REFERENCIAS = (
    Path(__file__).resolve().parent.parent.parent / "ambiente-de-dados" / "docs" / "referencias"
)
PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "comparacao_ae"

ARQUIVOS_IBGE = {"Ambos": "ibge_2024_ambos.xlsx", "M": "ibge_2024_homens.xlsx", "F": "ibge_2024_mulheres.xlsx"}


def carregar_ibge(nome_arquivo):
    """Idêntico ao benchmark_ibge.py: idade (coluna A) e qx em fração
    (coluna B / 1000). Dados começam na linha 7 (skiprows=6)."""
    df = pd.read_excel(
        PASTA_REFERENCIAS / nome_arquivo,
        sheet_name=0, header=None, skiprows=6,
        usecols="A:B", names=["idade", "qx_por_mil"],
    )
    df = df.dropna(subset=["idade"])
    df["idade"] = pd.to_numeric(df["idade"], errors="coerce")
    df = df.dropna(subset=["idade"])
    df["idade"] = df["idade"].astype(int)
    df["qx"] = df["qx_por_mil"] / 1000
    return dict(zip(df["idade"], df["qx"]))


def carregar_taxas_brutas_por_sexo(cur):
    """Igual a taxas_brutas_qx.calcular_taxas_brutas(), mas por sexo em vez
    de submassa — a Tábua do IBGE não tem noção de submassa (isso é
    específico do plano fictício da Tribo 3), só de sexo."""
    cur.execute("""
        SELECT FLOOR(e.idade_exata)::int AS idade,
               p.sexo,
               COUNT(*) FILTER (WHERE e.tipo_saida = 'obito') AS obitos,
               SUM(e.tempo_exposto) AS exposicao_central
          FROM exposicao e
          JOIN participante p ON p.participante_id = e.participante_id
         GROUP BY FLOOR(e.idade_exata), p.sexo
         ORDER BY idade, sexo
    """)
    linhas = []
    for idade, sexo, obitos, exposicao in cur.fetchall():
        linhas.append({
            "idade": idade, "sexo": sexo, "obitos": obitos,
            "exposicao_central": float(exposicao) if exposicao else 0.0,
        })
    return linhas


def calcular_ae(brutas_por_sexo, ibge_por_categoria):
    """Uma linha por (idade, categoria) com atual (observado), esperado
    (qx_ibge * exposição) e razão A/E. 'categoria' é M, F ou Ambos (pool de
    M+F na mesma idade)."""
    linhas = []

    # M e F direto
    for l in brutas_por_sexo:
        qx_ibge = ibge_por_categoria[l["sexo"]].get(l["idade"])
        if qx_ibge is None or l["exposicao_central"] <= 0:
            continue
        esperado = qx_ibge * l["exposicao_central"]
        linhas.append({
            "idade": l["idade"], "categoria": l["sexo"],
            "obitos_atual": l["obitos"], "exposicao_central": round(l["exposicao_central"], 5),
            "qx_ibge": qx_ibge, "obitos_esperado": round(esperado, 5),
            "razao_ae": round(l["obitos"] / esperado, 4) if esperado > 0 else None,
        })

    # Ambos: pool de M+F por idade
    pool = defaultdict(lambda: {"obitos": 0, "exposicao_central": 0.0})
    for l in brutas_por_sexo:
        pool[l["idade"]]["obitos"] += l["obitos"]
        pool[l["idade"]]["exposicao_central"] += l["exposicao_central"]
    for idade, agregado in pool.items():
        qx_ibge = ibge_por_categoria["Ambos"].get(idade)
        if qx_ibge is None or agregado["exposicao_central"] <= 0:
            continue
        esperado = qx_ibge * agregado["exposicao_central"]
        linhas.append({
            "idade": idade, "categoria": "Ambos",
            "obitos_atual": agregado["obitos"], "exposicao_central": round(agregado["exposicao_central"], 5),
            "qx_ibge": qx_ibge, "obitos_esperado": round(esperado, 5),
            "razao_ae": round(agregado["obitos"] / esperado, 4) if esperado > 0 else None,
        })

    linhas.sort(key=lambda l: (l["categoria"], l["idade"]))
    return linhas


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "categoria", "obitos_atual", "exposicao_central",
                  "qx_ibge", "obitos_esperado", "razao_ae"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def montar_relatorio(linhas):
    texto = ["# Comparação A/E — qx observado (bruto) vs. IBGE 2024", ""]
    for categoria in ["Ambos", "M", "F"]:
        cels = [l for l in linhas if l["categoria"] == categoria]
        if not cels:
            continue
        atual_total = sum(l["obitos_atual"] for l in cels)
        esperado_total = sum(l["obitos_esperado"] for l in cels)
        razao_total = round(atual_total / esperado_total, 4) if esperado_total > 0 else None
        texto.append(f"## {categoria}")
        texto.append(f"- idades comparadas: {len(cels)}")
        texto.append(f"- óbitos observados (total): {atual_total}")
        texto.append(f"- óbitos esperados sob IBGE (total): {esperado_total:.3f}")
        if razao_total is not None:
            leitura = "mortalidade observada acima da IBGE" if razao_total > 1.1 else \
                "mortalidade observada abaixo da IBGE" if razao_total < 0.9 else \
                "mortalidade observada em linha com a IBGE"
            texto.append(f"- razão A/E geral: {razao_total} ({leitura})")
        texto.append("")
    texto.append(
        "Nota: célula por célula (idade x sexo), o A/E tende a ser instável — "
        "exposição pequena por idade numa massa de 300 participantes. A razão "
        "geral (soma dos óbitos / soma do esperado) é a leitura mais robusta; "
        "ver docs/qx_bruto/ e o teste de aderência para o comportamento por idade."
    )
    return "\n".join(texto)


def main():
    ibge_por_categoria = {cat: carregar_ibge(arq) for cat, arq in ARQUIVOS_IBGE.items()}

    conn = conectar()
    cur = conn.cursor()
    brutas_por_sexo = carregar_taxas_brutas_por_sexo(cur)
    cur.close()
    conn.close()

    if not brutas_por_sexo:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    linhas = calcular_ae(brutas_por_sexo, ibge_por_categoria)
    if not linhas:
        print("Nenhuma idade em comum entre a massa sintética e a tábua do IBGE.")
        return

    caminho_csv = PASTA_SAIDA / f"comparacao_ae_{date.today().isoformat()}.csv"
    gravar_csv(linhas, caminho_csv)

    relatorio = montar_relatorio(linhas)
    print(relatorio)

    caminho_md = PASTA_SAIDA / f"comparacao_ae_{date.today().isoformat()}.md"
    caminho_md.write_text(relatorio, encoding="utf-8")
    print(f"\nGravado em {caminho_csv} e {caminho_md}")


if __name__ == "__main__":
    main()
