"""Coleta auditavel de series brutas do SGS do Banco Central do Brasil."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import shutil
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


COLLECTOR_VERSION = "0.1.0"
MANIFEST_VERSION = "1.0.0"
MAX_WINDOW_DAYS = 3640
SOURCE_NAME = "Banco Central do Brasil - Sistema Gerenciador de Series Temporais"
SOURCE_CATALOG_URL = "https://dadosabertos.bcb.gov.br/"
SERIES_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


@dataclass(frozen=True)
class SeriesSpec:
    code: int
    name: str
    frequency: str
    unit: str


SERIES = {
    "selic_daily": SeriesSpec(11, "Taxa Selic diaria", "daily", "percent_per_day"),
    "selic_target": SeriesSpec(432, "Meta para a taxa Selic", "daily", "percent_per_year"),
    "cdi": SeriesSpec(12, "Taxa CDI diaria", "daily", "percent_per_day"),
    "ipca": SeriesSpec(433, "IPCA", "monthly", "percent_per_month"),
    "igpm": SeriesSpec(189, "IGP-M", "monthly", "percent_per_month"),
    "usd_brl": SeriesSpec(1, "Dolar comercial venda", "daily", "brl_per_usd"),
}


class BacenCollectionError(RuntimeError):
    """Falha de transporte, validacao ou publicacao de um snapshot."""


class BacenResponseError(BacenCollectionError):
    """Resposta do SGS nao segue o contrato esperado pelo coletor."""


def date_windows(start, end, max_window_days=MAX_WINDOW_DAYS):
    """Divide um periodo inclusivo em janelas contiguas aceitas pelo SGS."""
    if type(start) is not date or type(end) is not date:
        raise ValueError("Inicio e fim devem ser datas.")
    if start > end:
        raise ValueError("A data inicial nao pode ser posterior a data final.")
    if type(max_window_days) is not int or max_window_days < 1:
        raise ValueError("O tamanho da janela deve ser um inteiro positivo.")

    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + timedelta(days=max_window_days))
        yield cursor, window_end
        if window_end == end:
            break
        cursor = window_end + timedelta(days=1)


def build_series_url(code, start, end):
    query = urlencode({
        "formato": "json",
        "dataInicial": start.strftime("%d/%m/%Y"),
        "dataFinal": end.strftime("%d/%m/%Y"),
    })
    return f"{SERIES_URL.format(code=code)}?{query}"


def fetch_bytes(url, timeout=30):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"tribo3-economic-scenarios/{COLLECTOR_VERSION}",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise BacenCollectionError(
                    f"SGS respondeu com HTTP {response.status}."
                )
            return response.read()
    except HTTPError as exc:
        raise BacenCollectionError(f"SGS respondeu com HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise BacenCollectionError("Nao foi possivel consultar o SGS.") from None


def validate_response(body, start, end):
    """Valida o envelope sem transformar ou reserializar os bytes brutos."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BacenResponseError("O SGS retornou JSON invalido ou fora de UTF-8.") from None

    if not isinstance(payload, list):
        raise BacenResponseError("O SGS retornou um envelope inesperado.")

    for index, row in enumerate(payload):
        if not isinstance(row, dict) or set(row) != {"data", "valor"}:
            raise BacenResponseError(
                f"Registro {index} do SGS nao contem apenas data e valor."
            )
        if not isinstance(row["data"], str) or not isinstance(row["valor"], str):
            raise BacenResponseError(
                f"Registro {index} do SGS possui tipos inesperados."
            )
        try:
            record_date = datetime.strptime(row["data"], "%d/%m/%Y").date()
            value = Decimal(row["valor"].replace(",", "."))
        except (ValueError, InvalidOperation):
            raise BacenResponseError(
                f"Registro {index} do SGS possui data ou valor invalido."
            ) from None
        if not start <= record_date <= end:
            raise BacenResponseError(
                f"Registro {index} do SGS esta fora da janela solicitada."
            )
        if not value.is_finite():
            raise BacenResponseError(
                f"Registro {index} do SGS possui valor nao finito."
            )
    return len(payload)


def _selected_series(keys):
    selected = list(SERIES) if keys is None else list(keys)
    if not selected:
        raise ValueError("Selecione pelo menos uma serie.")
    if len(selected) != len(set(selected)):
        raise ValueError("Uma serie nao pode ser selecionada mais de uma vez.")
    unknown = sorted(set(selected) - SERIES.keys())
    if unknown:
        raise ValueError(f"Series desconhecidas: {unknown}.")
    return selected


def _utc_timestamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O horario da coleta deve possuir fuso horario.")
    return value.astimezone(timezone.utc)


def collect_snapshot(
    output_root,
    start,
    end,
    series=None,
    *,
    fetcher=fetch_bytes,
    timeout=30,
    collected_at=None,
):
    """Coleta series e publica um diretorio somente quando todas terminarem."""
    selected = _selected_series(series)
    windows = list(date_windows(start, end))
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("O timeout deve ser um numero positivo.")

    collected_at = _utc_timestamp(collected_at or datetime.now(timezone.utc))
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    suffix = uuid4().hex[:12]
    timestamp = collected_at.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"bacen-sgs-{timestamp}-{suffix}"
    temporary = output_root / f".{snapshot_id}.tmp"
    destination = output_root / snapshot_id
    temporary.mkdir()

    manifest = {
        "schema_version": MANIFEST_VERSION,
        "snapshot_id": snapshot_id,
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "collector": {
            "name": "cenarios-economicos.app.data_sources.bacen",
            "version": COLLECTOR_VERSION,
        },
        "source": {
            "name": SOURCE_NAME,
            "catalog_url": SOURCE_CATALOG_URL,
            "api_template": SERIES_URL,
        },
        "requested_period": {"start": start.isoformat(), "end": end.isoformat()},
        "series": [],
    }

    try:
        for key in selected:
            spec = SERIES[key]
            series_entry = {
                "key": key,
                **asdict(spec),
                "record_count": 0,
                "files": [],
            }
            for window_start, window_end in windows:
                url = build_series_url(spec.code, window_start, window_end)
                body = fetcher(url, timeout=timeout)
                if not isinstance(body, bytes):
                    raise BacenResponseError("O transportador deve retornar bytes.")
                record_count = validate_response(body, window_start, window_end)
                relative_path = Path("raw") / key / (
                    f"{window_start.isoformat()}_{window_end.isoformat()}.json"
                )
                raw_path = temporary / relative_path
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(body)
                series_entry["record_count"] += record_count
                series_entry["files"].append({
                    "path": relative_path.as_posix(),
                    "request_url": url,
                    "window": {
                        "start": window_start.isoformat(),
                        "end": window_end.isoformat(),
                    },
                    "record_count": record_count,
                    "byte_count": len(body),
                    "sha256": sha256(body).hexdigest(),
                })
            if series_entry["record_count"] == 0:
                raise BacenResponseError(
                    f"A serie {key} nao retornou registros no periodo solicitado."
                )
            manifest["series"].append(series_entry)

        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
