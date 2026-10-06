# -*- coding: utf-8 -*-
"""Testes de scripts/explicar_lee_carter.py (Passo 7 / SL-07, Etapa 1).

Dois grupos:
- Unitários: usam parâmetros de BRINQUEDO (fixture `params_brinquedo`), com
  valores escolhidos à mão para a resposta ser conhecida. Eles NÃO comprovam
  integração com o Passo 6 (declarado no PR, bloco de mocks / CTR-005).
- Integração: chamam o contrato real do Passo 6
  (`obter_parametros_para_passo7()`, série real do IBGE).

Rodar de dentro de explicabilidade-model-risk/:
    python -m pytest -v
"""

import copy
import json
import math
import sys
from pathlib import Path

import jsonschema
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import explicar_lee_carter as elc  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture de brinquedo
# ---------------------------------------------------------------------------

@pytest.fixture
def params_brinquedo():
    """Lee-Carter de brinquedo: 5 idades (28 a 32), 5 anos (2000 a 2004).

    beta_x igual em todas as idades (soma 1), kappa_t caindo 1 por ano
    (média 0, drift -1), alpha_x crescendo com a idade.
    """
    return {
        "idades": [28, 29, 30, 31, 32],
        "alpha_x": [-6.0, -5.9, -5.8, -5.7, -5.6],
        "beta_x": [0.2, 0.2, 0.2, 0.2, 0.2],
        "kappa_t": [2.0, 1.0, 0.0, -1.0, -2.0],
        "anos_historicos": [2000, 2001, 2002, 2003, 2004],
        "drift": -1.0,
        "variancia_explicada": 0.95,
        "origem_dados": "BRINQUEDO (fixture de teste)",
    }


def q_manual(alpha, beta, kappa):
    return 1 - math.exp(-math.exp(alpha + beta * kappa))


# ---------------------------------------------------------------------------
# Cálculo de q(x,t)
# ---------------------------------------------------------------------------

def test_qx_historico_usa_kappa_do_ano(params_brinquedo):
    q = elc.calcular_qx(params_brinquedo, [30], [2001])[0]
    assert q == pytest.approx(q_manual(-5.8, 0.2, 1.0))


def test_qx_futuro_usa_drift(params_brinquedo):
    # 2007 = último ano (2004, kappa -2) + 3 anos de drift -1 -> kappa -5
    q = elc.calcular_qx(params_brinquedo, [32], [2007])[0]
    assert q == pytest.approx(q_manual(-5.6, 0.2, -5.0))


def _passo6_e_params_minimos():
    sys.path.insert(0, str(elc.PASTA_PASSO6 / "scripts"))
    from modelos.lee_carter import projetar_lee_carter

    params = {
        "idades": [40, 41], "alpha_x": [-5.0, -4.9], "beta_x": [0.4, 0.6],
        "kappa_t": [1.0, -1.0], "anos_historicos": [2010, 2011], "drift": -2.0,
    }
    modelo_passo6 = {
        "idades": params["idades"], "anos": params["anos_historicos"],
        "ax": np.array(params["alpha_x"]), "bx": np.array(params["beta_x"]),
        "kt": np.array(params["kappa_t"]), "drift": params["drift"],
    }
    return projetar_lee_carter, params, modelo_passo6


def test_qx_igual_a_formula_do_passo6():
    """Mesma fórmula de modelos/lee_carter.py::projetar_lee_carter (Passo 6),
    no último ano histórico e na projeção."""
    projetar_lee_carter, params, modelo_passo6 = _passo6_e_params_minimos()
    for idade in (40, 41):
        for ano in (2011, 2015, 2030):
            esperado = projetar_lee_carter(modelo_passo6, idade, ano)
            obtido = elc.calcular_qx(params, [idade], [ano])[0]
            assert obtido == pytest.approx(esperado, rel=1e-9)


def test_qx_historico_difere_do_passo6_de_proposito():
    """Diferença registrada em decisoes.md (D5): antes do último ano, o Passo 6
    usa kappa_T; aqui usamos o kappa_t ajustado daquele ano."""
    projetar_lee_carter, params, modelo_passo6 = _passo6_e_params_minimos()
    passo6 = projetar_lee_carter(modelo_passo6, 40, 2010)
    nosso = elc.calcular_qx(params, [40], [2010])[0]
    assert passo6 == pytest.approx(q_manual(-5.0, 0.4, -1.0))  # kappa de 2011
    assert nosso == pytest.approx(q_manual(-5.0, 0.4, 1.0))    # kappa de 2010


def test_ano_antes_da_serie_e_rejeitado(params_brinquedo):
    with pytest.raises(ValueError):
        elc.calcular_qx(params_brinquedo, [30], [1999])


def test_idade_fora_do_modelo_e_rejeitada(params_brinquedo):
    with pytest.raises(ValueError):
        elc.calcular_qx(params_brinquedo, [27], [2002])
    with pytest.raises(ValueError):
        elc.calcular_qx(params_brinquedo, [33], [2002])


def test_anos_analisados_inclui_horizonte(params_brinquedo):
    anos = elc.anos_analisados(params_brinquedo, horizonte=3)
    assert anos == [2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007]


# ---------------------------------------------------------------------------
# Plausibilidade e alertas
# ---------------------------------------------------------------------------

def _por_nome(checagens):
    return {c["nome"]: c for c in checagens}


def test_brinquedo_passa_em_todas_as_checagens(params_brinquedo):
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = elc.verificar_plausibilidade(params_brinquedo, anos)
    assert all(c["aprovado"] for c in checagens), checagens


def test_drift_positivo_bloqueia(params_brinquedo):
    params_brinquedo["kappa_t"] = [-2.0, -1.0, 0.0, 1.0, 2.0]
    params_brinquedo["drift"] = 1.0
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = _por_nome(elc.verificar_plausibilidade(params_brinquedo, anos))
    assert not checagens["kappa_em_queda"]["aprovado"]


def test_q_caindo_com_idade_adulta_bloqueia(params_brinquedo):
    params_brinquedo["alpha_x"][3] = -7.0  # idade 31 com mortalidade menor que a 30
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = _por_nome(elc.verificar_plausibilidade(params_brinquedo, anos))
    assert not checagens["q_cresce_com_idade"]["aprovado"]


def test_queda_abaixo_da_idade_minima_nao_bloqueia_e_vira_alerta(params_brinquedo):
    params_brinquedo["alpha_x"][1] = -6.5  # idade 29 menor que a 28 (corcova)
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = _por_nome(elc.verificar_plausibilidade(params_brinquedo, anos))
    assert checagens["q_cresce_com_idade"]["aprovado"]
    tipos = [a["tipo"] for a in elc.gerar_alertas(params_brinquedo)]
    assert "corcova_de_acidentes" in tipos


def test_valor_nao_finito_bloqueia(params_brinquedo):
    params_brinquedo["alpha_x"][0] = float("nan")
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = _por_nome(elc.verificar_plausibilidade(params_brinquedo, anos))
    assert not checagens["valores_finitos"]["aprovado"]


def test_estrutura_inconsistente_bloqueia_sem_quebrar(params_brinquedo):
    params_brinquedo["beta_x"] = params_brinquedo["beta_x"][:4]  # 4 betas para 5 idades
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    checagens = elc.verificar_plausibilidade(params_brinquedo, anos)
    assert [c["nome"] for c in checagens] == ["estrutura_consistente"]
    assert not checagens[0]["aprovado"]


@pytest.mark.parametrize("variancia", [1.5, -0.1, float("nan")])
def test_variancia_explicada_invalida_gera_bloqueado_sem_quebrar(params_brinquedo, tmp_path, variancia):
    params_brinquedo["variancia_explicada"] = variancia
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert relatorio["status"] == "BLOQUEADO"
    assert (tmp_path / "relatorio_explicabilidade_lee_carter.json").exists()


@pytest.mark.parametrize("campo,indice", [("alpha_x", 0), ("kappa_t", 2), ("drift", None)])
def test_bloqueado_com_nan_grava_json_valido(params_brinquedo, tmp_path, campo, indice):
    """NaN não existe em JSON: no relatório BLOQUEADO ele vira null."""
    if indice is None:
        params_brinquedo[campo] = float("nan")
    else:
        params_brinquedo[campo][indice] = float("nan")
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert relatorio["status"] == "BLOQUEADO"
    texto = (tmp_path / "relatorio_explicabilidade_lee_carter.json").read_text("utf-8")

    def rejeitar(constante):
        raise ValueError(f"{constante} não é JSON válido")

    gravado = json.loads(texto, parse_constant=rejeitar)
    valor = gravado["parametros"][campo]
    assert (valor if indice is None else valor[indice]) is None


def test_schema_rejeita_aprovado_com_parametro_null(params_brinquedo, tmp_path):
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    adulterado = copy.deepcopy(relatorio)
    adulterado["parametros"]["drift"] = None
    with pytest.raises(jsonschema.ValidationError):
        elc.validar_relatorio(adulterado)


@pytest.mark.parametrize("entrada", [
    {"idades": [30], "alpha_x": [-5.8], "beta_x": [1.0]},          # 1 idade só
    {"idades": [], "alpha_x": [], "beta_x": []},                    # nenhuma idade
    {"anos_historicos": [], "kappa_t": []},                         # nenhum ano
])
def test_entrada_vazia_ou_curta_gera_bloqueado_sem_quebrar(params_brinquedo, tmp_path, entrada):
    params_brinquedo.update(entrada)
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert relatorio["status"] == "BLOQUEADO"
    assert (tmp_path / "relatorio_explicabilidade_lee_carter.json").exists()


def test_anos_com_lacuna_bloqueiam(params_brinquedo):
    params_brinquedo["anos_historicos"] = [2000, 2001, 2003, 2004, 2005]
    assert elc.problemas_estrutura(params_brinquedo)


def test_beta_negativo_vira_alerta(params_brinquedo):
    params_brinquedo["beta_x"] = [0.3, 0.3, 0.3, 0.2, -0.1]  # soma continua 1
    tipos = [a["tipo"] for a in elc.gerar_alertas(params_brinquedo)]
    assert "beta_negativo" in tipos


def test_salto_de_kappa_e_detectado(params_brinquedo):
    # Variações: -1, +4, -5, -1. Limite = fator x |drift| = 4 x 0,75 = 3.
    # Saltos: 2001->2002 e 2002->2003.
    params_brinquedo["kappa_t"] = [1.0, 0.0, 4.0, -1.0, -2.0]
    params_brinquedo["drift"] = -0.75
    saltos = elc.detectar_saltos_kappa(params_brinquedo, fator=4.0)  # limite 3
    assert [(s["de"], s["para"]) for s in saltos] == [(2001, 2002), (2002, 2003)]


def test_q_no_limite_de_corte_vira_alerta(params_brinquedo):
    params_brinquedo["alpha_x"][0] = -20.0  # q da idade 28 abaixo de 0,000001 -> cortado
    tipos = [a["tipo"] for a in elc.gerar_alertas(params_brinquedo, horizonte=5)]
    assert "q_no_limite_de_corte" in tipos


def test_sem_salto_sem_alerta(params_brinquedo):
    assert elc.detectar_saltos_kappa(params_brinquedo) == []
    assert elc.gerar_alertas(params_brinquedo) == []


# ---------------------------------------------------------------------------
# ALE e SHAP
# ---------------------------------------------------------------------------

def test_ale_idade_crescente_e_ano_decrescente(params_brinquedo):
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    res = elc.calcular_ale(params_brinquedo, anos, grid_size=4)
    efeito_idade = [p["efeito"] for p in res["idade"]]
    efeito_ano = [p["efeito"] for p in res["ano"]]
    assert efeito_idade == sorted(efeito_idade)                 # idade ↑ -> q ↑
    assert efeito_ano == sorted(efeito_ano, reverse=True)       # ano ↑ -> q ↓ (drift < 0)


def test_shap_soma_reconstroi_q(params_brinquedo):
    """Propriedade de eficiência: valor base + soma dos SHAP = q(x,t)."""
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    res = elc.calcular_shap(params_brinquedo, anos)
    q = elc.calcular_qx(params_brinquedo, res["pontos"][:, 0], res["pontos"][:, 1])
    reconstruido = res["valor_base"] + res["valores"].sum(axis=1)
    assert np.allclose(reconstruido, q, rtol=0, atol=1e-12)


def test_shap_igual_a_biblioteca_shap(params_brinquedo):
    """A fórmula fechada bate com shap.explainers.Exact (mesmo fundo)."""
    shap = pytest.importorskip("shap")
    anos = elc.anos_analisados(params_brinquedo, horizonte=5)
    fundo = elc.grade_entradas(params_brinquedo, params_brinquedo["anos_historicos"]).to_numpy(float)
    pontos = elc.grade_entradas(params_brinquedo, anos).to_numpy(float)

    nosso = elc.calcular_shap_pontos(params_brinquedo, pontos, fundo)

    def f(m):
        return elc.calcular_qx(params_brinquedo, m[:, 0], m[:, 1])

    masker = shap.maskers.Independent(fundo, max_samples=len(fundo))
    biblioteca = shap.explainers.Exact(f, masker)(pontos, silent=True)
    assert np.allclose(nosso["valores"], biblioteca.values, atol=1e-12)
    assert nosso["valor_base"] == pytest.approx(float(np.mean(biblioteca.base_values)))


# ---------------------------------------------------------------------------
# Relatório JSON (contrato v1.0.0) e execução completa
# ---------------------------------------------------------------------------

def test_execucao_brinquedo_gera_relatorio_valido(params_brinquedo, tmp_path):
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert relatorio["status"] == "APROVADO"
    gravado = json.loads((tmp_path / "relatorio_explicabilidade_lee_carter.json").read_text("utf-8"))
    elc.validar_relatorio(gravado)
    for nome in gravado["graficos"]:
        assert (tmp_path / nome).stat().st_size > 0


def test_execucao_implausivel_e_bloqueada(params_brinquedo, tmp_path):
    params_brinquedo["alpha_x"][4] = -9.0  # idade 32 com mortalidade muito menor
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert relatorio["status"] == "BLOQUEADO"
    assert relatorio["ale"] is None and relatorio["shap"] is None
    assert relatorio["graficos"] == []
    assert not list(tmp_path.glob("*.png"))


def test_bloqueado_apaga_graficos_da_rodada_anterior(params_brinquedo, tmp_path):
    assert elc.executar(params_brinquedo, pasta_saida=tmp_path)["status"] == "APROVADO"
    assert list(tmp_path.glob("*.png"))
    implausivel = copy.deepcopy(params_brinquedo)
    implausivel["alpha_x"][4] = -9.0
    assert elc.executar(implausivel, pasta_saida=tmp_path)["status"] == "BLOQUEADO"
    assert not list(tmp_path.glob("*.png"))


def test_graficos_gerados_sao_os_esperados(params_brinquedo, tmp_path):
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    assert sorted(relatorio["graficos"]) == sorted(elc.NOMES_GRAFICOS)


def test_schema_rejeita_relatorio_sem_campo(params_brinquedo, tmp_path):
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    incompleto = copy.deepcopy(relatorio)
    del incompleto["nota_de_uso"]
    with pytest.raises(jsonschema.ValidationError):
        elc.validar_relatorio(incompleto)


def test_schema_rejeita_aprovado_com_checagem_falha(params_brinquedo, tmp_path):
    relatorio = elc.executar(params_brinquedo, pasta_saida=tmp_path)
    adulterado = copy.deepcopy(relatorio)
    adulterado["plausibilidade"][0]["aprovado"] = False
    with pytest.raises(jsonschema.ValidationError):
        elc.validar_relatorio(adulterado)


# ---------------------------------------------------------------------------
# Integração com o contrato real do Passo 6 (série IBGE 2015-2024)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def params_reais():
    return elc.carregar_parametros()


def test_integracao_contrato_real_gera_relatorio_aprovado(params_reais, tmp_path):
    relatorio = elc.executar(params_reais, pasta_saida=tmp_path)
    elc.validar_relatorio(relatorio)
    assert relatorio["status"] == "APROVADO", relatorio["plausibilidade"]
    assert relatorio["parametros"]["origem_dados"] == params_reais["origem_dados"]


def test_integracao_idade_explica_mais_que_ano(params_reais):
    """Plausibilidade de sinal: na faixa 20-70, a idade pesa mais que o calendário."""
    anos = elc.anos_analisados(params_reais)
    resumo = elc.resumir_shap(elc.calcular_shap(params_reais, anos))
    imp = resumo["importancia_media_abs"]
    assert imp["idade"] > imp["ano"]


def test_integracao_ale_idade_cresce_a_partir_da_idade_minima(params_reais):
    anos = elc.anos_analisados(params_reais)
    pontos = elc.calcular_ale(params_reais, anos)["idade"]
    efeito = [p["efeito"] for p in pontos if p["valor"] >= elc.IDADE_MINIMA_MONOTONIA]
    assert all(b > a for a, b in zip(efeito, efeito[1:]))
