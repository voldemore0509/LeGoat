# -*- coding: utf-8 -*-
"""Tests unitaires."""
from __future__ import annotations

import unittest
from pathlib import Path

from .chat import ChatSession
from .assets import LogoLoader

# ============================================================
# Tests unitaires
# ============================================================

class TestChatSession(unittest.TestCase):
    """Tests de la logique de session de chat."""

    def test_normalize(self):
        s = ChatSession()
        s.submit("  Bonjour   Le Goat  ")
        self.assertEqual(s.messages[0], ("Vous", "Bonjour Le Goat"))

    def test_empty_ignored(self):
        s = ChatSession()
        self.assertEqual(s.submit("   "), "")


class TestLogo(unittest.TestCase):
    """Tests du chargement des ressources graphiques."""

    def test_fallback(self):
        uri = LogoLoader.get_data_uri([Path("/no/such/file")])
        self.assertTrue(uri.startswith("data:image/svg+xml,"))


def run_tests() -> None:
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestChatSession))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestLogo))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


