"""
Gerador de massa sintética — Tribo 3

Gera participantes, eventos, exposição e contribuições/benefícios, injeta
as imperfeições controladas do §5.1 e registra o gabarito em
gabarito.registro_erro_injetado.

A massa é sintética por necessidade (não existe base pública de
participante de fundo de previdência, e o §5.2 precisa de gabarito
conhecido para medir precision/recall), mas a trajetória de cada
participante é simulada ano a ano com qx real por idade/sexo — ver
calibracao.py.

O destino é o schema `staging` (todo campo TEXT NULL), não as tabelas
tipadas: é o que permite gravar nulo em campo obrigatório e data em
formato trocado, como o §5.1 exige. Quem promove staging -> tabelas
finais é o pipeline_qualidade.py.

Uso:
    python gerar_dataset.py --n-participantes 300 --seed 42

Mesma seed = mesmo dataset (§6, reprodutibilidade).
"""

import argparse
import random
import uuid
from datetime import date, timedelta

import psycopg2.extras
from faker import Faker

from calibracao import (IDADE_APOSENTADORIA, TAXA_APOSENTADORIA_ANUAL,
                        TAXA_DESLIGAMENTO_ANUAL, TAXA_INVALIDEZ_ANUAL,
                        carregar_tabua_qx, descrever_calibracao, qx_anual)
from db import conectar
from dominio import (PLANO_TIPOS, SEXOS, SUBMASSAS, TIPOS_ERRO, novo_uuid,
                     to_text)
from injetores import INJETORES

# ---------- parâmetros de geração (declarados no data card, §6) ----------

# Faixa de idade na ENTRADA do plano, não na data de referência: a idade
# atual e o status atual emergem da simulação ano a ano, não são sorteados.
IDADE_INGRESSO_MIN = 18
IDADE_INGRESSO_MAX = 55

# Quantos anos atrás o ingresso mais antigo pode ter acontecido. Precisa
# ser longo: com histórias curtas, quase ninguém morre (qx de adulto é da
# ordem de 0,2%/ano) e o Passo 5 ficaria sem óbito para calcular A/E.
ANOS_MAX_DE_PLANO = 30

# Só desligado e óbito encerram o vínculo. Aposentado e pensionista
# continuam no plano — o §3.1 define data_desligamento como "preenchida
# se houver desligamento", e preenchê-la para aposentados truncaria a
# exposição ao risco e enviesaria o qx.
STATUS_QUE_DESLIGAM = ("desligado", "obito")

STATUS_PARA_EVENTO = {
    "obito": "obito",
    "aposentado": "aposentadoria",
    "desligado": "desligamento",
    "pensionista": "invalidez",  # simplificação: pensionista via invalidez
}

TAXA_INJECAO = 0.05  # fração dos participantes que recebe alguma imperfeição
MESES_CONTRIBUICAO = 6

# Data-base do lote. Fica num global porque atravessa quase toda função
# de geração. O §6 exige "mesma seed = mesmo resultado": com date.today()
# implícito, rodar amanhã produziria um dataset diferente com a mesma
# seed, então a data entra como parâmetro explícito (--data-referencia).
DATA_REFERENCIA = date.today()


def simular_trajetoria(participante, tabua, rng):
    """Simula ano a ano, do ingresso até a data de referência.

    Devolve (status_final, data_mudanca, linhas_de_exposicao).

    O sorteio é por ano civil, com o qx da idade daquele ano — é o ponto
    inteiro do pivô para dado real: um sorteio único de status com peso
    global não tem como respeitar a idade, e o qx real varia duas ordens
    de grandeza entre os 25 e os 85 anos.

    Encaixa no desenho que já existia: `exposicao` sempre foi uma linha
    por ano civil, então a simulação produz exatamente essas linhas como
    subproduto, em vez de derivá-las depois de um status já decidido.

    Ordem dos decrementos dentro do ano: óbito primeiro (é o único que o
    Passo 5 mede), depois os que só valem para quem está ativo.
    Aposentadoria e invalidez mudam o estado mas NÃO encerram a
    exposição — quem se aposenta continua exposto ao risco de morte.
    """
    nascimento = participante["data_nascimento"]
    ingresso = participante["data_ingresso"]
    sexo = participante["sexo"]

    status = "ativo"
    data_mudanca = None
    linhas = []

    for ano in range(ingresso.year, DATA_REFERENCIA.year + 1):
        janela_inicio = max(ingresso, date(ano, 1, 1))
        janela_fim = min(DATA_REFERENCIA, date(ano, 12, 31))
        if janela_fim < janela_inicio:
            continue

        # Idade e fração de ano considerando a janela inteira — é sobre
        # ela que o risco do ano é sorteado.
        idade = _idade_em(nascimento, janela_fim)
        tempo = _fracao_do_ano(janela_inicio, janela_fim)

        # Ano parcial (ingresso no meio do ano, ou o ano corrente) expõe
        # menos ao risco: escalar as taxas anuais pela fração exposta.
        morreu = rng.random() < qx_anual(tabua, idade, sexo) * tempo

        tipo_saida = "censura"
        if morreu:
            tipo_saida = "obito"
            status = "obito"
            data_mudanca = _data_no_intervalo(janela_inicio, janela_fim, rng)
        elif status == "ativo":
            if rng.random() < TAXA_DESLIGAMENTO_ANUAL * tempo:
                tipo_saida = "saida_estudo"
                status = "desligado"
                data_mudanca = _data_no_intervalo(janela_inicio, janela_fim, rng)
            elif (idade >= IDADE_APOSENTADORIA[sexo]
                  and rng.random() < TAXA_APOSENTADORIA_ANUAL * tempo):
                status = "aposentado"
                data_mudanca = _data_no_intervalo(janela_inicio, janela_fim, rng)
            elif rng.random() < TAXA_INVALIDEZ_ANUAL * tempo:
                status = "pensionista"
                data_mudanca = _data_no_intervalo(janela_inicio, janela_fim, rng)

        # Saída terminal no meio do ano trunca a exposição na data da
        # saída: contar o ano civil inteiro inflaria o denominador do qx
        # e puxaria o A/E do Passo 5 para baixo justamente nas idades
        # onde há óbito. Aposentadoria e invalidez não truncam nada —
        # quem se aposenta segue exposto até o fim do ano.
        if status in STATUS_QUE_DESLIGAM:
            janela_fim = data_mudanca
            idade = _idade_em(nascimento, janela_fim)
            tempo = _fracao_do_ano(janela_inicio, janela_fim)

        linhas.append({
            "exposicao_id": novo_uuid(rng),
            "participante_id": participante["participante_id"],
            "submassa": participante["submassa"],
            "idade_exata": round(idade, 3),
            "ano_calendario": ano,
            "tempo_exposto": round(tempo, 5),
            "tipo_saida": tipo_saida,
            "data_base": janela_fim,
        })

        if status in STATUS_QUE_DESLIGAM:
            break

    return status, data_mudanca, linhas


def _data_no_intervalo(inicio, fim, rng):
    return inicio + timedelta(days=rng.randint(0, (fim - inicio).days))


def _idade_em(nascimento, data_base):
    """Idade exata na data-base, calculada de fato (não ano - ano)."""
    return (data_base - nascimento).days / 365.25


def _fracao_do_ano(inicio, fim):
    """Fração de ano exposta na janela, inclusiva nas duas pontas."""
    return min(((fim - inicio).days + 1) / 365.25, 1.0)


def gerar_participante(fake, rng, tabua):
    """Devolve (participante, linhas_de_exposicao).

    Sorteia a idade de ENTRADA e a data de ingresso; o nascimento sai
    dessas duas. A idade atual e o status atual não são sorteados — saem
    da simulação, e é isso que faz a massa refletir a mortalidade real.
    """
    ingresso = fake.date_between_dates(
        date_start=DATA_REFERENCIA - timedelta(days=ANOS_MAX_DE_PLANO * 365),
        date_end=DATA_REFERENCIA - timedelta(days=30),
    )
    idade_ingresso = rng.randint(IDADE_INGRESSO_MIN, IDADE_INGRESSO_MAX)
    nascimento = ingresso - timedelta(days=round(idade_ingresso * 365.25))

    participante = {
        "participante_id": novo_uuid(rng),
        "cpf_sintetico": fake.cpf().replace(".", "").replace("-", ""),
        "plano_tipo": rng.choice(PLANO_TIPOS),
        "submassa": rng.choice(SUBMASSAS),
        "sexo": rng.choice(SEXOS),
        "data_nascimento": nascimento,
        "data_ingresso": ingresso,
        "data_evento_conhecimento": ingresso + timedelta(days=rng.randint(1, 5)),
        "data_vigencia_inicio": ingresso,
        "data_vigencia_fim": None,
        "versao_registro": 1,
    }

    status, data_mudanca, exposicoes = simular_trajetoria(participante, tabua, rng)

    participante["status_atual"] = status
    # data_desligamento só para quem de fato desliga (ver nota acima).
    participante["data_desligamento"] = (
        data_mudanca if status in STATUS_QUE_DESLIGAM else None
    )
    # Campo interno, não persistido: só orienta o evento.
    participante["_data_mudanca"] = data_mudanca

    return participante, exposicoes


def gerar_evento(participante, rng):
    tipo = STATUS_PARA_EVENTO.get(participante["status_atual"])
    if tipo is None:
        return None
    data_evento = participante["_data_mudanca"]
    return {
        "evento_id": novo_uuid(rng),
        "participante_id": participante["participante_id"],
        "tipo_evento": tipo,
        "data_evento": data_evento,
        "data_conhecimento": data_evento + timedelta(days=rng.randint(1, 10)),
        "fonte": "gerador_sintetico_v1",
    }


def _fim_da_exposicao(participante):
    """Até quando o participante está exposto ao risco.

    Desligamento e óbito encerram; aposentadoria e invalidez não — quem
    se aposenta continua exposto ao risco de morte dentro do plano.
    """
    if participante["status_atual"] in STATUS_QUE_DESLIGAM:
        return participante["data_desligamento"]
    return DATA_REFERENCIA


def gerar_contribuicoes(participante, rng):
    """Até 6 competências mensais antes do fim do vínculo."""
    linhas = []
    fim = _fim_da_exposicao(participante)
    em_beneficio = participante["status_atual"] in ("aposentado", "pensionista")
    ano, mes = fim.year, fim.month

    for _ in range(MESES_CONTRIBUICAO):
        if date(ano, mes, 1) < participante["data_ingresso"].replace(day=1):
            break
        linhas.append({
            "id": novo_uuid(rng),
            "participante_id": participante["participante_id"],
            "competencia": date(ano, mes, 1),
            "valor_contribuicao": round(rng.uniform(200, 2500), 2),
            "valor_beneficio": round(rng.uniform(1000, 5000), 2) if em_beneficio else None,
            "status_pagamento": rng.choices(
                ["em_dia", "atraso", "quitado"], weights=[0.8, 0.15, 0.05], k=1
            )[0],
        })
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    return linhas


def injetar_imperfeicoes(rng, dados, n_alvos):
    """Aplica n_alvos imperfeições entre os 9 tipos do §5.1.

    A primeira rodada percorre os 9 tipos uma vez cada, em ordem
    embaralhada: com sorteio puro e poucos alvos, algum tipo sairia com
    zero injeções e a regra correspondente ficaria sem nada para
    detectar — o precision/recall dele viraria NaN no relatório do §5.2.
    Os alvos restantes são sorteados livremente.

    Quando o tipo escolhido não tem alvo disponível no lote, tenta os
    demais, para que a taxa de injeção declarada valha de fato.
    """
    gabarito = []
    usados = set()

    ordem = rng.sample(TIPOS_ERRO, k=len(TIPOS_ERRO))
    for i in range(max(n_alvos, len(TIPOS_ERRO))):
        if i < len(ordem):
            preferidos = [ordem[i]]
        else:
            preferidos = rng.sample(TIPOS_ERRO, k=len(TIPOS_ERRO))
        for tipo in preferidos + TIPOS_ERRO:
            linhas = INJETORES[tipo](rng, dados, usados)
            if linhas:
                gabarito.extend(linhas)
                break
    return gabarito


# ---------- escrita no staging ----------

COLUNAS_STAGING = {
    "staging.participante": [
        "participante_id", "cpf_sintetico", "plano_tipo", "submassa", "sexo",
        "data_nascimento", "data_ingresso", "data_desligamento", "status_atual",
        "data_evento_conhecimento", "data_vigencia_inicio", "data_vigencia_fim",
        "versao_registro",
    ],
    "staging.evento": [
        "evento_id", "participante_id", "tipo_evento", "data_evento",
        "data_conhecimento", "fonte",
    ],
    "staging.exposicao": [
        "exposicao_id", "participante_id", "submassa", "idade_exata",
        "ano_calendario", "tempo_exposto", "tipo_saida", "data_base",
    ],
    "staging.contribuicao_beneficio": [
        "id", "participante_id", "competencia", "valor_contribuicao",
        "valor_beneficio", "status_pagamento",
    ],
}


def inserir_staging(cur, tabela, registros, lote_id):
    if not registros:
        return
    colunas = COLUNAS_STAGING[tabela]
    lista = ", ".join(["lote_id"] + colunas)
    valores = [
        tuple([lote_id] + [to_text(r[c]) for c in colunas]) for r in registros
    ]
    psycopg2.extras.execute_values(
        cur, f"INSERT INTO {tabela} ({lista}) VALUES %s", valores
    )


def resumir_massa(dados):
    """Distribuição realizada — a verificação barata de que a calibração pegou.

    O status não é mais sorteado, então a única forma de saber o que saiu
    é olhar o resultado. Zero óbito significa lote pequeno demais para o
    Passo 5 calcular A/E: subir --n-participantes.
    """
    por_status = {}
    for p in dados["participantes"]:
        por_status[p["status_atual"]] = por_status.get(p["status_atual"], 0) + 1

    obitos = sum(1 for e in dados["exposicoes"] if e["tipo_saida"] == "obito")
    expostos = sum(float(e["tempo_exposto"]) for e in dados["exposicoes"])
    idades = [float(e["idade_exata"]) for e in dados["exposicoes"]]

    linhas = ["Massa realizada (emerge da simulação, não é sorteada):"]
    total = len(dados["participantes"])
    for status, n in sorted(por_status.items(), key=lambda kv: -kv[1]):
        linhas.append(f"  {status:<12} {n:>5}  ({n / total:.1%})")
    linhas.append(f"  idade na exposição: {min(idades):.0f} a {max(idades):.0f} anos")
    linhas.append(f"  {obitos} óbitos em {expostos:.1f} anos-pessoa "
                  f"— qx bruto agregado {obitos / expostos:.5f}"
                  if expostos else "  sem exposição gerada")
    if not obitos:
        linhas.append("  ATENÇÃO: nenhum óbito no lote — o Passo 5 fica sem "
                      "numerador para o A/E. Subir --n-participantes.")
    return "\n".join(linhas)


def main():
    global DATA_REFERENCIA

    parser = argparse.ArgumentParser()
    parser.add_argument("--n-participantes", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-referencia", type=date.fromisoformat,
                        default=DATA_REFERENCIA,
                        help="data-base do lote (ISO). Fixe para reproduzir "
                             "um dataset antigo byte a byte.")
    args = parser.parse_args()
    DATA_REFERENCIA = args.data_referencia

    Faker.seed(args.seed)
    rng = random.Random(args.seed)
    fake = Faker("pt_BR")

    # Uma leitura só dos xlsx do IBGE para o lote inteiro.
    tabua = carregar_tabua_qx()

    dados = {"participantes": [], "eventos": [], "exposicoes": [], "contribuicoes": []}

    for _ in range(args.n_participantes):
        p, exposicoes = gerar_participante(fake, rng, tabua)
        dados["participantes"].append(p)

        ev = gerar_evento(p, rng)
        if ev:
            dados["eventos"].append(ev)
        dados["exposicoes"].extend(exposicoes)
        dados["contribuicoes"].extend(gerar_contribuicoes(p, rng))

    # Injeção depois da geração completa: os injetores de duplicidade e
    # órfão precisam do lote inteiro montado para escolher alvos.
    n_alvos = round(args.n_participantes * TAXA_INJECAO)
    gabarito = injetar_imperfeicoes(rng, dados, n_alvos)

    lote_id = str(uuid.uuid4())
    conn = conectar()
    cur = conn.cursor()

    inserir_staging(cur, "staging.participante", dados["participantes"], lote_id)
    inserir_staging(cur, "staging.evento", dados["eventos"], lote_id)
    inserir_staging(cur, "staging.exposicao", dados["exposicoes"], lote_id)
    inserir_staging(cur, "staging.contribuicao_beneficio", dados["contribuicoes"], lote_id)

    if gabarito:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO gabarito.registro_erro_injetado (tabela_alvo, registro_id,
                campo_afetado, tipo_erro, valor_correto_original, valor_injetado)
            VALUES %s
        """, [(g["tabela_alvo"], g["registro_id"], g["campo_afetado"], g["tipo_erro"],
               g["valor_correto_original"], g["valor_injetado"]) for g in gabarito])

    conn.commit()
    cur.close()
    conn.close()

    por_tipo = {}
    for g in gabarito:
        por_tipo[g["tipo_erro"]] = por_tipo.get(g["tipo_erro"], 0) + 1

    print(f"Lote {lote_id} gravado em staging "
          f"(seed={args.seed}, data_referencia={DATA_REFERENCIA}):")
    print(f"  {len(dados['participantes'])} participantes, {len(dados['eventos'])} eventos, "
          f"{len(dados['exposicoes'])} exposições, {len(dados['contribuicoes'])} contribuições")
    print(f"  {len(gabarito)} imperfeições injetadas: "
          + ", ".join(f"{t}={n}" for t, n in sorted(por_tipo.items())))
    print()
    print(descrever_calibracao())
    print()
    print(resumir_massa(dados))


if __name__ == "__main__":
    main()
