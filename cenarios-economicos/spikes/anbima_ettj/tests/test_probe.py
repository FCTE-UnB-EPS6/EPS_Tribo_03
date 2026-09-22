from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs

from spikes.anbima_ettj.probe import (
    AnbimaResponseError,
    build_form_body,
    collect_snapshot,
    parse_response,
)


SAMPLE_XML = b"""<CURVAZERO>
<DATA_REFERENCIA>16/09/2026</DATA_REFERENCIA>
<PARAMETROS>
  <PARAMETRO Grupo='PREFIXADOS' B1='0,131827310616397' B2='6,67090210699499E-03' B3='-8,55791255582199E-03' B4='4,22859141840763E-02' L1='5,32321208391387' L2='0,217781147886871' />
  <PARAMETRO Grupo='IPCA' B1='6,98220895579283E-02' B2='-7,15486824137971E-03' B3='-4,57793800075902E-02' B4='3,22230171603302E-02' L1='5,99985437623' L2='0,480617736541648' />
</PARAMETROS>
<ETTJ>
  <VERTICES Vertice='252' IPCA='6,6792' Prefixados='13,5503' Inflacao='6,4408' />
  <VERTICES Vertice='1.008' IPCA='7,7213' Prefixados='14,2270' Inflacao='6,0393' />
  <VERTICES Vertice='2.646' IPCA='7,5118' Prefixados='' Inflacao='' />
</ETTJ>
<CIRCULAR_3316>
  <CIRCULAR Vertices='21' Taxa='13,6476' />
  <CIRCULAR Vertices='1.008' Taxa='14,2270' />
</CIRCULAR_3316>
<ERROS>
  <ERRO Titulo='LTN' SELIC='100000' Vencimento='01/10/2026' Erro='-0,0047' />
</ERROS>
</CURVAZERO>"""


class AnbimaETTJSpikeTests(unittest.TestCase):
    def test_form_matches_the_observed_official_contract(self):
        form = parse_qs(build_form_body(date(2026, 9, 16)).decode("ascii"))

        self.assertEqual(form, {
            "Idioma": ["PT"],
            "Dt_Ref": ["16/09/2026"],
            "saida": ["xml"],
        })

    def test_parser_accepts_full_precision_parameters_and_sparse_tail(self):
        summary = parse_response(SAMPLE_XML, date(2026, 9, 16))

        self.assertEqual(summary.reference_date, "2026-09-16")
        self.assertEqual(summary.parameter_groups, ("IPCA", "PREFIXADOS"))
        self.assertEqual(summary.parameter_count, 2)
        self.assertEqual(summary.vertex_count, 3)
        self.assertEqual(summary.circular_rate_count, 2)
        self.assertEqual(summary.fitting_error_count, 1)

    def test_snapshot_preserves_exact_bytes_and_writes_manifest(self):
        calls = []

        def fetcher(reference_date, timeout):
            calls.append((reference_date, timeout))
            return SAMPLE_XML

        with TemporaryDirectory() as temporary:
            snapshot = collect_snapshot(
                temporary,
                date(2026, 9, 16),
                fetcher=fetcher,
                timeout=12,
                collected_at=datetime(2026, 9, 17, 15, 30, tzinfo=timezone.utc),
            )
            manifest = json.loads((snapshot / "manifest.json").read_text())
            raw = snapshot / manifest["file"]["path"]

            self.assertEqual(calls, [(date(2026, 9, 16), 12)])
            self.assertTrue(snapshot.name.startswith(
                "anbima-ettj-2026-09-16-20260917T153000Z-"
            ))
            self.assertEqual(raw.read_bytes(), SAMPLE_XML)
            self.assertEqual(manifest["status"], "experimental-spike")
            self.assertEqual(manifest["request"]["form"]["Dt_Ref"], "16/09/2026")
            self.assertEqual(manifest["observed_content"]["vertex_count"], 3)
            self.assertEqual(manifest["file"]["byte_count"], len(SAMPLE_XML))
            self.assertEqual(manifest["file"]["sha256"], sha256(SAMPLE_XML).hexdigest())

    def test_empty_or_wrong_date_response_is_not_published(self):
        cases = [
            b"",
            SAMPLE_XML.replace(b"16/09/2026", b"15/09/2026"),
        ]
        for body in cases:
            with self.subTest(body=body[:40]), TemporaryDirectory() as temporary:
                with self.assertRaises(AnbimaResponseError):
                    collect_snapshot(
                        temporary,
                        date(2026, 9, 16),
                        fetcher=lambda reference_date, timeout, result=body: result,
                    )
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_missing_curve_or_non_increasing_vertices_are_rejected(self):
        cases = [
            SAMPLE_XML.replace(b"Grupo='IPCA'", b"Grupo='OUTRA'"),
            SAMPLE_XML.replace(b"Vertice='1.008'", b"Vertice='126'", 1),
        ]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(AnbimaResponseError):
                parse_response(body, date(2026, 9, 16))

    def test_transport_must_return_bytes(self):
        with self.assertRaisesRegex(AnbimaResponseError, "retornar bytes"):
            parse_response(SAMPLE_XML.decode("ascii"), date(2026, 9, 16))

    def test_invalid_arguments_fail_before_transport(self):
        def unexpected_fetch(reference_date, timeout):
            self.fail("A rede nao deveria ser consultada.")

        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                collect_snapshot(temporary, "2026-09-16", fetcher=unexpected_fetch)
            with self.assertRaises(ValueError):
                collect_snapshot(
                    temporary,
                    date(2026, 9, 16),
                    fetcher=unexpected_fetch,
                    timeout=0,
                )


if __name__ == "__main__":
    unittest.main()
