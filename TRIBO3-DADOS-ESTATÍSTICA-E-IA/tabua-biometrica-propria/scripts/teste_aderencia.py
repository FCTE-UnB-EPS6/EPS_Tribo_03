"""
Passo 5 — Teste de aderência da suavização (Qui-quadrado)

Exigência do §3/§8 (DoD): validar se a curva suavizada do qx ainda se
ajusta plausivelmente aos dados observados, não só suavizar e seguir em
frente. Dos três testes sugeridos no roteiro (KS, Anderson-Darling,
Qui-quadrado), usa Qui-quadrado por ser o padrão atuarial pra comparar
óbitos observados vs. esperados por célula de exposição — os outros dois
comparam distribuições contínuas, e aqui o dado já vem discretizado em
células (idade x submassa).

H0: o qx suavizado descreve bem a mortalidade observada.
Estatística: soma, célula a célula, de (observado - esperado)^2 / esperado,
onde esperado = qx_suavizado * exposicao_central.

Células com esperado < 1 óbito são agrupadas (pooling) dentro de cada
submassa antes do teste — premissa padrão do qui-quadrado, senão o p-valor
fica instável nas idades com pouca exposição (a massa sintética é pequena,
300 participantes por padrão).

Uso:
    python teste_aderencia.py
"""

from collections import defaultdict
from datetime import date
from pathlib import Path

from scipy.stats import chi2

from db import conectar
from taxas_brutas_qx import calcular_taxas_brutas
from suavizacao import suavizar_por_submassa

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "teste_aderencia"
LIMIAR_ESPERADO = 1.0  # óbitos esperados mínimos por célula antes de agrupar
ALPHA = 0.05


def montar_celulas(linhas_suavizadas, limiar=LIMIAR_ESPERADO):
    """Uma célula (O, E) por idade elegível, mais um pool de idades com
    esperado baixo, tudo agrupado por submassa."""
    por_submassa = defaultdict(list)
    for l in linhas_suavizadas:
        if l["qx_suavizado"] is None or l["exposicao_central"] <= 0:
            continue
        esperado = l["qx_suavizado"] * l["exposicao_central"]
        por_submassa[l["submassa"]].append({
            "idade": l["idade"], "obs": l["obitos"], "esp": esperado,
        })

    celulas_por_submassa = {}
    for submassa, cels in por_submassa.items():
        grandes = [c for c in cels if c["esp"] >= limiar]
        pequenas = [c for c in cels if c["esp"] < limiar]
        linhas_teste = [
            {"rotulo": f"idade {c['idade']}", "obs": c["obs"], "esp": c["esp"]}
            for c in grandes
        ]
        if pequenas:
            esp_pool = sum(c["esp"] for c in pequenas)
            if esp_pool > 0:
                linhas_teste.append({
                    "rotulo": f"pool ({len(pequenas)} idades, esperado < {limiar})",
                    "obs": sum(c["obs"] for c in pequenas),
                    "esp": esp_pool,
                })
        celulas_por_submassa[submassa] = linhas_teste
    return celulas_por_submassa


def qui_quadrado(celulas):
    """(estatistica, graus_de_liberdade, p_valor) para uma lista de células
    {obs, esp}. df = n_celulas - 1 (um grau perdido por ajustar a curva aos
    mesmos dados que geram o total observado)."""
    estatistica = sum((c["obs"] - c["esp"]) ** 2 / c["esp"] for c in celulas if c["esp"] > 0)
    df = len(celulas) - 1
    if df <= 0:
        return estatistica, df, None
    p_valor = float(chi2.sf(estatistica, df))
    return estatistica, df, p_valor


def montar_relatorio(celulas_por_submassa):
    linhas_relatorio = ["# Teste de aderência — qx suavizado vs. observado (Qui-quadrado)", ""]
    stat_total, df_total = 0.0, 0

    for submassa in sorted(celulas_por_submassa):
        celulas = celulas_por_submassa[submassa]
        linhas_relatorio.append(f"## {submassa}")
        if not celulas:
            linhas_relatorio.append("- sem células com esperado > 0 — exposição insuficiente "
                                     "nesta submassa para o teste.")
            linhas_relatorio.append("")
            continue
        estatistica, df, p_valor = qui_quadrado(celulas)
        linhas_relatorio.append(f"- células no teste (pós-pooling): {len(celulas)}")
        linhas_relatorio.append(f"- estatística qui-quadrado: {estatistica:.4f}")
        linhas_relatorio.append(f"- graus de liberdade: {df}")
        if p_valor is None:
            linhas_relatorio.append("- p-valor: não calculável (menos de 2 células após pooling — "
                                     "submassa com exposição insuficiente para este teste)")
        else:
            veredito = "aderência plausível (H0 não rejeitada)" if p_valor >= ALPHA \
                else "aderência rejeitada — revisar a suavização"
            linhas_relatorio.append(f"- p-valor: {p_valor:.4f} (alpha={ALPHA}) -> {veredito}")
            stat_total += estatistica
            df_total += df
        linhas_relatorio.append("")

    if df_total > 0:
        p_valor_total = float(chi2.sf(stat_total, df_total))
        veredito = "aderência plausível (H0 não rejeitada)" if p_valor_total >= ALPHA \
            else "aderência rejeitada — revisar a suavização"
        linhas_relatorio.append("## Geral (soma das estatísticas independentes por submassa)")
        linhas_relatorio.append(f"- estatística qui-quadrado: {stat_total:.4f}")
        linhas_relatorio.append(f"- graus de liberdade: {df_total}")
        linhas_relatorio.append(f"- p-valor: {p_valor_total:.4f} (alpha={ALPHA}) -> {veredito}")

    return "\n".join(linhas_relatorio)


def main():
    conn = conectar()
    cur = conn.cursor()
    brutas = calcular_taxas_brutas(cur)
    cur.close()
    conn.close()

    if not brutas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    suavizadas = suavizar_por_submassa(brutas)
    celulas_por_submassa = montar_celulas(suavizadas)
    relatorio = montar_relatorio(celulas_por_submassa)

    print(relatorio)

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_SAIDA / f"teste_aderencia_{date.today().isoformat()}.md"
    caminho.write_text(relatorio, encoding="utf-8")
    print(f"\nGravado em {caminho}")


if __name__ == "__main__":
    main()
