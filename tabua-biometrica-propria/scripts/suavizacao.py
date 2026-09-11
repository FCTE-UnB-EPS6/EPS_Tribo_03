"""
Passo 5 — Suavização (baseline)

Terceira etapa do fluxo (... → taxas brutas → comparação A/E → suavização →
...). Implementada antes da comparação A/E porque, ao contrário dela, não
depende do Passo 3 — a suavização só precisa do qx bruto que
taxas_brutas_qx.py já calcula.

Método: média móvel ponderada pela exposição central, por submassa — o
baseline mais simples dos dois sugeridos no roteiro (Whittaker-Henderson é
a alternativa mais sofisticada; só vale trocar se o teste de aderência
mostrar que a média móvel não se sustenta — ver teste_aderencia.py e o
princípio de "baseline antes de complexidade" usado nos outros passos).

Ponderar por exposição (em vez de média simples entre idades vizinhas) evita
que uma idade com exposição mínima puxe a curva tanto quanto uma com
exposição robusta.

Uso:
    python suavizacao.py
"""

from datetime import date
from pathlib import Path
import csv

from db import conectar
from taxas_brutas_qx import calcular_taxas_brutas

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "qx_suavizado"

# Janela de suavização: +-JANELA idades ao redor da idade central (5 pontos
# no total com JANELA=2). Simples e fixo de propósito — é o baseline.
JANELA = 2


def agrupar_por_submassa(linhas):
    """[{idade, submassa, obitos, exposicao_central, qx_bruto}, ...] ->
    {submassa: {idade: linha}}, só com células que têm exposição."""
    por_submassa = {}
    for linha in linhas:
        if linha["exposicao_central"] <= 0:
            continue
        por_submassa.setdefault(linha["submassa"], {})[linha["idade"]] = linha
    return por_submassa


def suavizar_submassa(dados_idade, janela=JANELA):
    """dados_idade: {idade: linha}. Devolve {idade: qx_suavizado}.

    Média de qx_bruto das idades em [idade-janela, idade+janela] presentes
    nesta submassa, ponderada por exposicao_central. Sem vizinhos válidos
    (idade isolada), mantém o qx_bruto original — não há o que suavizar.
    """
    idades = sorted(dados_idade)
    suavizado = {}
    for idade in idades:
        vizinhas = [
            dados_idade[i] for i in range(idade - janela, idade + janela + 1)
            if i in dados_idade and dados_idade[i]["qx_bruto"] is not None
        ]
        peso_total = sum(v["exposicao_central"] for v in vizinhas)
        if peso_total > 0:
            qx_suav = sum(v["qx_bruto"] * v["exposicao_central"] for v in vizinhas) / peso_total
        else:
            qx_suav = dados_idade[idade]["qx_bruto"]
        suavizado[idade] = round(qx_suav, 6) if qx_suav is not None else None
    return suavizado


def suavizar_por_submassa(linhas):
    """Ponto de entrada reaproveitado por teste_aderencia.py.

    Recebe a saída de calcular_taxas_brutas() e devolve uma lista de linhas
    com qx_bruto e qx_suavizado lado a lado, por (idade, submassa).
    """
    por_submassa = agrupar_por_submassa(linhas)
    resultado = []
    for submassa, dados_idade in por_submassa.items():
        qx_suav = suavizar_submassa(dados_idade)
        for idade, linha in sorted(dados_idade.items()):
            resultado.append({
                "idade": idade,
                "submassa": submassa,
                "obitos": linha["obitos"],
                "exposicao_central": linha["exposicao_central"],
                "qx_bruto": linha["qx_bruto"],
                "qx_suavizado": qx_suav[idade],
            })
    resultado.sort(key=lambda l: (l["submassa"], l["idade"]))
    return resultado


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "submassa", "obitos", "exposicao_central",
                  "qx_bruto", "qx_suavizado"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main():
    conn = conectar()
    cur = conn.cursor()
    brutas = calcular_taxas_brutas(cur)
    cur.close()
    conn.close()

    if not brutas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    resultado = suavizar_por_submassa(brutas)

    caminho = PASTA_SAIDA / f"qx_suavizado_{date.today().isoformat()}.csv"
    gravar_csv(resultado, caminho)

    print(f"{len(resultado)} células suavizadas (janela +-{JANELA} anos, "
          f"ponderada por exposição).")
    print(f"Gravado em {caminho}")
    print("Rode teste_aderencia.py em seguida para validar o ajuste.")


if __name__ == "__main__":
    main()
