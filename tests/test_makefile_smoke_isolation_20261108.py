"""Makefile smoke must route through the isolated launcher, without running it."""
from pathlib import Path
import unittest


class MakefileSmokeIsolation(unittest.TestCase):
    def test_smoke_has_no_production_target_or_direct_client(self):
        text = (Path(__file__).resolve().parents[1] / 'Makefile').read_text(encoding='utf-8')
        block = text.split('.PHONY: smoke\n', 1)[1].split('.PHONY: ci\n', 1)[0]
        self.assertIn('scripts/run_smoke_in_ci.py', block)
        self.assertNotIn('scripts/full_smoke_test.py', block)
        self.assertNotIn('--base-url', block)
        self.assertNotIn('app/run_server.py', block)
        self.assertIn('$(origin BASE_URL)', block)
        self.assertNotIn('BASE_URL ?= http://127.0.0.1:8080', text)


if __name__ == '__main__':
    unittest.main()
