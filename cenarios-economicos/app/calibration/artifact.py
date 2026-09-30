"""Transforma snapshots verificados em um artefato versionado de calibracao."""

import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4
import xml.etree.ElementTree as ET

from app.data_sources.bacen import COLLECTOR_VERSION as BACEN_COLLECTOR_VERSION, SERIES
from app.data_sources.ibovespa import COLLECTOR_VERSION as IBOVESPA_COLLECTOR_VERSION
from app.services.scenario_generator import dumps_decimal


BUILDER_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
TRANSFORMATION_POLICY_VERSION = "0.1.0"
DECIMAL_PLACES = 8
CALCULATION_PRECISION = 50
QUANTUM = Decimal("0.00000001")
MAX_ENDPOINT_STALENESS_DAYS = 7
CALENDAR_ID = "BR_SETTLEMENT_252"
CALENDAR_COVERAGE = "source_consistent"
SUPPORTED_ANBIMA_SPIKE_VERSION = "0.1.0"
REQUIRED_BACEN_SERIES = tuple(SERIES)
HISTORICAL_METRICS = (
    "selic_effective",
    "selic_target",
    "cdi",
    "ipca",
    "igpm",
    "usd_brl",
    "ibovespa",
)
IDENTIFIER_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


class CalibrationError(RuntimeError):
    """Falha de validacao ou publicacao do artefato."""


class CalibrationInputError(CalibrationError):
    """Snapshot ou parametro nao satisfaz o contrato de calibracao."""


def _json_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise CalibrationInputError(f"JSON contem chave duplicada: {key}.")
        result[key] = value
    return result


def _load_json_bytes(body, description):
    try:
        return json.loads(
            body.decode("utf-8"),
            parse_float=Decimal,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CalibrationInputError(f"{description} contem {value} nao finito.")
            ),
            object_pairs_hook=_json_pairs,
        )
    except CalibrationInputError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CalibrationInputError(
            f"{description} nao e JSON UTF-8 valido."
        ) from None


def _object(value, description):
    if not isinstance(value, dict):
        raise CalibrationInputError(f"{description} deve ser um objeto.")
    return value


def _list(value, description):
    if not isinstance(value, list):
        raise CalibrationInputError(f"{description} deve ser uma lista.")
    return value


def _text(value, description):
    if not isinstance(value, str) or not value.strip():
        raise CalibrationInputError(f"{description} deve ser texto nao vazio.")
    return value


def _integer(value, description, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise CalibrationInputError(
            f"{description} deve ser inteiro maior ou igual a {minimum}."
        )
    return value


def _iso_date(value, description):
    if not isinstance(value, str):
        raise CalibrationInputError(f"{description} deve usar YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise CalibrationInputError(f"{description} deve usar YYYY-MM-DD.") from None
    if parsed.isoformat() != value:
        raise CalibrationInputError(f"{description} deve usar YYYY-MM-DD.")
    return parsed


def _decimal(value, description):
    if isinstance(value, bool) or type(value) not in (str, int, Decimal):
        raise CalibrationInputError(f"{description} deve ser decimal exato.")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise CalibrationInputError(f"{description} deve ser decimal exato.") from None
    if not parsed.is_finite():
        raise CalibrationInputError(f"{description} deve ser finito.")
    return parsed


def _decimal_br(value, description, *, optional=False):
    if not isinstance(value, str):
        raise CalibrationInputError(f"{description} deve ser texto.")
    stripped = value.strip()
    if not stripped:
        if optional:
            return None
        raise CalibrationInputError(f"{description} esta vazio.")
    return _decimal(stripped.replace(".", "").replace(",", "."), description)


def _quantize(value):
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        rounded = value.quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
    return abs(rounded) if rounded == 0 else rounded


def _utc_timestamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O horario de geracao deve possuir fuso horario.")
    return value.astimezone(timezone.utc)


def _manifest(snapshot_root, expected_description):
    root = Path(snapshot_root)
    if not root.is_dir():
        raise CalibrationInputError(
            f"O snapshot {expected_description} nao e um diretorio."
        )
    path = root / "manifest.json"
    try:
        body = path.read_bytes()
    except OSError:
        raise CalibrationInputError(
            f"O snapshot {expected_description} nao possui manifest.json legivel."
        ) from None
    manifest = _object(
        _load_json_bytes(body, f"Manifesto {expected_description}"),
        f"Manifesto {expected_description}",
    )
    return root, manifest, sha256(body).hexdigest()


def _verified_file(snapshot_root, entry, description):
    entry = _object(entry, description)
    relative_text = _text(entry.get("path"), f"{description}.path")
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise CalibrationInputError(f"{description}.path nao e relativo seguro.")
    root = snapshot_root.resolve()
    path = (snapshot_root / relative).resolve()
    if path != root and root not in path.parents:
        raise CalibrationInputError(f"{description}.path escapa do snapshot.")
    try:
        body = path.read_bytes()
    except OSError:
        raise CalibrationInputError(f"{description}.path nao pode ser lido.") from None
    expected_bytes = _integer(entry.get("byte_count"), f"{description}.byte_count")
    expected_hash = _text(entry.get("sha256"), f"{description}.sha256")
    if len(body) != expected_bytes:
        raise CalibrationInputError(f"{description} diverge do byte_count do manifesto.")
    if sha256(body).hexdigest() != expected_hash:
        raise CalibrationInputError(f"{description} diverge do SHA-256 do manifesto.")
    return body, relative.as_posix(), expected_hash


def _source_descriptor(kind, manifest, manifest_hash, files, **extra):
    collector = _object(manifest.get("collector"), f"collector de {kind}")
    descriptor = {
        "kind": kind,
        "snapshot_id": _text(manifest.get("snapshot_id"), f"snapshot_id de {kind}"),
        "collected_at": _text(manifest.get("collected_at"), f"collected_at de {kind}"),
        "collector": {
            "name": _text(collector.get("name"), f"collector.name de {kind}"),
            "version": _text(
                collector.get("version"), f"collector.version de {kind}"
            ),
        },
        "manifest_sha256": manifest_hash,
        "files": files,
    }
    descriptor.update(extra)
    return descriptor


def _load_bacen_snapshot(snapshot_root):
    root, manifest, manifest_hash = _manifest(snapshot_root, "do Bacen")
    if manifest.get("schema_version") != "1.0.0":
        raise CalibrationInputError("Versao do manifesto Bacen nao suportada.")
    collector = _object(manifest.get("collector"), "collector do Bacen")
    if collector.get("name") != "cenarios-economicos.app.data_sources.bacen":
        raise CalibrationInputError("Manifesto nao pertence ao coletor Bacen esperado.")
    if collector.get("version") != BACEN_COLLECTOR_VERSION:
        raise CalibrationInputError("Versao do coletor Bacen nao suportada.")
    requested = _object(manifest.get("requested_period"), "requested_period do Bacen")
    requested_start = _iso_date(requested.get("start"), "requested_period.start")
    requested_end = _iso_date(requested.get("end"), "requested_period.end")
    if requested_start > requested_end:
        raise CalibrationInputError("Periodo solicitado do Bacen e invertido.")

    entries = _list(manifest.get("series"), "series do Bacen")
    by_key = {}
    for entry in entries:
        entry = _object(entry, "Entrada de serie Bacen")
        key = _text(entry.get("key"), "series.key")
        if key in by_key:
            raise CalibrationInputError(f"Serie Bacen duplicada no manifesto: {key}.")
        by_key[key] = entry
    unexpected = set(by_key) - SERIES.keys()
    if unexpected:
        raise CalibrationInputError(
            f"Snapshot Bacen contem series desconhecidas: {sorted(unexpected)}."
        )
    missing = set(REQUIRED_BACEN_SERIES) - by_key.keys()
    if missing:
        raise CalibrationInputError(
            f"Snapshot Bacen nao contem as series obrigatorias: {sorted(missing)}."
        )

    observations = {}
    hashes = {}
    all_files = []
    for key in REQUIRED_BACEN_SERIES:
        entry = by_key[key]
        spec = SERIES[key]
        expected = {
            "code": spec.code,
            "frequency": spec.frequency,
            "unit": spec.unit,
        }
        for field, value in expected.items():
            if entry.get(field) != value:
                raise CalibrationInputError(
                    f"Metadado {field} da serie Bacen {key} diverge do catalogo."
                )
        rows = {}
        series_hashes = []
        file_entries = _list(entry.get("files"), f"files de {key}")
        total_count = 0
        for index, file_entry in enumerate(file_entries):
            description = f"Arquivo Bacen {key}[{index}]"
            body, relative, file_hash = _verified_file(root, file_entry, description)
            payload = _list(_load_json_bytes(body, description), description)
            expected_count = _integer(
                file_entry.get("record_count"), f"{description}.record_count"
            )
            if len(payload) != expected_count:
                raise CalibrationInputError(
                    f"{description} diverge do record_count do manifesto."
                )
            window = _object(file_entry.get("window"), f"{description}.window")
            window_start = _iso_date(window.get("start"), f"{description}.window.start")
            window_end = _iso_date(window.get("end"), f"{description}.window.end")
            for row_index, row in enumerate(payload):
                row = _object(row, f"{description} registro {row_index}")
                if set(row) != {"data", "valor"}:
                    raise CalibrationInputError(
                        f"{description} registro {row_index} possui campos inesperados."
                    )
                try:
                    observed_at = datetime.strptime(row["data"], "%d/%m/%Y").date()
                except (TypeError, ValueError):
                    raise CalibrationInputError(
                        f"{description} registro {row_index} possui data invalida."
                    ) from None
                value = _decimal(
                    _text(row["valor"], f"{description} registro {row_index}.valor")
                    .replace(",", "."),
                    f"{description} registro {row_index}.valor",
                )
                if not window_start <= observed_at <= window_end:
                    raise CalibrationInputError(
                        f"{description} contem observacao fora da janela."
                    )
                if observed_at in rows:
                    raise CalibrationInputError(
                        f"Serie Bacen {key} possui data duplicada: {observed_at}."
                    )
                rows[observed_at] = value
            total_count += len(payload)
            series_hashes.append(file_hash)
            all_files.append({"path": relative, "sha256": file_hash})
        if total_count != _integer(entry.get("record_count"), f"record_count de {key}"):
            raise CalibrationInputError(
                f"Serie Bacen {key} diverge do record_count agregado."
            )
        observations[key] = rows
        hashes[key] = series_hashes

    source = _source_descriptor(
        "bacen_sgs",
        manifest,
        manifest_hash,
        all_files,
        requested_period={
            "start": requested_start.isoformat(),
            "end": requested_end.isoformat(),
        },
    )
    return observations, hashes, source, requested_start, requested_end


def _load_ibovespa_snapshot(snapshot_root):
    root, manifest, manifest_hash = _manifest(snapshot_root, "do Ibovespa")
    if manifest.get("schema_version") != "1.0.0":
        raise CalibrationInputError("Versao do manifesto Ibovespa nao suportada.")
    collector = _object(manifest.get("collector"), "collector do Ibovespa")
    if collector.get("name") != "cenarios-economicos.app.data_sources.ibovespa":
        raise CalibrationInputError(
            "Manifesto nao pertence ao coletor Ibovespa esperado."
        )
    if collector.get("version") != IBOVESPA_COLLECTOR_VERSION:
        raise CalibrationInputError("Versao do coletor Ibovespa nao suportada.")
    provenance = _object(manifest.get("data_provenance"), "proveniencia do Ibovespa")
    if provenance.get("is_official_b3_source") is not False:
        raise CalibrationInputError(
            "A proveniencia do Ibovespa deve declarar fonte nao oficial da B3."
        )
    provider_call = _object(manifest.get("provider_call"), "provider_call do Ibovespa")
    expected_call = {
        "tickers": "^BVSP",
        "interval": "1d",
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
        "rounding": False,
    }
    for field, expected in expected_call.items():
        if provider_call.get(field) != expected:
            raise CalibrationInputError(
                f"provider_call.{field} do Ibovespa deve ser {expected!r}."
            )
    file_entry = _object(manifest.get("file"), "Arquivo do Ibovespa")
    if file_entry.get("classification") != "provider-extract-not-raw-b3-data":
        raise CalibrationInputError("Classificacao do arquivo Ibovespa e inesperada.")
    body, relative, file_hash = _verified_file(root, file_entry, "Arquivo do Ibovespa")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise CalibrationInputError("CSV do Ibovespa nao esta em UTF-8.") from None
    reader = csv.DictReader(io.StringIO(text, newline=""))
    expected_header = ("Date", "Open", "High", "Low", "Close", "Adj Close", "Volume")
    if tuple(reader.fieldnames or ()) != expected_header:
        raise CalibrationInputError("CSV do Ibovespa possui cabecalho inesperado.")
    requested = _object(manifest.get("requested_period"), "periodo do Ibovespa")
    requested_start = _iso_date(
        requested.get("start_inclusive"), "requested_period.start_inclusive"
    )
    requested_end = _iso_date(
        requested.get("end_inclusive"), "requested_period.end_inclusive"
    )
    rows = {}
    previous = None
    try:
        for index, row in enumerate(reader):
            if None in row or set(row) != set(expected_header):
                raise CalibrationInputError(
                    f"CSV do Ibovespa registro {index} possui campos inesperados."
                )
            observed_at = _iso_date(row["Date"], f"Ibovespa registro {index}.Date")
            close = _decimal(row["Close"], f"Ibovespa registro {index}.Close")
            if close <= 0:
                raise CalibrationInputError(
                    f"Ibovespa registro {index}.Close deve ser positivo."
                )
            if not requested_start <= observed_at <= requested_end:
                raise CalibrationInputError("CSV do Ibovespa contem data fora do periodo.")
            if observed_at in rows or (previous is not None and observed_at <= previous):
                raise CalibrationInputError(
                    "Datas do CSV do Ibovespa devem ser unicas e crescentes."
                )
            rows[observed_at] = close
            previous = observed_at
    except csv.Error:
        raise CalibrationInputError("CSV do Ibovespa e invalido.") from None
    observed_content = _object(manifest.get("observed_content"), "observed_content")
    if len(rows) != _integer(observed_content.get("record_count"), "record_count Ibovespa"):
        raise CalibrationInputError("CSV do Ibovespa diverge do record_count.")
    source = _source_descriptor(
        "ibovespa_yahoo_yfinance",
        manifest,
        manifest_hash,
        [{"path": relative, "sha256": file_hash}],
        administrator="B3",
        provider=_text(provenance.get("provider"), "provider do Ibovespa"),
        access_client=_text(
            provenance.get("access_client"), "access_client do Ibovespa"
        ),
        access_client_version=_text(
            provenance.get("access_client_version"),
            "access_client_version do Ibovespa",
        ),
        serialization_library=_text(
            provenance.get("serialization_library"),
            "serialization_library do Ibovespa",
        ),
        serialization_library_version=_text(
            provenance.get("serialization_library_version"),
            "serialization_library_version do Ibovespa",
        ),
        file_classification=file_entry["classification"],
        is_official_b3_source=False,
        requested_period={
            "start": requested_start.isoformat(),
            "end": requested_end.isoformat(),
        },
    )
    return rows, [file_hash], source, requested_start, requested_end


def _completed_year(year, cutoff_date):
    return date(year, 12, 31) <= cutoff_date


def _compose(values):
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        factor = Decimal(1)
        for value in values:
            rate = value / Decimal(100)
            if rate <= -1:
                raise CalibrationInputError("Taxa de fluxo deve ser maior que -100%.")
            factor *= Decimal(1) + rate
        return _quantize(factor - Decimal(1))


def _monthly_returns(values, cutoff_date):
    months = {}
    for observed_at, value in values.items():
        if observed_at > cutoff_date:
            continue
        key = (observed_at.year, observed_at.month)
        if key in months:
            raise CalibrationInputError(
                f"Serie mensal possui duas observacoes para {observed_at:%Y-%m}."
            )
        months[key] = value
    results = {}
    for year in sorted({item[0] for item in months}):
        if not _completed_year(year, cutoff_date):
            continue
        if all((year, month) in months for month in range(1, 13)):
            results[year] = {
                "value": _compose(months[(year, month)] for month in range(1, 13)),
                "observation_count": 12,
                "coverage": "complete",
            }
    return results


def _daily_dates_are_consistent(dates, year, requested_start, requested_end):
    if not dates or requested_start > date(year, 1, 1) or requested_end < date(year, 12, 31):
        return False
    ordered = sorted(dates)
    if (ordered[0] - date(year, 1, 1)).days > MAX_ENDPOINT_STALENESS_DAYS:
        return False
    if (date(year, 12, 31) - ordered[-1]).days > MAX_ENDPOINT_STALENESS_DAYS:
        return False
    return all((following - current).days <= MAX_ENDPOINT_STALENESS_DAYS
               for current, following in zip(ordered, ordered[1:]))


def _paired_daily_returns(
    selic_values, cdi_values, cutoff_date, requested_start, requested_end
):
    results = {"selic_effective": {}, "cdi": {}}
    years = sorted({item.year for item in selic_values} | {item.year for item in cdi_values})
    for year in years:
        if not _completed_year(year, cutoff_date):
            continue
        selic_dates = {item for item in selic_values if item.year == year and item <= cutoff_date}
        cdi_dates = {item for item in cdi_values if item.year == year and item <= cutoff_date}
        if selic_dates != cdi_dates or not _daily_dates_are_consistent(
            selic_dates, year, requested_start, requested_end
        ):
            continue
        ordered = sorted(selic_dates)
        common = {
            "observation_count": len(ordered),
            "coverage": CALENDAR_COVERAGE,
            "calendar_id": CALENDAR_ID,
        }
        results["selic_effective"][year] = {
            **common,
            "value": _compose(selic_values[item] for item in ordered),
        }
        results["cdi"][year] = {
            **common,
            "value": _compose(cdi_values[item] for item in ordered),
        }
    return results


def _last_before(values, boundary):
    candidates = [item for item in values if item < boundary]
    if not candidates:
        return None
    observed_at = max(candidates)
    if (boundary - observed_at).days > MAX_ENDPOINT_STALENESS_DAYS:
        return None
    return observed_at, values[observed_at]


def _year_end_levels(values, cutoff_date):
    results = {}
    for year in sorted({item.year for item in values}):
        if not _completed_year(year, cutoff_date):
            continue
        endpoint = _last_before(values, date(year + 1, 1, 1))
        if endpoint is None:
            continue
        observed_at, value = endpoint
        rate = value / Decimal(100)
        if rate <= -1:
            raise CalibrationInputError("Meta Selic deve ser maior que -100%.")
        results[year] = {
            "value": _quantize(rate),
            "observation_count": 1,
            "coverage": "endpoint_within_7_days",
            "observed_at": observed_at.isoformat(),
        }
    return results


def _level_changes(values, cutoff_date):
    results = {}
    years = range(min((item.year for item in values), default=cutoff_date.year),
                  cutoff_date.year + 1)
    for year in years:
        if not _completed_year(year, cutoff_date):
            continue
        start = _last_before(values, date(year, 1, 1))
        end = _last_before(values, date(year + 1, 1, 1))
        if start is None or end is None:
            continue
        start_date, start_value = start
        end_date, end_value = end
        if start_value <= 0 or end_value <= 0:
            raise CalibrationInputError("Series de nivel devem ser positivas.")
        with localcontext() as context:
            context.prec = CALCULATION_PRECISION
            value = _quantize(end_value / start_value - Decimal(1))
        results[year] = {
            "value": value,
            "observation_count": 2,
            "coverage": "endpoints_within_7_days",
            "start_observed_at": start_date.isoformat(),
            "end_observed_at": end_date.isoformat(),
        }
    return results


def _historical_record(metric, year, result, source, file_hashes, source_series, method,
                       measure):
    record = {
        "metric": metric,
        "period_start": date(year, 1, 1).isoformat(),
        "period_end": date(year + 1, 1, 1).isoformat(),
        "value": result["value"],
        "unit": "annual_decimal",
        "measure": measure,
        "basis": "nominal",
        "status": "observed",
        "method": method,
        "transformation_policy_version": TRANSFORMATION_POLICY_VERSION,
        "source_snapshot_id": source["snapshot_id"],
        "source_series": source_series,
        "source_file_sha256": list(file_hashes),
        "observation_count": result["observation_count"],
        "coverage": result["coverage"],
    }
    for optional in (
        "calendar_id",
        "observed_at",
        "start_observed_at",
        "end_observed_at",
    ):
        if optional in result:
            record[optional] = result[optional]
    return record


def _load_anbima_snapshot(snapshot_root, cutoff_date, allow_experimental):
    if snapshot_root is None:
        return None, None
    if not allow_experimental:
        raise CalibrationInputError(
            "O snapshot ANBIMA ainda e experimental; use autorizacao explicita."
        )
    root, manifest, manifest_hash = _manifest(snapshot_root, "experimental da ANBIMA")
    if manifest.get("schema_version") != "1.0.0" or manifest.get("status") != "experimental-spike":
        raise CalibrationInputError("Manifesto ANBIMA experimental nao suportado.")
    collector = _object(manifest.get("collector"), "collector ANBIMA")
    if collector.get("name") != "spikes.anbima_ettj.probe":
        raise CalibrationInputError("Manifesto nao pertence ao spike ANBIMA esperado.")
    if collector.get("version") != SUPPORTED_ANBIMA_SPIKE_VERSION:
        raise CalibrationInputError("Versao do spike ANBIMA nao suportada.")
    body, relative, file_hash = _verified_file(
        root, manifest.get("file"), "Arquivo XML ANBIMA"
    )
    try:
        xml_root = ET.fromstring(body)
    except ET.ParseError:
        raise CalibrationInputError("XML ANBIMA e invalido.") from None
    if xml_root.tag != "CURVAZERO":
        raise CalibrationInputError("Raiz do XML ANBIMA deve ser CURVAZERO.")
    date_elements = xml_root.findall("./DATA_REFERENCIA")
    if len(date_elements) != 1 or not date_elements[0].text:
        raise CalibrationInputError("XML ANBIMA nao possui data de referencia unica.")
    try:
        reference_date = datetime.strptime(
            date_elements[0].text.strip(), "%d/%m/%Y"
        ).date()
    except ValueError:
        raise CalibrationInputError("Data de referencia ANBIMA e invalida.") from None
    observed_content = _object(manifest.get("observed_content"), "observed_content ANBIMA")
    if observed_content.get("reference_date") != reference_date.isoformat():
        raise CalibrationInputError("Data ANBIMA diverge do manifesto.")
    staleness = (cutoff_date - reference_date).days
    if not 0 <= staleness <= MAX_ENDPOINT_STALENESS_DAYS:
        raise CalibrationInputError(
            "Curva ANBIMA deve estar entre zero e sete dias antes do corte."
        )

    raw_vertices = xml_root.findall("./ETTJ/VERTICES")
    if len(raw_vertices) != _integer(
        observed_content.get("vertex_count"), "vertex_count ANBIMA", minimum=1
    ):
        raise CalibrationInputError("Vertices ANBIMA divergem do manifesto.")
    vertices = []
    previous = 0
    for index, item in enumerate(raw_vertices):
        raw_vertex = _decimal_br(item.attrib.get("Vertice"), f"Vertice ANBIMA {index}")
        if raw_vertex != raw_vertex.to_integral_value():
            raise CalibrationInputError("Vertice ANBIMA deve ser inteiro.")
        vertex = int(raw_vertex)
        if vertex <= previous:
            raise CalibrationInputError("Vertices ANBIMA devem ser positivos e crescentes.")
        previous = vertex
        nominal = _decimal_br(
            item.attrib.get("Prefixados"), f"Prefixados ANBIMA {index}", optional=True
        )
        real = _decimal_br(item.attrib.get("IPCA"), f"IPCA ANBIMA {index}", optional=True)
        published = _decimal_br(
            item.attrib.get("Inflacao"), f"Inflacao ANBIMA {index}", optional=True
        )
        vertices.append({
            "business_days": vertex,
            "nominal": None if nominal is None else nominal / Decimal(100),
            "real": None if real is None else real / Decimal(100),
            "published_inflation": (
                None if published is None else published / Decimal(100)
            ),
        })
    if not any(item["nominal"] is not None for item in vertices) or not any(
        item["real"] is not None for item in vertices
    ):
        raise CalibrationInputError("Curva ANBIMA nao possui taxas nominal e real.")

    curve = _ettj_curve(reference_date, vertices, source_snapshot_id=manifest["snapshot_id"],
                        file_hash=file_hash)
    source = _source_descriptor(
        "anbima_ettj_experimental",
        manifest,
        manifest_hash,
        [{"path": relative, "sha256": file_hash}],
        status="experimental-spike",
        reference_date=reference_date.isoformat(),
        experimental_use_authorized=True,
    )
    return curve, source


def _log_discount(rate, business_days):
    if rate <= -1:
        raise CalibrationInputError("Taxa spot ETTJ deve ser maior que -100%.")
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        return -(Decimal(business_days) / Decimal(252)) * (Decimal(1) + rate).ln()


def _interpolated_log_discount(points, business_days):
    if business_days in points:
        return points[business_days]
    ordered = sorted(points)
    lower = max((item for item in ordered if item < business_days), default=None)
    upper = min((item for item in ordered if item > business_days), default=None)
    if lower is None or upper is None:
        raise CalibrationInputError("Interpolacao ETTJ exigiria extrapolacao.")
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        weight = Decimal(business_days - lower) / Decimal(upper - lower)
        return points[lower] + weight * (points[upper] - points[lower])


def _forward_rate(points, start, end):
    start_log = _interpolated_log_discount(points, start)
    end_log = _interpolated_log_discount(points, end)
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        exponent = (start_log - end_log) * Decimal(252) / Decimal(end - start)
        return exponent.exp() - Decimal(1)


def _ettj_curve(reference_date, raw_vertices, *, source_snapshot_id, file_hash):
    nominal_points = {0: Decimal(0)}
    real_points = {0: Decimal(0)}
    vertices = []
    for item in raw_vertices:
        business_days = item["business_days"]
        nominal = item["nominal"]
        real = item["real"]
        published = item["published_inflation"]
        if nominal is not None:
            nominal_points[business_days] = _log_discount(nominal, business_days)
        if real is not None:
            real_points[business_days] = _log_discount(real, business_days)
        recomputed = None
        difference = None
        if nominal is not None and real is not None:
            with localcontext() as context:
                context.prec = CALCULATION_PRECISION
                recomputed = (Decimal(1) + nominal) / (Decimal(1) + real) - Decimal(1)
                if published is not None:
                    difference = recomputed - published
        vertices.append({
            "business_days": business_days,
            "nominal_spot_rate": None if nominal is None else _quantize(nominal),
            "real_spot_rate": None if real is None else _quantize(real),
            "published_implied_inflation_spot": (
                None if published is None else _quantize(published)
            ),
            "recomputed_implied_inflation_spot": (
                None if recomputed is None else _quantize(recomputed)
            ),
            "published_minus_recomputed": (
                None if difference is None else _quantize(published - recomputed)
            ),
        })
    last_nominal = max(nominal_points)
    last_real = max(real_points)
    max_common = min(last_nominal, last_real)
    forwards = []
    for period in range(1, max_common // 252 + 1):
        start = 252 * (period - 1)
        end = 252 * period
        nominal = _forward_rate(nominal_points, start, end)
        real = _forward_rate(real_points, start, end)
        with localcontext() as context:
            context.prec = CALCULATION_PRECISION
            inflation = (Decimal(1) + nominal) / (Decimal(1) + real) - Decimal(1)
        forwards.append({
            "period": period,
            "start_business_days": start,
            "end_business_days": end,
            "nominal_rate": _quantize(nominal),
            "real_rate": _quantize(real),
            "implied_inflation": _quantize(inflation),
            "unit": "annual_decimal",
            "measure": "forward_rate",
            "status": "market_implied",
            "method": "log_discount_factor_interpolation",
        })
    if not forwards:
        raise CalibrationInputError(
            "Curva ANBIMA nao alcanca o primeiro vertice anual de 252 dias uteis."
        )
    return {
        "reference_date": reference_date.isoformat(),
        "unit": "annual_decimal",
        "day_count": "business_days_252",
        "status": "market_implied",
        "source_status": "experimental-spike",
        "source_snapshot_id": source_snapshot_id,
        "source_file_sha256": file_hash,
        "vertices": vertices,
        "annual_forwards": forwards,
    }


def _validate_identity(calibration_id, calibration_version, responsible):
    if not isinstance(calibration_id, str) or not IDENTIFIER_PATTERN.fullmatch(
        calibration_id
    ):
        raise ValueError(
            "calibration_id deve usar letras minusculas, numeros e hifens."
        )
    if not isinstance(calibration_version, str) or not VERSION_PATTERN.fullmatch(
        calibration_version
    ):
        raise ValueError("calibration_version deve usar MAJOR.MINOR.PATCH.")
    if not isinstance(responsible, str) or not responsible.strip():
        raise ValueError("responsible deve ser texto nao vazio.")


def build_calibration_artifact(
    output_root,
    bacen_snapshot,
    ibovespa_snapshot,
    cutoff_date,
    calibration_id,
    calibration_version,
    responsible,
    *,
    anbima_snapshot=None,
    allow_experimental_anbima=False,
    generated_at=None,
):
    """Constroi e publica atomicamente uma calibracao sem consultar a rede."""
    _validate_identity(calibration_id, calibration_version, responsible)
    if type(cutoff_date) is not date:
        raise ValueError("cutoff_date deve ser uma data.")
    if type(allow_experimental_anbima) is not bool:
        raise ValueError("allow_experimental_anbima deve ser booleano.")
    if allow_experimental_anbima and anbima_snapshot is None:
        raise ValueError(
            "allow_experimental_anbima exige um snapshot ANBIMA."
        )
    generated_at = _utc_timestamp(generated_at or datetime.now(timezone.utc))

    bacen, bacen_hashes, bacen_source, bacen_start, bacen_end = (
        _load_bacen_snapshot(bacen_snapshot)
    )
    ibovespa, ibovespa_hashes, ibovespa_source, ibov_start, ibov_end = (
        _load_ibovespa_snapshot(ibovespa_snapshot)
    )
    if not bacen_start <= cutoff_date <= bacen_end:
        raise CalibrationInputError("Data de corte esta fora do snapshot Bacen.")
    if not ibov_start <= cutoff_date <= ibov_end:
        raise CalibrationInputError("Data de corte esta fora do snapshot Ibovespa.")

    daily = _paired_daily_returns(
        bacen["selic_daily"],
        bacen["cdi"],
        cutoff_date,
        bacen_start,
        bacen_end,
    )
    results = {
        "selic_effective": daily["selic_effective"],
        "selic_target": _year_end_levels(bacen["selic_target"], cutoff_date),
        "cdi": daily["cdi"],
        "ipca": _monthly_returns(bacen["ipca"], cutoff_date),
        "igpm": _monthly_returns(bacen["igpm"], cutoff_date),
        "usd_brl": _level_changes(bacen["usd_brl"], cutoff_date),
        "ibovespa": _level_changes(ibovespa, cutoff_date),
    }
    common_years = sorted(set.intersection(*(set(results[key]) for key in HISTORICAL_METRICS)))
    if not common_years:
        raise CalibrationInputError(
            "Os snapshots nao possuem ano civil completo comum para todas as series."
        )

    metadata = {
        "selic_effective": (
            bacen_source, bacen_hashes["selic_daily"], "selic_daily",
            "compound_daily_factors", "effective_return",
        ),
        "selic_target": (
            bacen_source, bacen_hashes["selic_target"], "selic_target",
            "year_end_rate_level", "annual_rate_level",
        ),
        "cdi": (
            bacen_source, bacen_hashes["cdi"], "cdi",
            "compound_daily_factors", "effective_return",
        ),
        "ipca": (
            bacen_source, bacen_hashes["ipca"], "ipca",
            "compound_monthly_factors", "effective_return",
        ),
        "igpm": (
            bacen_source, bacen_hashes["igpm"], "igpm",
            "compound_monthly_factors", "effective_return",
        ),
        "usd_brl": (
            bacen_source, bacen_hashes["usd_brl"], "usd_brl",
            "calendar_year_endpoint_ratio", "level_change",
        ),
        "ibovespa": (
            ibovespa_source, ibovespa_hashes, "close",
            "calendar_year_endpoint_ratio", "level_change",
        ),
    }
    observations = []
    for year in common_years:
        for metric in HISTORICAL_METRICS:
            source, hashes, source_series, method, measure = metadata[metric]
            observations.append(_historical_record(
                metric,
                year,
                results[metric][year],
                source,
                hashes,
                source_series,
                method,
                measure,
            ))

    market_curve, anbima_source = _load_anbima_snapshot(
        anbima_snapshot, cutoff_date, allow_experimental_anbima
    )
    sources = [bacen_source, ibovespa_source]
    if anbima_source is not None:
        sources.append(anbima_source)
    artifact_id = f"{calibration_id}@{calibration_version}"
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "economic_calibration",
        "artifact_id": artifact_id,
        "calibration_id": calibration_id,
        "calibration_version": calibration_version,
        "builder_version": BUILDER_VERSION,
        "transformation_policy_version": TRANSFORMATION_POLICY_VERSION,
        "cutoff_date": cutoff_date.isoformat(),
        "responsible": responsible.strip(),
        "scope": (
            "historical_and_market_implied" if market_curve is not None
            else "historical_only"
        ),
        "conventions": {
            "period": "calendar_year_half_open",
            "unit": "annual_decimal",
            "decimal_places": DECIMAL_PLACES,
            "rounding": "ROUND_HALF_EVEN",
            "calculation_precision_significant_digits": CALCULATION_PRECISION,
            "daily_calendar_id": CALENDAR_ID,
            "daily_calendar_verification": CALENDAR_COVERAGE,
            "max_endpoint_staleness_days": MAX_ENDPOINT_STALENESS_DAYS,
        },
        "source_snapshots": sources,
        "historical": {
            "common_years": common_years,
            "available_years": {
                metric: sorted(results[metric]) for metric in HISTORICAL_METRICS
            },
            "observations": observations,
        },
        "market_curve": market_curve,
        "variable_mapping": {
            "inflation": {
                "historical_metric": "ipca",
                "trajectory_metric": (
                    "ettj_implied_inflation_forward" if market_curve else None
                ),
                "status": "candidate_not_approved",
            },
            "discount_rate": {
                "historical_context": ["selic_effective", "cdi", "selic_target"],
                "trajectory_metric": "ettj_nominal_forward" if market_curve else None,
                "status": "candidate_not_approved",
            },
            "salary_growth": {
                "status": "unavailable",
                "reason": "Nenhuma fonte salarial foi incorporada.",
            },
            "asset_return": {
                "historical_metric": "ibovespa",
                "status": "partial_benchmark_only",
                "reason": "Ibovespa nao representa a carteira total do plano.",
            },
        },
        "limitations": [
            "Valores historicos SGS refletem a versao conhecida na data da coleta, nao vintages point-in-time.",
            "Cobertura diaria e source_consistent; o calendario BR_SETTLEMENT_252 ainda nao foi verificado por feriado.",
            "Yahoo Finance e yfinance nao sao fontes oficiais da B3.",
            "A calibracao nao define crescimento salarial nem retorno da carteira total.",
            "Valores market_implied nao sao resultados futuros observados.",
            "Este artefato ainda nao e entrada do contrato de geracao 0.1.0.",
        ],
    }

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    directory_name = f"calibration-{calibration_id}-v{calibration_version}"
    destination = output_root / directory_name
    if destination.exists():
        raise CalibrationError(
            "Ja existe artefato para esse calibration_id e calibration_version."
        )
    temporary = output_root / f".{directory_name}.{uuid4().hex[:12]}.tmp"
    temporary.mkdir()
    try:
        calibration_body = (dumps_decimal(artifact) + "\n").encode("utf-8")
        (temporary / "calibration.json").write_bytes(calibration_body)
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "artifact_id": artifact_id,
            "created_at": generated_at.isoformat().replace("+00:00", "Z"),
            "builder": {
                "name": "cenarios-economicos.app.calibration.artifact",
                "version": BUILDER_VERSION,
            },
            "calibration": {
                "id": calibration_id,
                "version": calibration_version,
                "cutoff_date": cutoff_date.isoformat(),
                "transformation_policy_version": TRANSFORMATION_POLICY_VERSION,
                "scope": artifact["scope"],
            },
            "source_manifests": [
                {
                    "kind": source["kind"],
                    "snapshot_id": source["snapshot_id"],
                    "sha256": source["manifest_sha256"],
                }
                for source in sources
            ],
            "file": {
                "path": "calibration.json",
                "format": "json",
                "encoding": "utf-8",
                "byte_count": len(calibration_body),
                "sha256": sha256(calibration_body).hexdigest(),
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
