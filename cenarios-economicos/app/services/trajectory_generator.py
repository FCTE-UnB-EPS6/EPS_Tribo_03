"""Gerador puro de cenários para trajetórias econômicas do contrato 0.2.0."""

from copy import deepcopy

from app.contracts.trajectory import (
    TrajectoryContractError,
    validate_trajectory_request,
)
from app.services.scenario_generator import (
    SCENARIOS,
    VARIABLES,
    SCALE,
    ScenarioError,
    decimal_rate,
    fail,
    obj,
    scaled,
    string,
    version,
)


GENERATOR_VERSION = SCENARIO_VERSION = "0.2.0"


def validate_trajectory(request):
    """Converte erros do contrato isolado para o envelope comum da aplicação."""
    try:
        return validate_trajectory_request(request)
    except TrajectoryContractError as exc:
        raise ScenarioError(exc.code, exc.field, exc.message) from exc


def _validate_rules(rules, request, variable_names):
    code = "INVALID_RULESET"
    obj(
        rules,
        {
            "ruleset_id",
            "ruleset_version",
            "description",
            "responsible",
            "reference",
            "scenarios",
        },
        (),
        None,
        code,
    )
    for field in ("ruleset_id", "description", "responsible", "reference"):
        string(rules[field], field, code)
    version(rules["ruleset_version"], "ruleset_version", code)
    if any(
        rules[field] != request[field]
        for field in ("ruleset_id", "ruleset_version")
    ):
        fail(
            "RULESET_NOT_FOUND",
            "ruleset_id",
            "Configuração fornecida não corresponde ao ID e versão solicitados.",
        )
    obj(rules["scenarios"], SCENARIOS, (), "scenarios", code)
    adjustments = {}
    for scenario_key in SCENARIOS:
        scenario = rules["scenarios"][scenario_key]
        path = f"scenarios.{scenario_key}"
        obj(
            scenario,
            {"label", "rationale", "target_metric", "adjustments"},
            (),
            path,
            code,
        )
        for field in ("label", "rationale", "target_metric"):
            string(scenario[field], f"{path}.{field}", code)
        obj(
            scenario["adjustments"],
            variable_names,
            set(VARIABLES) - set(variable_names),
            f"{path}.adjustments",
            code,
        )
        adjustments[scenario_key] = {
            variable: scaled(value, f"{path}.adjustments.{variable}", code)
            for variable, value in scenario["adjustments"].items()
            if variable in variable_names
        }
        if scenario_key == "base" and any(adjustments[scenario_key].values()):
            fail(code, f"{path}.adjustments", "Base exige ajustes zero.")
    return adjustments


def generate_trajectory_scenarios(request, rules):
    """Aplica choques aditivos a cada período de uma trajetória validada."""
    validated = validate_trajectory(request)
    periods = validated["trajectory"]["periods"]
    variable_names = tuple(
        variable for variable in VARIABLES if variable in periods[0]["variables"]
    )
    adjustments = _validate_rules(rules, validated, variable_names)
    scenarios = []
    for scenario_key in SCENARIOS:
        values = []
        for period in periods:
            variables = {}
            for variable in variable_names:
                base = scaled(
                    period["variables"][variable]["value"],
                    f"trajectory.periods.{period['period'] - 1}.variables.{variable}.value",
                    "INVALID_TRAJECTORY_VALUE",
                    True,
                )
                result = base + adjustments[scenario_key][variable]
                if result <= -SCALE:
                    fail(
                        "INVALID_SCENARIO",
                        f"scenarios.{scenario_key}.periods.{period['period'] - 1}.variables.{variable}",
                        "Taxa após ajuste deve ser maior que -1.",
                    )
                variables[variable] = decimal_rate(result)
            values.append(
                {
                    "period": period["period"],
                    "period_start": period["period_start"],
                    "period_end": period["period_end"],
                    "variables": variables,
                }
            )
        scenarios.append(
            {
                "scenario_key": scenario_key,
                "label": rules["scenarios"][scenario_key]["label"],
                "scenario_version": SCENARIO_VERSION,
                "base_date": validated["base_date"],
                "horizon_years": validated["horizon_years"],
                "unit": validated["unit"],
                "rate_basis": validated["rate_basis"],
                "trajectory_id": validated["trajectory"]["trajectory_id"],
                "trajectory_version": validated["trajectory"]["trajectory_version"],
                "values": values,
            }
        )
    return {
        "contract_version": validated["contract_version"],
        "generator_version": GENERATOR_VERSION,
        "request_snapshot": deepcopy(validated),
        "ruleset_snapshot": deepcopy(rules),
        "scenarios": scenarios,
    }
