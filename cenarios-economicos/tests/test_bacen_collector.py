from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs, urlparse

from app.data_sources.bacen import (
    BacenResponseError,
    MAX_WINDOW_DAYS,
    SERIES,
    build_series_url,
    collect_snapshot,
    date_windows,
)


class BacenCollectorTests(unittest.TestCase):
    def test_windows_cover_the_period_without_overlap(self):
        start = date(2000, 1, 1)
        end = date(2026, 9, 17)
        windows = list(date_windows(start, end))

        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], end)
        for current, following in zip(windows, windows[1:]):
            self.assertEqual(following[0], current[1] + timedelta(days=1))
        self.assertTrue(all((window_end - window_start).days <= MAX_WINDOW_DAYS
                            for window_start, window_end in windows))

    def test_url_contains_series_and_inclusive_dates(self):
        url = build_series_url(433, date(2025, 1, 2), date(2025, 3, 4))
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertTrue(parsed.path.endswith("bcdata.sgs.433/dados"))
        self.assertEqual(query, {
            "formato": ["json"],
            "dataInicial": ["02/01/2025"],
            "dataFinal": ["04/03/2025"],
        })

    def test_snapshot_preserves_raw_bytes_and_writes_auditable_manifest(self):
        bodies = []

        def fetcher(url, timeout):
            query = parse_qs(urlparse(url).query)
            record = [{
                "data": query["dataInicial"][0],
                "valor": "4.2500",
            }]
            body = ("  " + json.dumps(record, separators=(",", ":")) + "\n").encode()
            bodies.append((url, timeout, body))
            return body

        with TemporaryDirectory() as temporary:
            snapshot = collect_snapshot(
                temporary,
                date(2025, 1, 1),
                date(2025, 1, 2),
                ["ipca", "usd_brl"],
                fetcher=fetcher,
                timeout=12,
                collected_at=datetime(2026, 9, 17, 15, 30, tzinfo=timezone.utc),
            )
            manifest = json.loads((snapshot / "manifest.json").read_text())

            self.assertTrue(snapshot.name.startswith("bacen-sgs-20260917T153000Z-"))
            self.assertEqual(manifest["schema_version"], "1.0.0")
            self.assertEqual(manifest["collected_at"], "2026-09-17T15:30:00Z")
            self.assertEqual(manifest["requested_period"], {
                "start": "2025-01-01",
                "end": "2025-01-02",
            })
            self.assertEqual([item["key"] for item in manifest["series"]],
                             ["ipca", "usd_brl"])
            self.assertEqual(len(bodies), 2)

            for series_entry, (_, timeout, body) in zip(manifest["series"], bodies):
                file_entry = series_entry["files"][0]
                raw = snapshot / file_entry["path"]
                self.assertEqual(timeout, 12)
                self.assertEqual(raw.read_bytes(), body)
                self.assertEqual(file_entry["byte_count"], len(body))
                self.assertEqual(file_entry["sha256"], sha256(body).hexdigest())
                self.assertEqual(file_entry["record_count"], 1)
                self.assertEqual(series_entry["record_count"], 1)
                self.assertEqual(series_entry["code"], SERIES[series_entry["key"]].code)

    def test_long_period_keeps_each_raw_window(self):
        def fetcher(url, timeout):
            query = parse_qs(urlparse(url).query)
            return json.dumps([{
                "data": query["dataInicial"][0],
                "valor": "1",
            }]).encode()

        start = date(2000, 1, 1)
        end = start + timedelta(days=MAX_WINDOW_DAYS + 5)
        with TemporaryDirectory() as temporary:
            snapshot = collect_snapshot(
                temporary, start, end, ["selic_daily"], fetcher=fetcher
            )
            manifest = json.loads((snapshot / "manifest.json").read_text())
            files = manifest["series"][0]["files"]

            self.assertEqual(len(files), 2)
            self.assertEqual(files[0]["window"]["end"],
                             (start + timedelta(days=MAX_WINDOW_DAYS)).isoformat())
            self.assertEqual(files[1]["window"]["start"],
                             (start + timedelta(days=MAX_WINDOW_DAYS + 1)).isoformat())
            self.assertTrue(all((snapshot / item["path"]).is_file() for item in files))

    def test_invalid_response_does_not_publish_partial_snapshot(self):
        calls = 0

        def fetcher(url, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                return b'[{"data":"01/01/2025","valor":"1"}]'
            return b'{"erro":"indisponivel"}'

        with TemporaryDirectory() as temporary:
            with self.assertRaises(BacenResponseError):
                collect_snapshot(
                    temporary,
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    ["ipca", "igpm"],
                    fetcher=fetcher,
                )
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_empty_series_is_rejected_without_snapshot(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(BacenResponseError, "nao retornou registros"):
                collect_snapshot(
                    temporary,
                    date(2025, 1, 1),
                    date(2025, 1, 31),
                    ["ipca"],
                    fetcher=lambda url, timeout: b"[]",
                )
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_invalid_arguments_are_rejected_before_network_access(self):
        def unexpected_fetch(url, timeout):
            self.fail("A rede nao deveria ser consultada.")

        with TemporaryDirectory() as temporary:
            invalid = [
                (date(2025, 2, 1), date(2025, 1, 1), ["ipca"]),
                (date(2025, 1, 1), date(2025, 2, 1), []),
                (date(2025, 1, 1), date(2025, 2, 1), ["unknown"]),
                (date(2025, 1, 1), date(2025, 2, 1), ["ipca", "ipca"]),
            ]
            for start, end, selected in invalid:
                with self.subTest(selected=selected), self.assertRaises(ValueError):
                    collect_snapshot(
                        temporary, start, end, selected, fetcher=unexpected_fetch
                    )


if __name__ == "__main__":
    unittest.main()
