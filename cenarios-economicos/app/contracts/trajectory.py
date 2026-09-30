"""Contrato puro 0.2.0 para trajetorias economicas anuais variaveis."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import re


TRAJECTORY_CONTRACT_VERSION = "0.2.0"
SUPPORTED_ARTIFACT_SCHEMA_VERSION = "1.0.0"
SUPPORTED_TRANSFORMATION_POLICY_VERSION = "0.1.0"
MAX_HORIZON_YEARS = 120
MAX_CALIBRATION_STALENESS_DAYS = 7
VARIABLES = ("inflation", "discount_rate", "salary_growth", "asset_return")
REQUIRED_VARIABLES = ("inflation", "discount_rate")
OPTIONAL_VARIABLES = ("salary_growth", "asset_return")
PURPOSES = ("projection", "backtest")
STATUSES = ("observed", "market_implied", "modeled")
MEASURES = (
    "effective_return",
    "annual_rate_level",
    "forward_rate",
    "level_change",
    "modeled_rate",
)
SOURCE_KINDS = ("calibration_artifact", "model")
VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
)
IDENTIFIER_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class TrajectoryContractError(ValueError):
    """Erro estruturado do contrato de trajetoria."""

    def __init__(self, code, field, message):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def as_dict(self):
        return {
            "error": {
                "code": self.code,
                "field": self.field,
                "message": self.message,
            }
        }


def _fail(code, field, message):
    raise TrajectoryContractError(code, field, message)


def _object(value, required, optional, field, code):
    if not isinstance(value, dict):
        _fail(code, field, "Esperado objeto.")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        _fail(
            code,
            field,
            f"Campos ausentes: {sorted(missing)}; desconhecidos: {sorted(extra)}.",
        )


def _string(value, field, code):
    if not isinstance(value, str) or not value.strip():
        _fail(code, field, "Esperada string nao vazia.")


def _identifier(value, field, code):
    _string(value, field, code)
    if not IDENTIFIER_PATTERN.fullmatch(value):
        _fail(code, field, "Use letras minusculas, numeros e hifens.")


def _version(value, field, code):
    _string(value, field, code)
    if not VERSION_PATTERN.fullmatch(value):
        _fail(code, field, "Versao deve ter formato MAJOR.MINOR.PATCH.")


def _valid_date(value, field, code):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
    ):
        _fail(code, field, "Data deve ter formato YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _fail(code, field, "Data invalida.")
    return parsed


def _rate(value, field):
    code = "INVALID_TRAJECTORY_VALUE"
    if type(value) not in (int, Decimal):
        _fail(
            code,
            field,
            "Esperado numero decimal exato; strings, booleanos e float nao sao aceitos.",
        )
    value = Decimal(value)
    if not value.is_finite() or value <= -1:
        _fail(code, field, "A taxa deve ser finita e maior que -1.")
    _, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    if digits and exponent < -8:
        _fail(code, field, "A taxa aceita no maximo oito casas decimais.")


def _anniversary(start, offset):
    year = start.year + offset
    try:
        return start.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def _json_pointer(value, field, code):
    _string(value, field, code)
    if not value.startswith("/"):
        _fail(code, field, "Esperado JSON Pointer absoluto iniciado por '/'.")
    index = 0
    while index < len(value):
        if value[index] == "~":
            if index + 1 >= len(value) or value[index + 1] not in "01":
                _fail(code, field, "JSON Pointer contem escape invalido.")
            index += 2
        else:
            index += 1


def _validate_calibration(calibration, base_date, purpose):
    code = "INVALID_CALIBRATION_REFERENCE"
    field = "calibration"
    required = {
        "artifact_id",
        "calibration_id",
        "calibration_version",
        "artifact_schema_version",
        "transformation_policy_version",
        "cutoff_date",
        "sha256",
        "scope",
    }
    _object(calibration, required, (), field, code)
    _identifier(calibration["calibration_id"], f"{field}.calibration_id", code)
    _version(calibration["calibration_version"], f"{field}.calibration_version", code)
    expected_artifact_id = (
        f"{calibration['calibration_id']}@{calibration['calibration_version']}"
    )
    if calibration["artifact_id"] != expected_artifact_id:
        _fail(
            code,
            f"{field}.artifact_id",
            "artifact_id deve combinar calibration_id e calibration_version.",
        )
    if calibration["artifact_schema_version"] != SUPPORTED_ARTIFACT_SCHEMA_VERSION:
        _fail(
            code,
            f"{field}.artifact_schema_version",
            "Versao do artefato de calibracao nao suportada.",
        )
    if (
        calibration["transformation_policy_version"]
        != SUPPORTED_TRANSFORMATION_POLICY_VERSION
    ):
        _fail(
            code,
            f"{field}.transformation_policy_version",
            "Versao da politica de transformacao nao suportada.",
        )
    if not isinstance(calibration["sha256"], str) or not SHA256_PATTERN.fullmatch(
        calibration["sha256"]
    ):
        _fail(code, f"{field}.sha256", "Esperado SHA-256 hexadecimal em minusculas.")
    if calibration["scope"] not in (
        "historical_only",
        "historical_and_market_implied",
    ):
        _fail(code, f"{field}.scope", "Escopo de calibracao desconhecido.")
    cutoff = _valid_date(calibration["cutoff_date"], f"{field}.cutoff_date", code)
    if purpose == "projection":
        staleness = (base_date - cutoff).days
        if not 0 <= staleness <= MAX_CALIBRATION_STALENESS_DAYS:
            _fail(
                code,
                f"{field}.cutoff_date",
                "Projecao exige calibracao entre zero e sete dias antes da data-base.",
            )
    return cutoff


def _validate_source(source, variable, status, source_metric, calibration,
                     base_date, cutoff, purpose, field):
    code = "INVALID_TRAJECTORY_VALUE"
    required = {
        "kind",
        "reference",
        "reference_version",
        "reference_date",
        "path",
    }
    _object(source, required, (), field, code)
    if source["kind"] not in SOURCE_KINDS:
        _fail(code, f"{field}.kind", "Origem deve ser calibration_artifact ou model.")
    _string(source["reference"], f"{field}.reference", code)
    _version(source["reference_version"], f"{field}.reference_version", code)
    reference_date = _valid_date(
        source["reference_date"], f"{field}.reference_date", code
    )
    _json_pointer(source["path"], f"{field}.path", code)

    if status in ("observed", "market_implied") and source["kind"] != "calibration_artifact":
        _fail(
            code,
            f"{field}.kind",
            f"Status {status} exige referencia ao artefato de calibracao.",
        )
    if status == "modeled" and source["kind"] != "model":
        _fail(
            code,
            f"{field}.kind",
            "Status modeled exige referencia a um modelo versionado.",
        )
    if source["kind"] == "calibration_artifact":
        if source["reference"] != calibration["artifact_id"]:
            _fail(
                code,
                f"{field}.reference",
                "Referencia deve apontar para o artifact_id declarado.",
            )
        if source["reference_version"] != calibration["calibration_version"]:
            _fail(
                code,
                f"{field}.reference_version",
                "Versao da referencia deve coincidir com a calibracao.",
            )

    if status == "observed":
        if purpose != "backtest":
            _fail(code, field.rsplit(".", 1)[0] + ".status", "Projecao nao aceita valor observado.")
        if reference_date > cutoff:
            _fail(code, f"{field}.reference_date", "Observacao excede a data de corte.")
    elif reference_date > base_date:
        _fail(
            code,
            f"{field}.reference_date",
            "Valor implicito ou modelado nao pode usar referencia posterior a data-base.",
        )

    if status == "market_implied":
        if calibration["scope"] != "historical_and_market_implied":
            _fail(
                code,
                field,
                "Calibracao historical_only nao contem curva market_implied.",
            )
        if not 0 <= (cutoff - reference_date).days <= MAX_CALIBRATION_STALENESS_DAYS:
            _fail(
                code,
                f"{field}.reference_date",
                "Curva implicita deve estar entre zero e sete dias antes do corte.",
            )
        expected_metric = {
            "inflation": "ettj_implied_inflation_forward",
            "discount_rate": "ettj_nominal_forward",
        }.get(variable)
        if source_metric != expected_metric:
            _fail(
                code,
                field.rsplit(".", 1)[0] + ".source_metric",
                "Metrica market_implied nao corresponde a variavel.",
            )


def _validate_variable(value, variable, calibration, base_date, cutoff, purpose,
                       period_end, field):
    code = "INVALID_TRAJECTORY_VALUE"
    required = {"value", "status", "measure", "source_metric", "method", "source"}
    _object(value, required, (), field, code)
    _rate(value["value"], f"{field}.value")
    status = value["status"]
    if status not in STATUSES:
        _fail(code, f"{field}.status", "Status economico desconhecido.")
    measure = value["measure"]
    if measure not in MEASURES:
        _fail(code, f"{field}.measure", "Medida economica desconhecida.")
    _string(value["source_metric"], f"{field}.source_metric", code)
    _string(value["method"], f"{field}.method", code)

    allowed_statuses = {
        "inflation": {"observed", "market_implied", "modeled"},
        "discount_rate": {"market_implied", "modeled"},
        "salary_growth": {"modeled"},
        "asset_return": {"modeled"},
    }
    if status not in allowed_statuses[variable]:
        _fail(
            code,
            f"{field}.status",
            f"Status {status} nao e permitido para {variable}.",
        )
    expected_measure = {
        "observed": "effective_return",
        "market_implied": "forward_rate",
        "modeled": "modeled_rate",
    }[status]
    if measure != expected_measure:
        _fail(
            code,
            f"{field}.measure",
            f"Status {status} exige medida {expected_measure}.",
        )
    if status == "observed":
        if value["source_metric"] != "ipca":
            _fail(code, f"{field}.source_metric", "Inflacao observada deve usar IPCA.")
        if period_end > cutoff:
            _fail(
                code,
                f"{field}.status",
                "Periodo observado deve terminar ate a data de corte.",
            )

    _validate_source(
        value["source"],
        variable,
        status,
        value["source_metric"],
        calibration,
        base_date,
        cutoff,
        purpose,
        f"{field}.source",
    )


def validate_trajectory_request(request):
    """Valida e devolve copia independente do request de trajetoria 0.2.0."""
    code = "INVALID_TRAJECTORY_REQUEST"
    required = {
        "contract_version",
        "purpose",
        "base_date",
        "horizon_years",
        "unit",
        "rate_basis",
        "ruleset_id",
        "ruleset_version",
        "calibration",
        "trajectory",
    }
    _object(request, required, (), None, code)
    if request["contract_version"] != TRAJECTORY_CONTRACT_VERSION:
        _fail(
            "UNSUPPORTED_TRAJECTORY_CONTRACT_VERSION",
            "contract_version",
            "Versao do contrato de trajetoria nao suportada.",
        )
    if request["purpose"] not in PURPOSES:
        _fail(code, "purpose", "Purpose deve ser projection ou backtest.")
    base_date = _valid_date(request["base_date"], "base_date", code)
    horizon = request["horizon_years"]
    if type(horizon) is not int or not 1 <= horizon <= MAX_HORIZON_YEARS:
        _fail(code, "horizon_years", "Horizonte deve ser inteiro entre 1 e 120.")
    if base_date.year + horizon > 9999:
        _fail(code, "horizon_years", "Data final excede o calendario suportado.")
    if request["unit"] != "annual_decimal":
        _fail(code, "unit", "Esperado annual_decimal.")
    if request["rate_basis"] != "nominal":
        _fail(code, "rate_basis", "Esperado nominal.")
    _string(request["ruleset_id"], "ruleset_id", code)
    _version(request["ruleset_version"], "ruleset_version", code)

    cutoff = _validate_calibration(
        request["calibration"], base_date, request["purpose"]
    )
    trajectory = request["trajectory"]
    _object(
        trajectory,
        {"trajectory_id", "trajectory_version", "periods"},
        (),
        "trajectory",
        code,
    )
    _identifier(trajectory["trajectory_id"], "trajectory.trajectory_id", code)
    _version(trajectory["trajectory_version"], "trajectory.trajectory_version", code)
    periods = trajectory["periods"]
    if not isinstance(periods, list):
        _fail(code, "trajectory.periods", "Esperada lista de periodos.")
    if len(periods) != horizon:
        _fail(
            "INVALID_TRAJECTORY",
            "trajectory.periods",
            "Quantidade de periodos deve coincidir com horizon_years.",
        )

    expected_variables = None
    last_period_end = None
    for index, period in enumerate(periods, 1):
        field = f"trajectory.periods.{index - 1}"
        _object(
            period,
            {"period", "period_start", "period_end", "variables"},
            (),
            field,
            "INVALID_TRAJECTORY",
        )
        if period["period"] != index:
            _fail(
                "INVALID_TRAJECTORY",
                f"{field}.period",
                "Periodos devem ser inteiros contiguos iniciados em 1.",
            )
        period_start = _valid_date(
            period["period_start"], f"{field}.period_start", "INVALID_TRAJECTORY"
        )
        period_end = _valid_date(
            period["period_end"], f"{field}.period_end", "INVALID_TRAJECTORY"
        )
        if period_start != _anniversary(base_date, index - 1) or period_end != _anniversary(
            base_date, index
        ):
            _fail(
                "INVALID_TRAJECTORY",
                field,
                "Datas do periodo devem seguir os aniversarios da data-base.",
            )
        if last_period_end is not None and period_start != last_period_end:
            _fail("INVALID_TRAJECTORY", field, "Periodos devem ser contiguos.")
        last_period_end = period_end

        variables = period["variables"]
        if not isinstance(variables, dict):
            _fail("INVALID_TRAJECTORY", f"{field}.variables", "Esperado objeto.")
        keys = set(variables)
        if not set(REQUIRED_VARIABLES) <= keys or not keys <= set(VARIABLES):
            _fail(
                "INVALID_TRAJECTORY",
                f"{field}.variables",
                "Inflation e discount_rate sao obrigatorias; variavel desconhecida.",
            )
        if expected_variables is None:
            expected_variables = keys
        elif keys != expected_variables:
            _fail(
                "INVALID_TRAJECTORY",
                f"{field}.variables",
                "Variaveis opcionais devem estar presentes em todos os periodos ou em nenhum.",
            )
        for variable in VARIABLES:
            if variable in variables:
                _validate_variable(
                    variables[variable],
                    variable,
                    request["calibration"],
                    base_date,
                    cutoff,
                    request["purpose"],
                    period_end,
                    f"{field}.variables.{variable}",
                )

    if request["purpose"] == "backtest" and last_period_end > cutoff:
        _fail(
            "INVALID_CALIBRATION_REFERENCE",
            "calibration.cutoff_date",
            "Backtest exige data de corte igual ou posterior ao fim da trajetoria.",
        )
    return deepcopy(request)
