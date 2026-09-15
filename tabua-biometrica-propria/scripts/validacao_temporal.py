"""
Passo 5 — Validação temporal (holdout por ano_calendario)

`exposicao.ano_calendario` já existe (uma linha por ano civil de exposição,
conforme regras_geracao.md) — não precisou criar nada novo. Separa o ano
mais recente como holdout, ajusta o qx suavizado só com os anos anteriores
(treino) e testa se ele ainda explica os óbitos observados no ano de fora
— mesma lógica de qui-quadrado do teste_aderencia.py, só que comparando
períodos diferentes em vez do mesmo período.

Uso:
    python validacao_temporal.py
"""

from datetime import date
from pathlib import Path

from db import conectar
from suavizacao import suavizar_por_submassa
from teste_aderencia import montar_celulas, qui_quadrado, ALPHA

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "validacao_temporal"


def carregar_por_ano(cur):
    """Uma linha por (ano_calendario, idade, submassa)."""
    cur.execute("""
        SELECT ano_calendario,
               FLOOR(idade_exata)::int AS idade,
               submassa,
               COUNT(*) FILTER (WHERE tipo_saida = 'obito') AS obitos,
               SUM(tempo_exposto) AS exposicao_central
          FROM exposicao
         GROUP BY ano_calendario, FLOOR(idade_exata), submassa
         ORDER BY ano_calendario, idade, submassa
    """)
    linhas = []
    for ano, idade, submassa, obitos, exposicao in cur.fetchall():
        linhas.append({
            "ano_calendario": ano, "idade": idade, "submassa": submassa,
            "obitos": obitos, "exposicao_central": float(exposicao) if exposicao else 0.0,
        })
    return linhas


def separar_treino_holdout(linhas):
    """Ano mais recente presente = holdout; todo o resto = treino."""
    anos = sorted({l["ano_calendario"] for l in linhas})
    if len(anos) < 2:
        return anos, None, None
    holdout_ano = anos[-1]
    treino = [l for l in linhas if l["ano_calendario"] != holdout_ano]
    holdout = [l for l in linhas if l["ano_calendario"] == holdout_ano]
    return anos, treino, holdout


def agregar_por_idade_submassa(linhas):
    """Soma obitos/exposicao através dos anos, por (idade, submassa) —
    formato aceito por suavizar_por_submassa (via taxas_brutas_qx)."""
    acumulado = {}
    for l in linhas:
        chave = (l["idade"], l["submassa"])
        reg = acumulado.setdefault(chave, {
            "idade": l["idade"], "submassa": l["submassa"],
            "obitos": 0, "exposicao_central": 0.0,
        })
        reg["obitos"] += l["obitos"]
        reg["exposicao_central"] += l["exposicao_central"]
    for reg in acumulado.values():
        reg["qx_bruto"] = (
            reg["obitos"] / reg["exposicao_central"] if reg["exposicao_central"] > 0 else None
        )
    return list(acumulado.values())


def montar_celulas_holdout(qx_treino_suavizado, holdout_agregado):
    """Formato aceito por montar_celulas()/qui_quadrado(): obitos e
    exposição são do ano de holdout, qx_suavizado vem do treino."""
    linhas = []
    for reg in holdout_agregado:
        qx_previsto = qx_treino_suavizado.get((reg["idade"], reg["submassa"]))
        if qx_previsto is None:
            continue  # idade/submassa sem histórico no treino — não dá pra prever
        linhas.append({
            "idade": reg["idade"], "submassa": reg["submassa"],
            "obitos": reg["obitos"], "exposicao_central": reg["exposicao_central"],
            "qx_suavizado": qx_previsto,
        })
    return linhas


def montar_relatorio(anos_treino, holdout_ano, celulas_por_submassa):
    linhas_relatorio = [
        "# Validação temporal — holdout por ano_calendario",
        "",
        f"Treino: anos {anos_treino[0]}-{anos_treino[-1]} "
        f"({len(anos_treino)} ano(s)). Holdout: {holdout_ano}.",
        "",
    ]
    stat_total, df_total = 0.0, 0
    for submassa in sorted(celulas_por_submassa):
        celulas = celulas_por_submassa[submassa]
        linhas_relatorio.append(f"## {submassa}")
        if not celulas:
            linhas_relatorio.append("- sem idade/submassa com histórico de treino "
                                     "e exposição no holdout ao mesmo tempo.")
            linhas_relatorio.append("")
            continue
        estatistica, df, p_valor = qui_quadrado(celulas)
        linhas_relatorio.append(f"- células testadas: {len(celulas)}")
        linhas_relatorio.append(f"- estatística qui-quadrado: {estatistica:.4f}")
        linhas_relatorio.append(f"- graus de liberdade: {df}")
        if p_valor is None:
            linhas_relatorio.append("- p-valor: não calculável (menos de 2 células)")
        else:
            veredito = "qx do treino ainda explica o holdout (H0 não rejeitada)" if p_valor >= ALPHA \
                else "qx do treino não explica o holdout — revisar suavização/horizonte"
            linhas_relatorio.append(f"- p-valor: {p_valor:.4f} (alpha={ALPHA}) -> {veredito}")
            stat_total += estatistica
            df_total += df
        linhas_relatorio.append("")

    if df_total > 0:
        from scipy.stats import chi2
        p_valor_total = float(chi2.sf(stat_total, df_total))
        veredito = "qx do treino ainda explica o holdout (H0 não rejeitada)" if p_valor_total >= ALPHA \
            else "qx do treino não explica o holdout — revisar suavização/horizonte"
        linhas_relatorio.append("## Geral")
        linhas_relatorio.append(f"- estatística qui-quadrado: {stat_total:.4f}")
        linhas_relatorio.append(f"- graus de liberdade: {df_total}")
        linhas_relatorio.append(f"- p-valor: {p_valor_total:.4f} (alpha={ALPHA}) -> {veredito}")

    return "\n".join(linhas_relatorio)


def main():
    conn = conectar()
    cur = conn.cursor()
    por_ano = carregar_por_ano(cur)
    cur.close()
    conn.close()

    if not por_ano:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    anos, treino, holdout = separar_treino_holdout(por_ano)
    if treino is None:
        print(f"Só há um ano_calendario nos dados ({anos[0] if anos else '?'}) — "
              "validação temporal ainda não é possível. Precisa de pelo menos 2 anos "
              "distintos em exposicao.ano_calendario.")
        return

    holdout_ano = anos[-1]
    treino_agregado = agregar_por_idade_submassa(treino)
    holdout_agregado = agregar_por_idade_submassa(holdout)

    suavizadas_treino = suavizar_por_submassa(treino_agregado)
    qx_treino_suavizado = {
        (l["idade"], l["submassa"]): l["qx_suavizado"] for l in suavizadas_treino
        if l["qx_suavizado"] is not None
    }

    celulas_holdout = montar_celulas_holdout(qx_treino_suavizado, holdout_agregado)
    celulas_por_submassa = montar_celulas(celulas_holdout)

    relatorio = montar_relatorio(anos[:-1], holdout_ano, celulas_por_submassa)
    print(relatorio)

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_SAIDA / f"validacao_temporal_{date.today().isoformat()}.md"
    caminho.write_text(relatorio, encoding="utf-8")
    print(f"\nGravado em {caminho}")


if __name__ == "__main__":
    main()
