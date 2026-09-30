"""
Passo 5 — Comparação A/E (BR-EMS como referência principal)

Etapa do fluxo do §3 que vem logo depois das taxas brutas (... exposição
ao risco -> eventos observados -> taxas brutas -> comparação A/E ->
suavização -> ...). Por isso usa taxas_brutas_qx (observado bruto), não o
qx suavizado/credibilizado — a suavização é a etapa seguinte, ainda não
tinha acontecido nesse ponto do fluxo original.

MUDANÇA DESTA RODADA (Risco 02 do plano de dados reais): o Passo 1
(`ambiente-de-dados/scripts/gerar_dataset.py`) passou a calibrar a
mortalidade sintética com o qx da Tábua Completa do IBGE 2024. A partir
daí, validar o A/E contra o mesmo IBGE deixou de testar realidade — vira
um teste de que o código simulou certo o que ele mesmo recebeu como
insumo. A referência PRINCIPAL deste script agora é a BR-EMS (mesmo
universo demográfico brasileiro, mas fonte independente da calibração).
O IBGE continua calculado e no relatório, mas só como DIAGNÓSTICO
secundário — explicitamente rotulado, nunca mais como validação.

BR-EMS não publica tábua para "Ambos os sexos" (só -m e -f); por isso a
categoria Ambos só existe no diagnóstico IBGE, não no A/E principal — ver
nota no relatório.

Fontes lidas direto de arquivo (mesma lógica de parsing dos scripts do
Passo 3: `ambiente-de-dados/scripts/benchmark_brems.py` e
`benchmark_ibge.py`), sem depender de `referencia_externa` estar
preenchida no banco — só acopla ao caminho dos arquivos em
`ambiente-de-dados/docs/referencias/`, que já são versionados.

A/E = óbitos observados / óbitos esperados (qx da referência x exposição
observada), por idade e sexo — precisa do join com `participante.sexo`
porque `exposicao` não carrega sexo diretamente.

Espera em ambiente-de-dados/docs/referencias/:
    br_ems_2026_sobrevivencia.xlsx  (abas BR-EMSsb-2026-m / -f) — PRINCIPAL
    ibge_2024_ambos.xlsx, ibge_2024_homens.xlsx, ibge_2024_mulheres.xlsx — DIAGNÓSTICO

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

ARQUIVO_BREMS = PASTA_REFERENCIAS / "br_ems_2026_sobrevivencia.xlsx"
ABAS_BREMS = {"M": "BR-EMSsb-2026-m", "F": "BR-EMSsb-2026-f"}


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


def carregar_brems(aba):
    """Idêntico a benchmark_brems.py: qx já vem como probabilidade direta
    (não "por mil"), a partir da linha 3 (skiprows=2)."""
    df = pd.read_excel(
        ARQUIVO_BREMS, sheet_name=aba, header=None, skiprows=2,
        usecols="A:B", names=["idade", "qx"],
    )
    df["idade"] = pd.to_numeric(df["idade"], errors="coerce")
    df = df.dropna(subset=["idade"])
    df["idade"] = df["idade"].astype(int)
    return dict(zip(df["idade"], df["qx"]))


def carregar_taxas_brutas_por_sexo(cur):
    """Igual a taxas_brutas_qx.calcular_taxas_brutas(), mas por sexo em vez
    de submassa — as referências externas não têm noção de submassa (isso
    é específico do plano fictício da Tribo 3), só de sexo."""
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


def _esperado(qx_tabua, idade, exposicao_central):
    qx = qx_tabua.get(idade)
    if qx is None or exposicao_central <= 0:
        return None, None
    return qx, qx * exposicao_central


def calcular_ae(brutas_por_sexo, brems_por_sexo, ibge_por_categoria):
    """Uma linha por (idade, categoria) com o observado e o esperado sob
    as duas referências: BR-EMS (principal, razao_ae_brems) e IBGE
    (diagnóstico, razao_ae_ibge — mesma fonte que calibrou o Passo 1,
    não serve como validação, ver docstring do módulo).

    'categoria' é M ou F (BR-EMS não tem Ambos) mais Ambos só para o
    diagnóstico IBGE.
    """
    linhas = []

    for l in brutas_por_sexo:
        sexo, idade, obitos, exp = l["sexo"], l["idade"], l["obitos"], l["exposicao_central"]
        qx_brems, esperado_brems = _esperado(brems_por_sexo.get(sexo, {}), idade, exp)
        qx_ibge, esperado_ibge = _esperado(ibge_por_categoria[sexo], idade, exp)
        if esperado_brems is None and esperado_ibge is None:
            continue
        linhas.append({
            "idade": idade, "categoria": sexo,
            "obitos_atual": obitos, "exposicao_central": round(exp, 5),
            "qx_brems": qx_brems,
            "obitos_esperado_brems": round(esperado_brems, 5) if esperado_brems is not None else None,
            "razao_ae_brems": round(obitos / esperado_brems, 4) if esperado_brems else None,
            "qx_ibge": qx_ibge,
            "obitos_esperado_ibge": round(esperado_ibge, 5) if esperado_ibge is not None else None,
            "razao_ae_ibge_diagnostico": round(obitos / esperado_ibge, 4) if esperado_ibge else None,
        })

    # Ambos: pool de M+F por idade -- só contra IBGE, BR-EMS não publica
    # tábua combinada (ver docstring).
    pool = defaultdict(lambda: {"obitos": 0, "exposicao_central": 0.0})
    for l in brutas_por_sexo:
        pool[l["idade"]]["obitos"] += l["obitos"]
        pool[l["idade"]]["exposicao_central"] += l["exposicao_central"]
    for idade, agregado in pool.items():
        qx_ibge, esperado_ibge = _esperado(ibge_por_categoria["Ambos"], idade, agregado["exposicao_central"])
        if esperado_ibge is None:
            continue
        linhas.append({
            "idade": idade, "categoria": "Ambos",
            "obitos_atual": agregado["obitos"], "exposicao_central": round(agregado["exposicao_central"], 5),
            "qx_brems": None, "obitos_esperado_brems": None, "razao_ae_brems": None,
            "qx_ibge": qx_ibge, "obitos_esperado_ibge": round(esperado_ibge, 5),
            "razao_ae_ibge_diagnostico": round(agregado["obitos"] / esperado_ibge, 4) if esperado_ibge else None,
        })

    linhas.sort(key=lambda l: (l["categoria"], l["idade"]))
    return linhas


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "categoria", "obitos_atual", "exposicao_central",
                  "qx_brems", "obitos_esperado_brems", "razao_ae_brems",
                  "qx_ibge", "obitos_esperado_ibge", "razao_ae_ibge_diagnostico"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def _leitura(razao):
    if razao is None:
        return "sem dado"
    if razao > 1.1:
        return "observada acima da referência"
    if razao < 0.9:
        return "observada abaixo da referência"
    return "observada em linha com a referência"


def montar_relatorio(linhas):
    texto = [
        "# Comparação A/E — qx observado (bruto) vs. BR-EMS (principal) e IBGE (diagnóstico)",
        "",
        "BR-EMS é a validação independente: o Passo 1 calibra a massa sintética "
        "com o qx do IBGE, então comparar A/E contra o próprio IBGE não testaria "
        "realidade (Risco 02 do plano de dados reais). O bloco IBGE abaixo é "
        "mantido só como diagnóstico e está rotulado como tal — não use a razão "
        "A/E do IBGE como evidência de que a tábua própria é boa.",
        "",
    ]

    texto.append("## BR-EMS (principal) — só M e F, BR-EMS não publica tábua combinada")
    for categoria in ["M", "F"]:
        cels = [l for l in linhas if l["categoria"] == categoria and l["razao_ae_brems"] is not None]
        if not cels:
            texto.append(f"- {categoria}: sem células com BR-EMS disponível.")
            continue
        atual_total = sum(l["obitos_atual"] for l in cels)
        esperado_total = sum(l["obitos_esperado_brems"] for l in cels)
        razao_total = round(atual_total / esperado_total, 4) if esperado_total > 0 else None
        texto.append(f"### {categoria}")
        texto.append(f"- idades comparadas: {len(cels)}")
        texto.append(f"- óbitos observados (total): {atual_total}")
        texto.append(f"- óbitos esperados sob BR-EMS (total): {esperado_total:.3f}")
        if razao_total is not None:
            texto.append(f"- razão A/E geral (BR-EMS): {razao_total} ({_leitura(razao_total)})")
        texto.append("")

    texto.append("## IBGE (diagnóstico — NÃO é validação, mesma fonte da calibração)")
    for categoria in ["Ambos", "M", "F"]:
        cels = [l for l in linhas if l["categoria"] == categoria and l["razao_ae_ibge_diagnostico"] is not None]
        if not cels:
            continue
        atual_total = sum(l["obitos_atual"] for l in cels)
        esperado_total = sum(l["obitos_esperado_ibge"] for l in cels)
        razao_total = round(atual_total / esperado_total, 4) if esperado_total > 0 else None
        texto.append(f"### {categoria}")
        texto.append(f"- idades comparadas: {len(cels)}")
        texto.append(f"- óbitos observados (total): {atual_total}")
        texto.append(f"- óbitos esperados sob IBGE (total): {esperado_total:.3f}")
        if razao_total is not None:
            texto.append(f"- razão A/E geral (IBGE, diagnóstico): {razao_total} "
                         f"— esperado ficar perto de 1,0x, já que é a mesma fonte "
                         "que calibrou a massa; desvio aqui indica bug na "
                         "simulação, não realismo.")
        texto.append("")

    texto.append(
        "Nota: célula por célula (idade x sexo), o A/E tende a ser instável — "
        "exposição pequena por idade. A razão geral (soma dos óbitos / soma do "
        "esperado) é a leitura mais robusta; ver docs/qx_bruto/ e o teste de "
        "aderência para o comportamento por idade."
    )
    return "\n".join(texto)


def main():
    brems_por_sexo = {sexo: carregar_brems(aba) for sexo, aba in ABAS_BREMS.items()}
    ibge_por_categoria = {cat: carregar_ibge(arq) for cat, arq in ARQUIVOS_IBGE.items()}

    conn = conectar()
    cur = conn.cursor()
    brutas_por_sexo = carregar_taxas_brutas_por_sexo(cur)
    cur.close()
    conn.close()

    if not brutas_por_sexo:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    linhas = calcular_ae(brutas_por_sexo, brems_por_sexo, ibge_por_categoria)
    if not linhas:
        print("Nenhuma idade em comum entre a massa sintética e as referências externas.")
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
