"""Núcleo puro do contrato 0.1.0; taxas calculadas como inteiros de 10^-8."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import re

CONTRACT_VERSION = GENERATOR_VERSION = SCENARIO_VERSION = "0.1.0"
VARIABLES = ("inflation", "discount_rate", "salary_growth", "asset_return")
SCENARIOS = ("base", "adverse", "favorable")
SCALE = 100_000_000


class ScenarioError(ValueError):
    def __init__(self, code, field, message):
        super().__init__(message)
        self.code, self.field, self.message = code, field, message

    def as_dict(self):
        return {"error": {"code": self.code, "field": self.field, "message": self.message}}


def fail(code, field, message):
    raise ScenarioError(code, field, message)


def loads_decimal(text):
    """Lê números fracionários sem passar por float; rejeita JSON ambíguo."""
    def constant(_):
        fail("INVALID_JSON", None, "JSON não aceita NaN ou infinito.")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail("INVALID_JSON", key, "Chave JSON duplicada.")
            result[key] = value
        return result

    try:
        return json.loads(text, parse_float=Decimal, parse_constant=constant,
                          object_pairs_hook=pairs)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ScenarioError):
            raise
        fail("INVALID_JSON", None, "Documento JSON inválido.")


def dumps_decimal(value):
    """Serializa Decimal como número JSON exato, sem conversão para float."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            fail("INVALID_JSON", None, "Número não finito.")
        return format(value, "f")
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            fail("INVALID_JSON", None, "Chaves devem ser strings.")
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + dumps_decimal(v)
                              for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(dumps_decimal, value)) + "]"
    if isinstance(value, float):
        fail("INVALID_JSON", None, "Use Decimal em vez de float.")
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def obj(value, required, optional, field, code):
    if not isinstance(value, dict):
        fail(code, field, "Esperado objeto.")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        fail(code, field, f"Campos ausentes: {sorted(missing)}; desconhecidos: {sorted(extra)}.")


def string(value, field, code):
    if not isinstance(value, str) or not value.strip():
        fail(code, field, "Esperada string não vazia.")


def version(value, field, code):
    string(value, field, code)
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        fail(code, field, "Versão deve ter formato MAJOR.MINOR.PATCH.")


def valid_date(value, field, code):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        fail(code, field, "Data deve ter formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(code, field, "Data inválida.")


def scaled(value, field, code, rate=False):
    if type(value) not in (int, Decimal):
        fail(code, field, "Esperado número decimal exato; use loads_decimal para ler JSON.")
    value = Decimal(value)
    if not value.is_finite() or (rate and value <= -1):
        fail(code, field, "A taxa deve ser finita e maior que -1." if rate else "Ajuste deve ser finito.")
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    if not digits:
        return 0
    if exponent < -8:
        fail(code, field, "Máximo de oito casas decimais, sem arredondamento.")
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    return (-1 if sign else 1) * coefficient * 10 ** (exponent + 8)


def decimal_rate(value):
    # Construção textual evita arredondamento pelo contexto global de Decimal.
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), SCALE)
    return Decimal(f"{sign}{whole}.{fraction:08d}")


def validate_request(request):
    code = "INVALID_REQUEST"
    required = {"contract_version", "base_date", "horizon_years", "unit", "rate_basis",
                "assumption_set_id", "assumption_version", "ruleset_id", "ruleset_version",
                "assumptions", "sources"}
    obj(request, required, (), None, code)
    if request["contract_version"] != CONTRACT_VERSION:
        fail("UNSUPPORTED_CONTRACT_VERSION", "contract_version", "Versão de contrato não suportada.")
    for field in ("assumption_set_id", "ruleset_id"):
        string(request[field], field, code)
    for field in ("assumption_version", "ruleset_version"):
        version(request[field], field, code)
    for field, expected in (("unit", "annual_decimal"), ("rate_basis", "nominal")):
        if request[field] != expected:
            fail(code, field, f"Esperado {expected}.")
    start = valid_date(request["base_date"], "base_date", code)
    horizon = request["horizon_years"]
    if type(horizon) is not int or not 1 <= horizon <= 120:
        fail(code, "horizon_years", "Horizonte deve ser inteiro entre 1 e 120.")
    if start.year + horizon > 9999:
        fail(code, "horizon_years", "Data final excede o calendário suportado (ano 9999).")
    obj(request["assumptions"], VARIABLES[:2], VARIABLES[2:], "assumptions", "INVALID_ASSUMPTION")
    rates = {key: scaled(request["assumptions"][key], f"assumptions.{key}", "INVALID_ASSUMPTION", True)
             for key in VARIABLES if key in request["assumptions"]}
    obj(request["sources"], rates.keys(), (), "sources", code)
    source_fields = {"kind", "reference", "reference_version", "description", "rationale",
                     "responsible", "reference_date"}
    for key, source in request["sources"].items():
        path = f"sources.{key}"
        obj(source, source_fields, (), path, code)
        for field in source_fields:
            string(source[field], f"{path}.{field}", code)
        if source["kind"] not in ("synthetic", "external"):
            fail(code, f"{path}.kind", "Origem deve ser synthetic ou external.")
        valid_date(source["reference_date"], f"{path}.reference_date", code)
    return start, horizon, rates


def validate_rules(rules, request, rates):
    code = "INVALID_RULESET"
    obj(rules, {"ruleset_id", "ruleset_version", "description", "responsible", "reference", "scenarios"}, (), None, code)
    for field in ("ruleset_id", "description", "responsible", "reference"):
        string(rules[field], field, code)
    version(rules["ruleset_version"], "ruleset_version", code)
    if any(rules[field] != request[field] for field in ("ruleset_id", "ruleset_version")):
        fail("RULESET_NOT_FOUND", "ruleset_id", "Configuração fornecida não corresponde ao ID e versão solicitados.")
    obj(rules["scenarios"], SCENARIOS, (), "scenarios", code)
    adjusted = {}
    for key in SCENARIOS:
        scenario = rules["scenarios"][key]
        path = f"scenarios.{key}"
        obj(scenario, {"label", "rationale", "target_metric", "adjustments"}, (), path, code)
        for field in ("label", "rationale", "target_metric"):
            string(scenario[field], f"{path}.{field}", code)
        obj(scenario["adjustments"], rates.keys(), set(VARIABLES) - rates.keys(), f"{path}.adjustments", code)
        adjustments = {v: scaled(n, f"{path}.adjustments.{v}", code)
                       for v, n in scenario["adjustments"].items()}
        if key == "base" and any(adjustments.values()):
            fail(code, f"{path}.adjustments", "Base exige ajustes zero.")
        adjusted[key] = {}
        for variable, rate in rates.items():
            result = rate + adjustments[variable]
            if result <= -SCALE:
                fail("INVALID_SCENARIO", f"{path}.variables.{variable}", "Taxa após ajuste deve ser maior que -1.")
            adjusted[key][variable] = decimal_rate(result)
    return adjusted


def anniversary(start, offset):
    year = start.year + offset
    try:
        return start.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def generate_scenarios(request, rules):
    """Produz conteúdo econômico reproduzível, sem I/O, IDs ou horário.

    A camada futura de aplicação acrescentará IDs, horário e status apenas após
    persistência. Esta função não representa uma resposta HTTP de execução salva.
    """
    start, horizon, rates = validate_request(request)
    adjusted = validate_rules(rules, request, rates)
    scenarios = []
    for key in SCENARIOS:
        scenarios.append({
            "scenario_key": key, "label": rules["scenarios"][key]["label"],
            "scenario_version": SCENARIO_VERSION, "base_date": start.isoformat(),
            "horizon_years": horizon, "unit": request["unit"], "rate_basis": request["rate_basis"],
            "values": [{"period": i, "period_start": anniversary(start, i - 1).isoformat(),
                        "period_end": anniversary(start, i).isoformat(),
                        "variables": adjusted[key].copy()} for i in range(1, horizon + 1)]})
    return {"contract_version": CONTRACT_VERSION, "generator_version": GENERATOR_VERSION,
            "request_snapshot": deepcopy(request), "ruleset_snapshot": deepcopy(rules),
            "scenarios": scenarios}
