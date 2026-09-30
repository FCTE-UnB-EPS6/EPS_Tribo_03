from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.data_sources.ibovespa import (
    IbovespaResponseError,
    ProviderExtract,
    collect_snapshot,
    download_parameters,
    validate_extract,
)


SAMPLE_CSV = (
    "Date,Open,High,Low,Close,Adj Close,Volume\n"
    "2026-09-14,178500.25,180000.5,177900.0,179500.75,179500.75,0\n"
    "2026-09-15,179500.75,181250.0,179100.5,180900.25,180900.25,0\n"
).encode("utf-8")


class IbovespaCollectorTests(unittest.TestCase):
    def test_parameters_make_the_inclusive_end_explicit(self):
        parameters = download_parameters(
            date(2026, 9, 14), date(2026, 9, 15), timeout=12
        )

        self.assertEqual(parameters["tickers"], "^BVSP")
        self.assertEqual(parameters["start"], "2026-09-14")
        self.assertEqual(parameters["end"], "2026-09-16")
        self.assertEqual(parameters["interval"], "1d")
        self.assertEqual(parameters["timeout"], 12)
        self.assertFalse(parameters["auto_adjust"])
        self.assertFalse(parameters["repair"])
        self.assertFalse(parameters["rounding"])
        self.assertFalse(parameters["threads"])

    def test_valid_extract_returns_observed_boundaries(self):
        summary = validate_extract(
            SAMPLE_CSV, date(2026, 9, 14), date(2026, 9, 15)
        )

        self.assertEqual(summary.record_count, 2)
        self.assertEqual(summary.first_date, "2026-09-14")
        self.assertEqual(summary.last_date, "2026-09-15")

    def test_snapshot_preserves_provider_extract_and_manifest(self):
        calls = []

        def fetcher(start, end, timeout):
            calls.append((start, end, timeout))
            return ProviderExtract(SAMPLE_CSV, "1.7.0", "3.0.5")

        with TemporaryDirectory() as temporary:
            snapshot = collect_snapshot(
                temporary,
                date(2026, 9, 14),
                date(2026, 9, 15),
                fetcher=fetcher,
                timeout=12,
                collected_at=datetime(2026, 9, 17, 15, 30, tzinfo=timezone.utc),
            )
            manifest = json.loads((snapshot / "manifest.json").read_text())
            extracted = snapshot / manifest["file"]["path"]

            self.assertEqual(calls, [(
                date(2026, 9, 14), date(2026, 9, 15), 12
            )])
            self.assertTrue(snapshot.name.startswith(
                "ibovespa-yahoo-20260917T153000Z-"
            ))
            self.assertEqual(extracted.read_bytes(), SAMPLE_CSV)
            self.assertEqual(manifest["file"]["sha256"], sha256(SAMPLE_CSV).hexdigest())
            self.assertEqual(manifest["file"]["byte_count"], len(SAMPLE_CSV))
            self.assertEqual(
                manifest["file"]["classification"],
                "provider-extract-not-raw-b3-data",
            )
            self.assertFalse(
                manifest["data_provenance"]["is_official_b3_source"]
            )
            self.assertEqual(
                manifest["data_provenance"]["access_client_version"], "1.7.0"
            )
            self.assertEqual(
                manifest["data_provenance"]["serialization_library_version"],
                "3.0.5",
            )
            self.assertEqual(manifest["observed_content"]["record_count"], 2)
            self.assertEqual(manifest["provider_call"]["end"], "2026-09-16")

    def test_invalid_extract_never_publishes_a_partial_snapshot(self):
        invalid_bodies = [
            b"Date,Open,High,Low,Close,Adj Close,Volume\n",
            SAMPLE_CSV.replace(b"2026-09-15", b"2026-09-13"),
            SAMPLE_CSV.replace(b"179500.75", b"NaN", 1),
            SAMPLE_CSV.replace(b",0\n", b",-1\n", 1),
        ]
        for body in invalid_bodies:
            with self.subTest(body=body), TemporaryDirectory() as temporary:
                with self.assertRaises(IbovespaResponseError):
                    collect_snapshot(
                        temporary,
                        date(2026, 9, 14),
                        date(2026, 9, 15),
                        fetcher=lambda start, end, timeout, value=body: ProviderExtract(
                            value, "1.7.0", "3.0.5"
                        ),
                    )
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_wrong_header_duplicate_and_non_bytes_are_rejected(self):
        cases = [
            SAMPLE_CSV.replace(b"Adj Close,", b""),
            SAMPLE_CSV.replace(b"2026-09-15", b"2026-09-14"),
            SAMPLE_CSV.decode("utf-8"),
        ]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(IbovespaResponseError):
                validate_extract(body, date(2026, 9, 14), date(2026, 9, 15))

    def test_invalid_arguments_fail_before_transport(self):
        def unexpected_fetch(start, end, timeout):
            self.fail("A rede nao deveria ser consultada.")

        invalid = [
            ("2026-09-14", date(2026, 9, 15), 30),
            (date(2026, 9, 16), date(2026, 9, 15), 30),
            (date(2026, 9, 14), date(2026, 9, 15), 0),
        ]
        with TemporaryDirectory() as temporary:
            for start, end, timeout in invalid:
                with self.subTest(start=start, end=end, timeout=timeout):
                    with self.assertRaises(ValueError):
                        collect_snapshot(
                            temporary,
                            start,
                            end,
                            fetcher=unexpected_fetch,
                            timeout=timeout,
                        )

    def test_fetcher_contract_is_explicit(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                IbovespaResponseError, "ProviderExtract"
            ):
                collect_snapshot(
                    temporary,
                    date(2026, 9, 14),
                    date(2026, 9, 15),
                    fetcher=lambda start, end, timeout: SAMPLE_CSV,
                )


if __name__ == "__main__":
    unittest.main()
