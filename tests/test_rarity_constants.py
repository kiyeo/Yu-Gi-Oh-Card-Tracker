import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.constants import RARITY_ABBREVIATIONS, RARITY_RANKING


class TestRarityConstants(unittest.TestCase):
    def test_key_abbreviations_are_correct(self):
        expected = {
            "Common": "C",
            "Normal Rare": "NR",
            "Rare": "R",
            "Super Rare": "SR",
            "Ultra Rare": "UR",
            "Secret Rare": "ScR",
            "Ultra Secret Rare": "UScR",
            "Secret Ultra Rare": "ScUR",
            "Prismatic Secret Rare": "PScR",
            "Extra Secret Rare": "EScR",
            "Platinum Secret Rare": "PlScR",
            "20th Secret Rare": "20ScR",
            "10000 Secret Rare": "10000ScR",
            "Quarter Century Secret Rare": "QCScR",
            "Ultimate Rare": "UtR",
            "Collector's Rare": "CR",
            "Starlight Rare": "StR",
            "Ghost Rare": "GR",
            "Holographic Rare": "HGR",
            "Parallel Rare": "PR",
            "Normal Parallel Rare": "NPR",
            "Super Parallel Rare": "SPR",
            "Ultra Parallel Rare": "UPR",
            "Secret Parallel Rare": "ScPR",
            "Extra Secret Parallel Rare": "EScPR",
            "Holographic Parallel Rare": "HGPR",
            "Gold Rare": "GUR",
            "Gold Secret Rare": "GScR",
            "Premium Gold Rare": "PGR",
            "Platinum Rare": "PlR",
            "Starfoil Rare": "SFR",
            "Mosaic Rare": "MSR",
            "Shatterfoil Rare": "SHR",
        }
        for full, abbr in expected.items():
            self.assertEqual(RARITY_ABBREVIATIONS.get(full), abbr, f"{full} -> {abbr}")

    def test_ranking_contains_all_primary_rarities(self):
        # Every full name in the corrected abbreviation table that is a primary
        # TCG rarity should also be rankable (so it appears in the filter and
        # sorts deterministically).
        primary = {
            "Common", "Normal Rare", "Rare", "Super Rare", "Ultra Rare",
            "Secret Rare", "Ultra Secret Rare", "Secret Ultra Rare",
            "Prismatic Secret Rare", "Extra Secret Rare", "Platinum Secret Rare",
            "20th Secret Rare", "10000 Secret Rare", "Quarter Century Secret Rare",
            "Ultimate Rare", "Collector's Rare", "Starlight Rare", "Ghost Rare",
            "Holographic Rare", "Parallel Rare", "Normal Parallel Rare",
            "Super Parallel Rare", "Ultra Parallel Rare", "Secret Parallel Rare",
            "Extra Secret Parallel Rare", "Holographic Parallel Rare",
            "Gold Rare", "Gold Secret Rare", "Premium Gold Rare", "Platinum Rare",
            "Starfoil Rare", "Mosaic Rare", "Shatterfoil Rare",
        }
        missing = primary - set(RARITY_RANKING)
        self.assertEqual(missing, set(), f"Missing from RARITY_RANKING: {missing}")

    def test_ranking_has_no_duplicates(self):
        self.assertEqual(len(RARITY_RANKING), len(set(RARITY_RANKING)))


if __name__ == '__main__':
    unittest.main()
