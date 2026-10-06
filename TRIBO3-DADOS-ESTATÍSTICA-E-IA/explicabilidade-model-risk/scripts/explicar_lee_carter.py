# -*- coding: utf-8 -*-
"""Passo 7 / SL-07, Etapa 1: explicabilidade e model risk do Lee-Carter (Passo 6).

Lê a decomposição de Lee-Carter pelo contrato do Passo 6
(`tabuas-geracionais-improvement/contracts/api_modelos.py::obter_parametros_para_passo7`),
sem alterar nada do Passo 6, e produz:

1. checagens de plausibilidade (bloqueiam a publicação se falharem);
2. alertas de model risk (não bloqueiam, mas ficam registrados);
3. ALE de q(x,t) em função da idade e do ano (PyALE);
4. SHAP exato de q(x,t) com as entradas idade e ano (fórmula fechada para
   2 entradas, conferida contra a biblioteca `shap` nos testes);
5. gráficos PNG de alpha_x, beta_x, kappa_t, ALE e SHAP;
6. relatório JSON v1.0.0, validado contra `schemas/relatorio_explicabilidade.schema.json`.

A taxa q(x,t) é recalculada a partir dos parâmetros com a mesma fórmula de
`modelos/lee_carter.py::projetar_lee_carter` do Passo 6:
    m(x,t) = exp(alpha_x + beta_x * kappa_t)
    q(x,t) = 1 - exp(-m(x,t))
Anos futuros usam kappa_T + h * drift (passeio aleatório com drift, sem
choque), igual ao Passo 6. Anos históricos usam o kappa_t estimado daquele
ano (valor ajustado); aqui há uma diferença consciente: `projetar_lee_carter`
usa kappa_T para qualquer ano <= T (ver docs/decisoes.md, D5). Os limites
de q do Passo 6 (0,000001 a 0,999) também são aplicados; se algum valor
bater num limite, isso vira alerta.

Uso (de dentro de explicabilidade-model-risk/):
    python scripts/explicar_lee_carter.py
"""

import json
import logging
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # gera PNG sem precisar de janela gráfica

import jsonschema  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PyALE import ale  # noqa: E402

PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_PASSO6 = PASTA_RAIZ.parent / "tabuas-geracionais-improvement"
PASTA_DADOS_IBGE = PASTA_RAIZ.parent / "ambiente-de-dados" / "docs" / "referencias" / "ibge_historico"
PASTA_SAIDA = PASTA_RAIZ / "docs" / "lee_carter"
ARQUIVO_SCHEMA = PASTA_RAIZ / "schemas" / "relatorio_explicabilidade.schema.json"

VERSAO_RELATORIO = "1.0.0"

# Decisões registradas em docs/decisoes.md (D3 e D4).
IDADE_MINIMA_MONOTONIA = 30   # abaixo disso existe a "corcova de acidentes" (causas externas)
FATOR_SALTO_KAPPA = 3.0       # variação anual de kappa_t > 3 x |drift| vira alerta
HORIZONTE_PROJECAO_ANOS = 30  # mesmo horizonte do Passo 6 (scripts/config.py)
GRID_ALE = 20                 # número de faixas do ALE
Q_MINIMO, Q_MAXIMO = 1e-6, 0.999  # limites de q aplicados pelo Passo 6 (projetar_lee_carter)

NOMES_GRAFICOS = (
    "alpha_x.png", "beta_x.png", "kappa_t.png",
    "ale_idade.png", "ale_ano.png", "shap_dependencia.png",
)

# Código e dados que determinam o resultado; usados no controle de alterações
# locais da rodada. docs/ fica de fora: é onde a própria rodada grava a saída.
CAMINHOS_RASTREADOS = (
    PASTA_RAIZ / "scripts",
    PASTA_RAIZ / "schemas",
    PASTA_RAIZ / "requirements.txt",
    PASTA_PASSO6 / "scripts",
    PASTA_PASSO6 / "contracts",
    PASTA_DADOS_IBGE,
)

NOTA_DE_USO = (
    "Explicação de um modelo de mortalidade populacional agregada (IBGE). "
    "Insumo para gestão coletiva de risco atuarial; nunca para decisão "
    "automática sobre pessoas."
)

log = logging.getLogger("explicabilidade.lee_carter")


# ---------------------------------------------------------------------------
# 1. Entrada: contrato do Passo 6
# ---------------------------------------------------------------------------

def carregar_parametros():
    """Chama o contrato do Passo 6 sem alterá-lo e devolve o dict dele."""
    if str(PASTA_PASSO6) not in sys.path:
        sys.path.insert(0, str(PASTA_PASSO6))
    from contracts.api_modelos import obter_parametros_para_passo7

    return obter_parametros_para_passo7()


# ---------------------------------------------------------------------------
# 2. Cálculo de q(x,t) a partir dos parâmetros
# ---------------------------------------------------------------------------

def kappa_para_ano(params, ano):
    """kappa do ano: histórico se o ano foi observado, projeção com drift se for futuro."""
    anos = params["anos_historicos"]
    if ano in anos:
        return params["kappa_t"][anos.index(ano)]
    ano_ultimo = anos[-1]
    if ano < anos[0]:
        raise ValueError(f"Ano {ano} anterior à série histórica ({anos[0]}).")
    if ano < ano_ultimo:
        raise ValueError(f"Ano {ano} sem kappa_t dentro da série histórica.")
    return params["kappa_t"][-1] + (ano - ano_ultimo) * params["drift"]


def calcular_qx(params, idades, anos):
    """q(x,t) para listas paralelas de idade e ano (mesmo tamanho)."""
    idades = np.rint(np.asarray(idades, dtype=float)).astype(int)
    anos = np.rint(np.asarray(anos, dtype=float)).astype(int)
    alpha = np.array(params["alpha_x"])
    beta = np.array(params["beta_x"])

    # Índice de cada idade em params["idades"] (vetorizado: o SHAP chama com ~1 milhão de pontos).
    idades_modelo = np.array(params["idades"])
    idx = np.searchsorted(idades_modelo, idades)
    fora = (idx >= len(idades_modelo)) | (idades_modelo[np.minimum(idx, len(idades_modelo) - 1)] != idades)
    if np.any(fora):
        raise ValueError(f"Idades fora do modelo: {sorted(set(idades[fora].tolist()))[:10]}")

    # kappa de cada ano: calculado uma vez por ano distinto.
    anos_unicos, inverso = np.unique(anos, return_inverse=True)
    kappa = np.array([kappa_para_ano(params, int(t)) for t in anos_unicos])[inverso]

    mx = np.exp(alpha[idx] + beta[idx] * kappa)
    # Mesmo tratamento de projetar_lee_carter (Passo 6): m >= 1 vira 0.999 e
    # q fica limitado a [Q_MINIMO, Q_MAXIMO].
    qx = np.where(mx < 1.0, 1.0 - np.exp(-mx), Q_MAXIMO)
    return np.clip(qx, Q_MINIMO, Q_MAXIMO)


def anos_analisados(params, horizonte=HORIZONTE_PROJECAO_ANOS):
    """Anos históricos + horizonte de projeção."""
    primeiro = params["anos_historicos"][0]
    ultimo = params["anos_historicos"][-1] + horizonte
    return list(range(primeiro, ultimo + 1))


def matriz_qx(params, anos):
    """Matriz q[idade, ano] (linhas = params['idades'], colunas = anos)."""
    idades = params["idades"]
    grade_idade = np.repeat(idades, len(anos))
    grade_ano = np.tile(anos, len(idades))
    return calcular_qx(params, grade_idade, grade_ano).reshape(len(idades), len(anos))


class ModeloQx:
    """Embrulha q(x,t) com a interface `predict(DataFrame)` que o PyALE espera."""

    def __init__(self, params):
        self.params = params

    def predict(self, X):
        return calcular_qx(self.params, X["idade"].to_numpy(), X["ano"].to_numpy())


def grade_entradas(params, anos):
    """Todas as combinações (idade, ano) analisadas, como DataFrame."""
    idades = params["idades"]
    return pd.DataFrame({
        "idade": np.repeat(idades, len(anos)),
        "ano": np.tile(anos, len(idades)),
    })


# ---------------------------------------------------------------------------
# 3. Plausibilidade (bloqueia) e alertas de model risk (não bloqueiam)
# ---------------------------------------------------------------------------

def _checagem(nome, aprovado, detalhe):
    return {"nome": nome, "aprovado": bool(aprovado), "detalhe": detalhe}


def problemas_estrutura(params):
    """Inconsistências de forma nos parâmetros que impedem calcular q(x,t)."""
    problemas = []
    idades = np.asarray(params["idades"])
    anos = np.asarray(params["anos_historicos"])
    if len(idades) == 0 or np.any(np.diff(idades) <= 0):
        problemas.append("idades vazias ou fora de ordem crescente")
    if len(anos) < 2 or np.any(np.diff(anos) != 1):
        problemas.append("anos_historicos com menos de 2 anos, fora de ordem ou com lacunas")
    for nome in ("alpha_x", "beta_x"):
        if len(params[nome]) != len(idades):
            problemas.append(f"{nome} com {len(params[nome])} valores para {len(idades)} idades")
    if len(params["kappa_t"]) != len(anos):
        problemas.append(f"kappa_t com {len(params['kappa_t'])} valores para {len(anos)} anos")
    return problemas


def verificar_plausibilidade(params, anos, idade_minima=IDADE_MINIMA_MONOTONIA):
    """Checagens que, se falharem, impedem a publicação da explicação.

    A primeira checagem é a de estrutura: se ela falhar, as demais não são
    calculadas (q(x,t) não pode ser calculado com parâmetros malformados).
    """
    problemas = problemas_estrutura(params)
    checagens = [_checagem(
        "estrutura_consistente", not problemas,
        "Tamanhos de alpha_x, beta_x e kappa_t batem com idades e anos; "
        "idades crescentes; anos consecutivos. "
        + ("Sem problemas." if not problemas else "Problemas: " + "; ".join(problemas)),
    )]
    if problemas:
        return checagens

    q = matriz_qx(params, anos)

    numeros = np.concatenate([
        params["alpha_x"], params["beta_x"], params["kappa_t"],
        [params["drift"], params["variancia_explicada"]], q.ravel(),
    ])
    checagens.append(_checagem(
        "valores_finitos", np.all(np.isfinite(numeros)),
        f"Parâmetros e q(x,t) sem NaN nem infinito; q(x,t) entre {q.min():.6f} e {q.max():.6f}.",
    ))

    idades = np.array(params["idades"])
    adultas = idades >= idade_minima
    diferencas = np.diff(q[adultas], axis=0)
    quedas = [
        (int(idades[adultas][i + 1]), int(anos[j]))
        for i, j in zip(*np.where(diferencas <= 0))
    ]
    checagens.append(_checagem(
        "q_cresce_com_idade", len(quedas) == 0,
        f"A partir de {idade_minima} anos, em todos os anos analisados. "
        + ("Sem exceções." if not quedas else f"Quedas em (idade, ano): {quedas[:10]}"),
    ))

    inclinacao = tendencia_linear_kappa(params)
    checagens.append(_checagem(
        "kappa_em_queda", params["drift"] < 0 and inclinacao < 0,
        f"drift = {params['drift']:.4f}; inclinação da reta de kappa_t = {inclinacao:.4f} "
        "(as duas devem ser negativas: mortalidade caindo).",
    ))

    soma_beta = float(np.sum(params["beta_x"]))
    media_kappa = float(np.mean(params["kappa_t"]))
    checagens.append(_checagem(
        "restricoes_canonicas", abs(soma_beta - 1) < 1e-6 and abs(media_kappa) < 1e-6,
        f"soma(beta_x) = {soma_beta:.6f} (deve ser 1); média(kappa_t) = {media_kappa:.6f} (deve ser 0).",
    ))

    return checagens


def tendencia_linear_kappa(params):
    """Inclinação da reta de mínimos quadrados de kappa_t contra o ano."""
    return float(np.polyfit(params["anos_historicos"], params["kappa_t"], 1)[0])


def detectar_saltos_kappa(params, fator=FATOR_SALTO_KAPPA):
    """Anos em que kappa_t varia mais que `fator` x |drift| em relação ao ano anterior."""
    anos = params["anos_historicos"]
    kappa = np.array(params["kappa_t"])
    limite = fator * abs(params["drift"])
    saltos = []
    for i, variacao in enumerate(np.diff(kappa)):
        if abs(variacao) > limite:
            saltos.append({
                "de": int(anos[i]), "para": int(anos[i + 1]),
                "variacao": float(variacao), "limite": float(limite),
            })
    return saltos


def gerar_alertas(params, idade_minima=IDADE_MINIMA_MONOTONIA,
                  horizonte=HORIZONTE_PROJECAO_ANOS):
    """Achados de model risk que não bloqueiam, mas precisam ser lidos por alguém."""
    alertas = []

    q_todos = matriz_qx(params, anos_analisados(params, horizonte))
    no_limite = int(np.sum((q_todos <= Q_MINIMO) | (q_todos >= Q_MAXIMO)))
    if no_limite:
        alertas.append({
            "tipo": "q_no_limite_de_corte",
            "detalhe": (
                f"{no_limite} valores de q(x,t) bateram no limite do Passo 6 "
                f"({Q_MINIMO:g} ou {Q_MAXIMO:g}); ali o modelo não responde mais "
                "a idade e ano, e a explicação perde sentido."
            ),
        })

    for s in detectar_saltos_kappa(params):
        alertas.append({
            "tipo": "salto_kappa",
            "detalhe": (
                f"kappa_t variou {s['variacao']:+.3f} de {s['de']} para {s['para']} "
                f"(limite {s['limite']:.3f} = {FATOR_SALTO_KAPPA:g} x |drift|). "
                "Possível quebra na série; avisar a dupla do Passo 6."
            ),
        })

    idades = np.array(params["idades"])
    beta = np.array(params["beta_x"])
    if np.any(beta < 0):
        alertas.append({
            "tipo": "beta_negativo",
            "detalhe": (
                f"beta_x negativo nas idades {idades[beta < 0].tolist()[:10]}: com kappa_t "
                "caindo, o modelo projeta mortalidade SUBINDO nessas idades. "
                "Avisar a dupla do Passo 6."
            ),
        })

    inclinacao = tendencia_linear_kappa(params)
    drift = params["drift"]
    if drift != 0 and abs(inclinacao - drift) / abs(drift) > 0.25:
        alertas.append({
            "tipo": "drift_sensivel_aos_extremos",
            "detalhe": (
                f"O drift do Passo 6 usa só o primeiro e o último ano ({drift:.4f}); "
                f"a reta ajustada a todos os anos dá {inclinacao:.4f}. "
                "Diferença acima de 25%: a projeção depende muito dos anos das pontas."
            ),
        })

    q = matriz_qx(params, params["anos_historicos"])
    jovens = idades < idade_minima
    quedas_jovens = int(np.sum(np.diff(q[jovens], axis=0) <= 0)) if jovens.sum() > 1 else 0
    if quedas_jovens:
        alertas.append({
            "tipo": "corcova_de_acidentes",
            "detalhe": (
                f"{quedas_jovens} casos de q(x,t) que não crescem com a idade abaixo de "
                f"{idade_minima} anos. Comportamento esperado (mortes por causas externas "
                "em adultos jovens); fora da checagem de monotonia."
            ),
        })

    return alertas


# ---------------------------------------------------------------------------
# 4. ALE e SHAP
# ---------------------------------------------------------------------------

def calcular_ale(params, anos, grid_size=GRID_ALE):
    """ALE de q(x,t) para idade e ano. Devolve {feature: [{valor, efeito}, ...]}."""
    X = grade_entradas(params, anos)
    modelo = ModeloQx(params)
    resultado = {}
    for feature in ("idade", "ano"):
        efeito = ale(
            X=X, model=modelo, feature=[feature], feature_type="continuous",
            grid_size=grid_size, include_CI=False, plot=False,
        )
        resultado[feature] = [
            {"valor": float(v), "efeito": float(e)}
            for v, e in zip(efeito.index, efeito["eff"])
        ]
    return resultado


def calcular_shap(params, anos):
    """Valores SHAP exatos de q(x,t) com 2 entradas (idade, ano).

    Fundo (background) = grade histórica (idades x anos observados): o valor
    base é a média de q no período observado. Com 2 entradas, o valor de
    Shapley tem fórmula fechada (média das 2 ordens possíveis):
        v(S) = média, sobre o fundo, de q com as entradas de S fixadas no ponto
        phi_idade = [(v({idade}) - v({})) + (q(x,t) - v({ano}))] / 2
        phi_ano   = [(v({ano})   - v({})) + (q(x,t) - v({idade}))] / 2
    É o mesmo que `shap.explainers.Exact` com masker `Independent` calcula
    (conferido em tests/), mas vetorizado: segundos em vez de minutos.
    """
    fundo = grade_entradas(params, params["anos_historicos"]).to_numpy(dtype=float)
    pontos = grade_entradas(params, anos).to_numpy(dtype=float)
    return calcular_shap_pontos(params, pontos, fundo)


def calcular_shap_pontos(params, pontos, fundo):
    n, b = len(pontos), len(fundo)
    q_ponto = calcular_qx(params, pontos[:, 0], pontos[:, 1])
    v_vazio = float(np.mean(calcular_qx(params, fundo[:, 0], fundo[:, 1])))
    # v({idade}): idade do ponto com cada ano do fundo; v({ano}): o contrário.
    v_idade = calcular_qx(
        params, np.repeat(pontos[:, 0], b), np.tile(fundo[:, 1], n),
    ).reshape(n, b).mean(axis=1)
    v_ano = calcular_qx(
        params, np.tile(fundo[:, 0], n), np.repeat(pontos[:, 1], b),
    ).reshape(n, b).mean(axis=1)

    phi_idade = ((v_idade - v_vazio) + (q_ponto - v_ano)) / 2
    phi_ano = ((v_ano - v_vazio) + (q_ponto - v_idade)) / 2
    return {
        "pontos": pontos,
        "valores": np.column_stack([phi_idade, phi_ano]),
        "valor_base": v_vazio,
    }


def resumir_shap(shap_res):
    valores = shap_res["valores"]
    return {
        "valor_base": shap_res["valor_base"],
        "importancia_media_abs": {
            "idade": float(np.mean(np.abs(valores[:, 0]))),
            "ano": float(np.mean(np.abs(valores[:, 1]))),
        },
    }


# ---------------------------------------------------------------------------
# 5. Gráficos
# ---------------------------------------------------------------------------

def _salvar(fig, pasta, nome):
    caminho = pasta / nome
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)
    return nome


def gerar_graficos(params, ale_res, shap_res, pasta):
    """Gera os PNGs e devolve a lista de nomes de arquivo."""
    nomes = []
    idades = params["idades"]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(idades, params["alpha_x"], marker=".")
    ax.set(title="alpha_x: nível médio de log-mortalidade por idade",
           xlabel="Idade", ylabel="alpha_x (log m)")
    nomes.append(_salvar(fig, pasta, "alpha_x.png"))

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(idades, params["beta_x"], marker=".")
    ax.set(title="beta_x: quanto cada idade acompanha a tendência (kappa_t)",
           xlabel="Idade", ylabel="beta_x")
    nomes.append(_salvar(fig, pasta, "beta_x.png"))

    anos_h = params["anos_historicos"]
    futuros = list(range(anos_h[-1], anos_h[-1] + HORIZONTE_PROJECAO_ANOS + 1))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(anos_h, params["kappa_t"], marker="o", label="kappa_t histórico")
    ax.plot(futuros, [kappa_para_ano(params, a) for a in futuros],
            linestyle="--", label=f"projeção (drift = {params['drift']:.3f}/ano)")
    for s in detectar_saltos_kappa(params):
        ax.axvspan(s["de"], s["para"], color="orange", alpha=0.25)
    ax.set(title="kappa_t: índice de nível da mortalidade no tempo",
           xlabel="Ano", ylabel="kappa_t")
    ax.legend()
    nomes.append(_salvar(fig, pasta, "kappa_t.png"))

    for feature, titulo in (("idade", "Idade"), ("ano", "Ano")):
        pontos = ale_res[feature]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot([p["valor"] for p in pontos], [p["efeito"] for p in pontos], marker=".")
        ax.axhline(0, color="grey", linewidth=0.8)
        ax.set(title=f"ALE: efeito de {titulo.lower()} sobre q(x,t)",
               xlabel=titulo, ylabel="Efeito em q (diferença da média)")
        nomes.append(_salvar(fig, pasta, f"ale_{feature}.png"))

    # Cor = a outra entrada: mostra a interação idade x ano, que o ALE não mostra.
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    titulos = ("Idade", "Ano")
    for i, titulo in enumerate(titulos):
        outra = 1 - i
        pontos = axs[i].scatter(shap_res["pontos"][:, i], shap_res["valores"][:, i],
                                c=shap_res["pontos"][:, outra], cmap="viridis", s=4)
        fig.colorbar(pontos, ax=axs[i], label=titulos[outra])
        axs[i].axhline(0, color="grey", linewidth=0.8)
        axs[i].set(title=f"SHAP de {titulo.lower()}", xlabel=titulo,
                   ylabel="Contribuição para q(x,t)")
    nomes.append(_salvar(fig, pasta, "shap_dependencia.png"))

    return nomes


# ---------------------------------------------------------------------------
# 6. Relatório JSON e metadados da rodada
# ---------------------------------------------------------------------------

def commit_atual():
    """SHA do commit do repositório e se há alterações não commitadas.

    "Alterações locais" considera o código desta pasta, o código do Passo 6
    e a série do IBGE (CAMINHOS_RASTREADOS), mas não docs/: preencher o
    experiment record ou ter saídas de uma rodada anterior não invalida a rodada.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PASTA_RAIZ,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        sujo = subprocess.run(
            ["git", "status", "--porcelain", "--", *map(str, CAMINHOS_RASTREADOS)],
            cwd=PASTA_RAIZ, capture_output=True, text=True, check=True,
        ).stdout.strip() != ""
        return sha, sujo
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido", True


def versoes_bibliotecas():
    versoes = {"python": platform.python_version()}
    for pacote in ("numpy", "pandas", "matplotlib", "PyALE", "jsonschema"):
        try:
            versoes[pacote] = metadata.version(pacote)
        except metadata.PackageNotFoundError:
            versoes[pacote] = "desconhecida"
    return versoes


def carregar_schema():
    with open(ARQUIVO_SCHEMA, encoding="utf-8") as f:
        return json.load(f)


def validar_relatorio(relatorio):
    """Levanta jsonschema.ValidationError se o relatório não seguir o contrato v1.0.0."""
    jsonschema.validate(relatorio, carregar_schema())


def montar_relatorio(params, anos, checagens, alertas, ale_res, shap_resumo,
                     graficos, rodada):
    aprovado = all(c["aprovado"] for c in checagens)
    return {
        "versao_contrato": VERSAO_RELATORIO,
        "modelo": "Lee-Carter",
        "passo_origem": 6,
        "status": "APROVADO" if aprovado else "BLOQUEADO",
        "rodada": rodada,
        "parametros": {
            "idades": [int(x) for x in params["idades"]],
            "anos_historicos": [int(x) for x in params["anos_historicos"]],
            "anos_analisados": [int(anos[0]), int(anos[-1])],
            "alpha_x": [float(x) for x in params["alpha_x"]],
            "beta_x": [float(x) for x in params["beta_x"]],
            "kappa_t": [float(x) for x in params["kappa_t"]],
            "drift": float(params["drift"]),
            "variancia_explicada": float(params["variancia_explicada"]),
            "origem_dados": params["origem_dados"],
        },
        "plausibilidade": checagens,
        "alertas": alertas,
        "ale": ale_res,
        "shap": shap_resumo,
        "graficos": graficos,
        "nota_de_uso": NOTA_DE_USO,
    }


# ---------------------------------------------------------------------------
# 7. Execução
# ---------------------------------------------------------------------------

def executar(params, pasta_saida=PASTA_SAIDA):
    """Roda a explicação completa e grava o relatório em `pasta_saida`.

    Se alguma checagem de plausibilidade falhar, grava só o relatório com
    status BLOQUEADO (sem ALE, SHAP e gráficos) e devolve esse relatório:
    explicação de um modelo implausível não é publicada.
    """
    inicio = time.perf_counter()
    agora = datetime.now(timezone.utc)
    # Antes de gravar qualquer saída: o estado do código é o que importa.
    sha, sujo = commit_atual()
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    # Gráficos de uma rodada anterior não podem sobrar ao lado de um relatório novo
    # (principalmente se o novo for BLOQUEADO e não listar gráfico nenhum).
    for nome in NOMES_GRAFICOS:
        (pasta_saida / nome).unlink(missing_ok=True)

    anos = anos_analisados(params)
    checagens = verificar_plausibilidade(params, anos)
    estrutura_ok = checagens[0]["aprovado"]
    alertas = gerar_alertas(params) if estrutura_ok else []
    for a in alertas:
        log.warning("ALERTA %s: %s", a["tipo"], a["detalhe"])

    aprovado = all(c["aprovado"] for c in checagens)
    if aprovado:
        ale_res = calcular_ale(params, anos)
        shap_res = calcular_shap(params, anos)
        shap_resumo = resumir_shap(shap_res)
        graficos = gerar_graficos(params, ale_res, shap_res, pasta_saida)
    else:
        for c in checagens:
            if not c["aprovado"]:
                log.error("BLOQUEADO %s: %s", c["nome"], c["detalhe"])
        ale_res, shap_resumo, graficos = None, None, []

    rodada = {
        "id": agora.strftime("%Y%m%dT%H%M%SZ"),
        "data_hora_utc": agora.isoformat(timespec="seconds"),
        "commit": sha,
        "commit_com_alteracoes_locais": sujo,
        "versoes": versoes_bibliotecas(),
        "tempo_execucao_s": round(time.perf_counter() - inicio, 3),
    }

    relatorio = montar_relatorio(params, anos, checagens, alertas, ale_res,
                                 shap_resumo, graficos, rodada)
    validar_relatorio(relatorio)

    caminho = pasta_saida / "relatorio_explicabilidade_lee_carter.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    log.info("Relatório %s gravado em %s (%.2fs)", relatorio["status"], caminho,
             rodada["tempo_execucao_s"])
    return relatorio


def main():
    # force=True: o PyALE chama basicConfig ao ser importado e esconderia o INFO.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
    params = carregar_parametros()
    log.info("Contrato do Passo 6 lido: %d idades, anos %d-%d, origem: %s",
             len(params["idades"]), params["anos_historicos"][0],
             params["anos_historicos"][-1], params["origem_dados"])
    relatorio = executar(params)
    return 0 if relatorio["status"] == "APROVADO" else 1


if __name__ == "__main__":
    sys.exit(main())
