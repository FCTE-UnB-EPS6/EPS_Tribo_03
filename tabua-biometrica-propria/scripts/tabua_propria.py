"""
Passo 5 — Consolidação: a tábua própria final

Última etapa do fluxo do §3 (... comparação com tábua externa -> validação
-> tábua própria). Reúne o que os outros scripts já calculam em uma saída
única por (idade, submassa) — hoje cada um produz seu artefato isolado
(bruto, suavizado, credibilizado, IC), sem nada que diga qual delas é "a"
tábua própria que o Passo 6 vai consumir.

Adota qx_credibilizado (credibility.py) como o qx oficial — é o último
tratamento estatístico da cadeia antes da comparação externa/validação,
e já incorpora a suavização por baixo (credibility.py suaviza antes de
credibilizar).

Antes de gravar como "oficial", roda dois portões de qualidade (reaproveita
os módulos já existentes, não recalcula nada do zero):

    1. Aderência: a mesma bateria de teste_aderencia.py (qui-quadrado geral).
    2. A/E: a mesma comparação de comparacao_ae.py contra o IBGE (categoria
       "Ambos"), com uma faixa de sanidade frouxa (0.5x-2x) — não é um
       critério estatístico formal, é só pra pegar um desvio grosseiro
       antes de oficializar.

Se algum portão falhar, a tábua ainda é gravada (pra não travar o Passo 6),
mas o relatório marca claramente que precisa de revisão antes de
considerar definitiva.

Uso:
    python tabua_propria.py
"""

from datetime import date
from pathlib import Path
import csv

from scipy.stats import chi2

from db import conectar
from taxas_brutas_qx import calcular_taxas_brutas
from suavizacao import suavizar_por_submassa
from credibility import calcular_credibility
from intervalos_confianca import calcular_ics
from teste_aderencia import montar_celulas, qui_quadrado, ALPHA as ALPHA_ADERENCIA
from comparacao_ae import carregar_ibge, ARQUIVOS_IBGE, carregar_taxas_brutas_por_sexo, calcular_ae

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "tabua_propria"

# Faixa de sanidade pro A/E geral antes de oficializar a tábua — frouxa de
# propósito (não é um critério estatístico formal, só pra pegar um desvio
# grosseiro). Fora dessa faixa não impede a gravação, só marca "revisar".
AE_FAIXA_ACEITAVEL = (0.5, 2.0)


def montar_tabua_final(brutas):
    """Uma linha por (idade, submassa) com bruto, suavizado, credibilizado
    e IC lado a lado — junta credibility.py e intervalos_confianca.py."""
    credibilizadas = calcular_credibility(brutas)
    ics = {(l["idade"], l["submassa"]): l for l in calcular_ics(brutas)}

    linhas = []
    for c in credibilizadas:
        ic = ics.get((c["idade"], c["submassa"]), {})
        linhas.append({
            "idade": c["idade"],
            "submassa": c["submassa"],
            "obitos": ic.get("obitos"),
            "exposicao_central": c["exposicao_central"],
            "qx_bruto": ic.get("qx_bruto"),
            "qx_suavizado": c["qx_suavizado_submassa"],
            "qx_credibilizado": c["qx_credibilizado"],
            "ic_inferior_95": ic.get("ic_inferior_95"),
            "ic_superior_95": ic.get("ic_superior_95"),
        })
    linhas.sort(key=lambda l: (l["submassa"], l["idade"]))
    return linhas


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "submassa", "obitos", "exposicao_central", "qx_bruto",
                   "qx_suavizado", "qx_credibilizado", "ic_inferior_95", "ic_superior_95"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def gate_aderencia(brutas):
    """Reaproveita teste_aderencia.py: soma as estatísticas independentes
    por submassa (mesma lógica de montar_relatorio, só devolvendo os
    números em vez de texto)."""
    suavizadas = suavizar_por_submassa(brutas)
    celulas_por_submassa = montar_celulas(suavizadas)

    stat_total, df_total = 0.0, 0
    for celulas in celulas_por_submassa.values():
        if not celulas:
            continue
        estatistica, df, p_valor = qui_quadrado(celulas)
        if p_valor is not None:
            stat_total += estatistica
            df_total += df

    if df_total <= 0:
        return None, "aderência não calculável (dados insuficientes)"
    p_valor_total = float(chi2.sf(stat_total, df_total))
    passou = p_valor_total >= ALPHA_ADERENCIA
    texto = (f"p-valor geral = {p_valor_total:.4f} (alpha={ALPHA_ADERENCIA}) -> "
             f"{'OK, aderência plausível' if passou else 'REVISAR: aderência rejeitada'}")
    return passou, texto


def gate_ae(cur):
    """Reaproveita comparacao_ae.py: razão A/E geral da categoria 'Ambos'."""
    ibge_por_categoria = {cat: carregar_ibge(arq) for cat, arq in ARQUIVOS_IBGE.items()}
    brutas_por_sexo = carregar_taxas_brutas_por_sexo(cur)
    if not brutas_por_sexo:
        return None, "A/E não calculável (sem exposição por sexo)"

    linhas_ae = calcular_ae(brutas_por_sexo, ibge_por_categoria)
    ambos = [l for l in linhas_ae if l["categoria"] == "Ambos"]
    if not ambos:
        return None, "A/E não calculável (sem idade em comum com a tábua IBGE)"

    atual_total = sum(l["obitos_atual"] for l in ambos)
    esperado_total = sum(l["obitos_esperado"] for l in ambos)
    if esperado_total <= 0:
        return None, "A/E não calculável (esperado total zero)"

    razao = atual_total / esperado_total
    minimo, maximo = AE_FAIXA_ACEITAVEL
    passou = minimo <= razao <= maximo
    texto = (f"razão A/E geral (Ambos) = {razao:.3f} (faixa aceitável "
             f"{minimo}x-{maximo}x) -> {'OK' if passou else 'REVISAR: fora da faixa de sanidade'}")
    return passou, texto


def montar_relatorio(linhas, gate_aderencia_resultado, gate_ae_resultado):
    aderencia_ok, texto_aderencia = gate_aderencia_resultado
    ae_ok, texto_ae = gate_ae_resultado

    gates_ok = [g for g in (aderencia_ok, ae_ok) if g is not None]
    pronta = bool(gates_ok) and all(gates_ok)

    texto = [
        "# Tábua Biométrica Própria — consolidação final",
        "",
        f"qx oficial adotado: **qx_credibilizado** (credibility.py) — "
        f"{len(linhas)} células (idade x submassa).",
        "",
        "## Portões de qualidade",
        f"- Teste de aderência: {texto_aderencia}",
        f"- Comparação A/E (IBGE): {texto_ae}",
        "",
        f"## Veredito: {'PRONTA PARA OFICIALIZAR' if pronta else 'REVISAR ANTES DE OFICIALIZAR'}",
        "",
    ]
    if not pronta:
        texto.append(
            "Pelo menos um portão não passou (ou não pôde ser calculado). A "
            "tábua abaixo foi gravada mesmo assim, pra não travar o Passo 6, "
            "mas não deve ser tratada como definitiva sem revisão."
        )
    return "\n".join(texto)


def main():
    conn = conectar()
    cur = conn.cursor()
    brutas = calcular_taxas_brutas(cur)

    if not brutas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        cur.close()
        conn.close()
        return

    linhas = montar_tabua_final(brutas)
    resultado_aderencia = gate_aderencia(brutas)
    resultado_ae = gate_ae(cur)

    cur.close()
    conn.close()

    caminho_csv = PASTA_SAIDA / f"tabua_propria_{date.today().isoformat()}.csv"
    gravar_csv(linhas, caminho_csv)

    relatorio = montar_relatorio(linhas, resultado_aderencia, resultado_ae)
    print(relatorio)

    caminho_md = PASTA_SAIDA / f"tabua_propria_{date.today().isoformat()}.md"
    caminho_md.write_text(relatorio, encoding="utf-8")
    print(f"\nGravado em {caminho_csv} e {caminho_md}")


if __name__ == "__main__":
    main()
