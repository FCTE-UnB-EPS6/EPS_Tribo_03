"""Integrações de rede opt-in; nunca fazem parte da suíte determinística padrão."""

from datetime import date
import importlib.util
import os
from tempfile import TemporaryDirectory
import unittest

from app.data_sources.bacen import collect_snapshot as collect_bacen
from app.data_sources.ibovespa import collect_snapshot as collect_ibovespa
from spikes.anbima_ettj.probe import collect_snapshot as collect_anbima


RUN_LIVE = os.environ.get("ESG_RUN_LIVE_DATA_TESTS") == "1"
TIMEOUT = float(os.environ.get("ESG_LIVE_DATA_TIMEOUT", "30"))
ANBIMA_DATE = os.environ.get("ESG_LIVE_ANBIMA_DATE")


@unittest.skipUnless(RUN_LIVE, "Defina ESG_RUN_LIVE_DATA_TESTS=1 para acessar a rede.")
class LivePublicDataTests(unittest.TestCase):
    def test_bacen_sgs_live_contract(self):
        with TemporaryDirectory() as temporary:
            snapshot = collect_bacen(
                temporary,
                date(2024, 1, 1),
                date(2024, 3, 31),
                ["ipca"],
                timeout=TIMEOUT,
            )
            self.assertTrue((snapshot / "manifest.json").is_file())
            self.assertTrue(any((snapshot / "raw" / "ipca").iterdir()))

    @unittest.skipUnless(
        importlib.util.find_spec("yfinance"),
        "Instale requirements-data.txt para testar yfinance ao vivo.",
    )
    def test_ibovespa_provider_live_contract(self):
        with TemporaryDirectory() as temporary:
            snapshot = collect_ibovespa(
                temporary,
                date(2024, 1, 2),
                date(2024, 1, 8),
                timeout=TIMEOUT,
            )
            self.assertTrue((snapshot / "manifest.json").is_file())
            self.assertTrue(any((snapshot / "provider").iterdir()))

    @unittest.skipUnless(
        ANBIMA_DATE,
        "Defina ESG_LIVE_ANBIMA_DATE para testar o formulário experimental.",
    )
    def test_anbima_experimental_live_contract(self):
        try:
            reference_date = date.fromisoformat(ANBIMA_DATE)
        except ValueError:
            self.fail("ESG_LIVE_ANBIMA_DATE deve usar YYYY-MM-DD.")
        with TemporaryDirectory() as temporary:
            snapshot = collect_anbima(
                temporary,
                reference_date,
                timeout=TIMEOUT,
            )
            self.assertTrue((snapshot / "manifest.json").is_file())
            self.assertTrue(any((snapshot / "raw").iterdir()))


if __name__ == "__main__":
    unittest.main()
