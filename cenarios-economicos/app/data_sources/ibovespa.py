"""Coleta auditavel do Ibovespa por meio do cliente terceiro yfinance."""

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import shutil
from uuid import uuid4


COLLECTOR_VERSION = "0.1.0"
MANIFEST_VERSION = "1.0.0"
TICKER = "^BVSP"
INTERVAL = "1d"
EXPECTED_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Adj Close", "Volume")
B3_INDEX_URL = (
    "https://www.b3.com.br/pt_br/market-data-e-indices/indices/"
    "indices-amplos/ibovespa.htm"
)
B3_METHODOLOGY_URL = (
    "https://www.b3.com.br/data/files/9C/15/76/F6/3F6947102255C247AC094EA8/"
    "IBOV-Metodologia-pt-br__Novo_.pdf"
)
YFINANCE_URL = "https://pypi.org/project/yfinance/"
YAHOO_FINANCE_URL = "https://finance.yahoo.com/quote/%5EBVSP/history/"


class IbovespaCollectionError(RuntimeError):
    """Falha de dependencia, transporte, validacao ou publicacao do snapshot."""


class IbovespaResponseError(IbovespaCollectionError):
    """Extrato do provedor nao segue o contrato esperado pelo coletor."""


@dataclass(frozen=True)
class ProviderExtract:
    body: bytes
    client_version: str
    serializer_version: str


@dataclass(frozen=True)
class ExtractSummary:
    record_count: int
    first_date: str
    last_date: str


def download_parameters(start, end, timeout=30):
    """Retorna os parametros explicitos usados na chamada de yfinance.download."""
    _validate_period(start, end)
    _validate_timeout(timeout)
    try:
        provider_end = end + timedelta(days=1)
    except OverflowError:
        raise ValueError("A data final nao permite calcular o limite exclusivo.") from None
    return {
        "tickers": TICKER,
        "start": start.isoformat(),
        "end": provider_end.isoformat(),
        "interval": INTERVAL,
        "group_by": "column",
        "actions": False,
        "prepost": False,
        "threads": False,
        "ignore_tz": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
        "keepna": False,
        "progress": False,
        "rounding": False,
        "timeout": timeout,
        "multi_level_index": False,
    }


def fetch_extract(start, end, timeout=30):
    """Consulta o Yahoo Finance via API publica do pacote yfinance."""
    parameters = download_parameters(start, end, timeout)
    try:
        import yfinance as yf
    except ImportError:
        raise IbovespaCollectionError(
            "Instale requirements-data.txt para coletar o Ibovespa."
        ) from None

    try:
        frame = yf.download(**parameters)
    except Exception:
        raise IbovespaCollectionError(
            "Nao foi possivel consultar o Yahoo Finance por yfinance."
        ) from None

    if frame is None or not hasattr(frame, "columns") or not hasattr(frame, "to_csv"):
        raise IbovespaResponseError("yfinance retornou um objeto inesperado.")
    actual_columns = tuple(str(column) for column in frame.columns)
    expected_values = EXPECTED_COLUMNS[1:]
    if set(actual_columns) != set(expected_values):
        raise IbovespaResponseError(
            "yfinance retornou colunas diferentes do contrato esperado."
        )

    try:
        ordered = frame.loc[:, list(expected_values)].copy()
        ordered.index.name = "Date"
        body = ordered.to_csv(
            date_format="%Y-%m-%d",
            lineterminator="\n",
        ).encode("utf-8")
    except Exception:
        raise IbovespaResponseError(
            "Nao foi possivel serializar o extrato do yfinance."
        ) from None

    client_version = str(getattr(yf, "__version__", "unknown"))
    try:
        serializer_version = version("pandas")
    except PackageNotFoundError:
        serializer_version = "unknown"
    return ProviderExtract(
        body=body,
        client_version=client_version,
        serializer_version=serializer_version,
    )


def validate_extract(body, start, end):
    """Valida o CSV serializado pelo coletor sem recalcular precos ou retornos."""
    _validate_period(start, end)
    if not isinstance(body, bytes):
        raise IbovespaResponseError("O extrato deve ser fornecido como bytes.")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise IbovespaResponseError("O extrato nao esta em UTF-8.") from None

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise IbovespaResponseError("O extrato possui cabecalho inesperado.")

    seen = set()
    first_date = None
    last_date = None
    previous_date = None
    count = 0
    price_columns = ("Open", "High", "Low", "Close", "Adj Close")
    try:
        for index, row in enumerate(reader):
            if None in row or set(row) != set(EXPECTED_COLUMNS):
                raise IbovespaResponseError(
                    f"O registro {index} possui quantidade inesperada de campos."
                )
            try:
                record_date = date.fromisoformat(row["Date"])
            except (TypeError, ValueError):
                raise IbovespaResponseError(
                    f"O registro {index} possui data invalida."
                ) from None
            if not start <= record_date <= end:
                raise IbovespaResponseError(
                    f"O registro {index} esta fora do periodo solicitado."
                )
            if record_date in seen or (
                previous_date is not None and record_date <= previous_date
            ):
                raise IbovespaResponseError(
                    "As datas do extrato devem ser unicas e crescentes."
                )

            values = {}
            for column in (*price_columns, "Volume"):
                try:
                    value = Decimal(row[column])
                except (InvalidOperation, TypeError):
                    raise IbovespaResponseError(
                        f"O registro {index} possui {column} invalido."
                    ) from None
                if not value.is_finite():
                    raise IbovespaResponseError(
                        f"O registro {index} possui {column} nao finito."
                    )
                values[column] = value
            if any(values[column] <= 0 for column in price_columns):
                raise IbovespaResponseError(
                    f"O registro {index} possui nivel de indice nao positivo."
                )
            if values["Volume"] < 0:
                raise IbovespaResponseError(
                    f"O registro {index} possui volume negativo."
                )

            seen.add(record_date)
            first_date = first_date or record_date
            last_date = record_date
            previous_date = record_date
            count += 1
    except csv.Error:
        raise IbovespaResponseError("O extrato contem CSV invalido.") from None

    if count == 0:
        raise IbovespaResponseError(
            "O Ibovespa nao retornou registros no periodo solicitado."
        )
    return ExtractSummary(
        record_count=count,
        first_date=first_date.isoformat(),
        last_date=last_date.isoformat(),
    )


def _validate_period(start, end):
    if type(start) is not date or type(end) is not date:
        raise ValueError("Inicio e fim devem ser datas.")
    if start > end:
        raise ValueError("A data inicial nao pode ser posterior a data final.")


def _validate_timeout(timeout):
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("O timeout deve ser um numero positivo.")


def _utc_timestamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O horario da coleta deve possuir fuso horario.")
    return value.astimezone(timezone.utc)


def collect_snapshot(
    output_root,
    start,
    end,
    *,
    fetcher=fetch_extract,
    timeout=30,
    collected_at=None,
):
    """Coleta um extrato do provedor e o publica junto com seu manifesto."""
    parameters = download_parameters(start, end, timeout)
    collected_at = _utc_timestamp(collected_at or datetime.now(timezone.utc))
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = collected_at.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"ibovespa-yahoo-{timestamp}-{uuid4().hex[:12]}"
    temporary = output_root / f".{snapshot_id}.tmp"
    destination = output_root / snapshot_id
    temporary.mkdir()

    try:
        extract = fetcher(start, end, timeout=timeout)
        if not isinstance(extract, ProviderExtract):
            raise IbovespaResponseError(
                "O transportador deve retornar um ProviderExtract."
            )
        if not extract.client_version:
            raise IbovespaResponseError(
                "A versao do cliente yfinance nao foi informada."
            )
        if not extract.serializer_version:
            raise IbovespaResponseError(
                "A versao do serializador pandas nao foi informada."
            )
        summary = validate_extract(extract.body, start, end)
        relative_path = Path("provider") / (
            f"ibovespa_{start.isoformat()}_{end.isoformat()}.csv"
        )
        data_path = temporary / relative_path
        data_path.parent.mkdir(parents=True)
        data_path.write_bytes(extract.body)

        manifest = {
            "schema_version": MANIFEST_VERSION,
            "snapshot_id": snapshot_id,
            "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
            "collector": {
                "name": "cenarios-economicos.app.data_sources.ibovespa",
                "version": COLLECTOR_VERSION,
            },
            "instrument": {
                "name": "Indice Bovespa (Ibovespa)",
                "administrator": "B3 S.A. - Brasil, Bolsa, Balcao",
                "official_index_url": B3_INDEX_URL,
                "official_methodology_url": B3_METHODOLOGY_URL,
                "unit": "index_points",
            },
            "data_provenance": {
                "provider": "Yahoo Finance",
                "provider_url": YAHOO_FINANCE_URL,
                "access_client": "yfinance",
                "access_client_version": extract.client_version,
                "access_client_url": YFINANCE_URL,
                "serialization_library": "pandas",
                "serialization_library_version": extract.serializer_version,
                "is_official_b3_source": False,
                "notice": (
                    "Yahoo Finance e yfinance nao sao fontes oficiais da B3; "
                    "yfinance e um cliente terceiro sem afiliacao oficial ao Yahoo."
                ),
            },
            "requested_period": {
                "start_inclusive": start.isoformat(),
                "end_inclusive": end.isoformat(),
            },
            "provider_call": parameters,
            "observed_content": asdict(summary),
            "file": {
                "path": relative_path.as_posix(),
                "classification": "provider-extract-not-raw-b3-data",
                "format": "csv",
                "encoding": "utf-8",
                "byte_count": len(extract.body),
                "sha256": sha256(extract.body).hexdigest(),
            },
            "transformations": [
                "yfinance converted the Yahoo response to a pandas DataFrame",
                "collector ordered OHLC, adjusted close and volume columns",
                "collector serialized dates as ISO-8601 and the table as UTF-8 CSV",
                "collector did not calculate returns or adjust prices",
            ],
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
