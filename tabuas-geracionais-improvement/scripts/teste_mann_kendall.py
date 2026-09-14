"""
Passo 6 — Teste de Tendência de Mann-Kendall

Executa o teste não-paramétrico de Mann-Kendall sobre as taxas de mortalidade
ao longo dos anos de calendário observados.

Exigência explícita do §3/§8 (Definition of Done) para comprovar direção
estatisticamente significativa de redução da mortalidade (mortality improvement).

Uso:
    python scripts/teste_mann_kendall.py
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
import sys
import numpy as np
from scipy.stats import norm

# Garante import local direto
PASTA_SCRIPTS = Path(__file__).resolve().parent
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from config import ALPHA, PASTA_TESTES_ESTATISTICOS
from series_temporais import carregar_dados


def calcular_mann_kendall(valores):
    """Calcula o teste de Mann-Kendall para uma sequência de valores temporais."""
    n = len(valores)
    if n < 4:
        return {
            "n": n, "S": 0, "var_s": 0.0, "Z": 0.0,
            "p_valor": 1.0, "direcao": "Amostra insuficiente (n < 4)"
        }

    s = 0
    for k in range(n - 1):
        for j in range(k + 1, n):
            s += int(np.sign(valores[j] - valores[k]))

    _, counts = np.unique(valores, return_counts=True)
    ajuste_empates = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - ajuste_empates) / 18.0

    if var_s > 0:
        if s > 0:
            z = (s - 1) / np.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / np.sqrt(var_s)
        else:
            z = 0.0
    else:
        z = 0.0

    p_valor = 2.0 * (1.0 - norm.cdf(abs(z)))

    if p_valor < ALPHA:
        if s < 0:
            direcao = "Tendência de QUEDA estatisticamente significante (Mortality Improvement confirmado)"
        else:
            direcao = "Tendência de ALTA estatisticamente significante (Piora de mortalidade)"
    else:
        direcao = "Sem tendência monotônica estatisticamente significante"

    return {
        "n": n,
        "S": int(s),
        "var_s": round(float(var_s), 4),
        "Z": round(float(z), 4),
        "p_valor": round(float(p_valor), 5),
        "direcao": direcao,
        "improvement_confirmado": bool(s < 0 and p_valor < ALPHA),
    }


def analisar_tendencias(linhas):
    dados_ano = defaultdict(lambda: {"obitos": 0, "exposicao": 0.0})
    faixas = {
        "20-39": defaultdict(lambda: {"obitos": 0, "exposicao": 0.0}),
        "40-59": defaultdict(lambda: {"obitos": 0, "exposicao": 0.0}),
        "60+": defaultdict(lambda: {"obitos": 0, "exposicao": 0.0}),
    }

    for l in linhas:
        ano = l["ano"]
        dados_ano[ano]["obitos"] += l["obitos"]
        dados_ano[ano]["exposicao"] += l["exposicao_central"]

        idade = l["idade"]
        if idade < 40:
            faixa = "20-39"
        elif idade < 60:
            faixa = "40-59"
        else:
            faixa = "60+"
        faixas[faixa][ano]["obitos"] += l["obitos"]
        faixas[faixa][ano]["exposicao"] += l["exposicao_central"]

    anos_ordenados = sorted(dados_ano.keys())
    taxas_globais = [
        dados_ano[a]["obitos"] / max(dados_ano[a]["exposicao"], 1e-9)
        for a in anos_ordenados
    ]

    res_global = calcular_mann_kendall(taxas_globais)
    res_global["anos"] = anos_ordenados
    res_global["taxas"] = [round(t, 6) for t in taxas_globais]

    res_faixas = {}
    for nome_faixa, dados in faixas.items():
        taxas = [dados[a]["obitos"] / max(dados[a]["exposicao"], 1e-9) for a in anos_ordenados]
        res_faixas[nome_faixa] = calcular_mann_kendall(taxas)

    return res_global, res_faixas


def montar_relatorio(res_global, res_faixas):
    linhas_relatorio = [
        "# Teste de Tendência de Mann-Kendall — Mortality Improvement",
        "",
        "**Objetivo:** Verificar se as taxas de mortalidade apresentam tendência de queda temporal estatisticamente significante (§3/§8 DoD).",
        f"**Nível de Significância (Alpha):** {ALPHA}",
        "",
        "## 1. Resultado Global da População",
        "",
        f"- **Período avaliado:** {res_global['anos'][0]} a {res_global['anos'][-1]} (n = {res_global['n']} anos)",
        f"- **Estatística S:** {res_global['S']}",
        f"- **Escore Z:** {res_global['Z']}",
        f"- **p-valor:** {res_global['p_valor']}",
        f"- **Diagnóstico:** **{res_global['direcao']}**",
        "",
        "### Trajetória Histórica das Taxas Centrais Anuais:",
        "| Ano | Taxa Central Geral (mx) |",
        "| :--- | :--- |",
    ]
    for ano, taxa in zip(res_global["anos"], res_global["taxas"]):
        linhas_relatorio.append(f"| {ano} | {taxa:.6f} |")

    linhas_relatorio.extend([
        "",
        "## 2. Análise por Grupos Etários",
        "",
        "| Faixa Etária | Estatística S | Escore Z | p-valor | Diagnóstico |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])
    for faixa, res in res_faixas.items():
        linhas_relatorio.append(
            f"| {faixa} anos | {res['S']} | {res['Z']} | {res['p_valor']} | {res['direcao']} |"
        )

    linhas_relatorio.extend([
        "",
        "## 3. Veredito para o Definition of Done (DoD)",
        "",
    ])
    if res_global["improvement_confirmado"]:
        linhas_relatorio.append(
            "> [!NOTE]\n"
            "> **APROVADO (Mortality Improvement Confirmado):** Há evidência estatística de declínio temporal da mortalidade. O ajuste de modelos dinâmicos/geracionais (Lee-Carter e Baseline) é plenamente justificado."
        )
    else:
        linhas_relatorio.append(
            "> [!NOTE]\n"
            "> **TENDÊNCIA INDETERMINADA OU ESTÁVEL:** O teste não rejeitou a hipótese nula com p < 0.05 no agregado global. Modelos com escala conservadora de improvement continuam aplicáveis por prudência atuarial."
        )

    return "\n".join(linhas_relatorio)


def main():
    linhas, _ = carregar_dados()
    res_global, res_faixas = analisar_tendencias(linhas)
    relatorio = montar_relatorio(res_global, res_faixas)

    PASTA_TESTES_ESTATISTICOS.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_TESTES_ESTATISTICOS / f"teste_mann_kendall_{date.today().isoformat()}.md"
    caminho.write_text(relatorio, encoding="utf-8")

    print("Teste de Mann-Kendall concluído:")
    print(f"  S: {res_global['S']}, Z: {res_global['Z']}, p-valor: {res_global['p_valor']}")
    print(f"  Diagnóstico: {res_global['direcao']}")
    print(f"  Relatório gravado em: {caminho}")


if __name__ == "__main__":
    main()
