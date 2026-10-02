import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import Collection, CollectionCard, CollectionVariant, CollectionEntry
import src.services.printing_image_service as svc


def _collection():
    return Collection(name="c", cards=[
        CollectionCard(card_id=1, name="Stardust Dragon", variants=[
            CollectionVariant(variant_id="v1", set_code="TDGS-EN040", rarity="Ultra Rare",
                              entries=[CollectionEntry(quantity=1, language="EN"),
                                       CollectionEntry(quantity=2, language="DE")]),
        ]),
        CollectionCard(card_id=2, name="Sogen", variants=[
            # Custom / no set code -> skipped.
            CollectionVariant(variant_id="v2", set_code="", rarity="Common",
                              entries=[CollectionEntry(quantity=1, language="EN")]),
            CollectionVariant(variant_id="v3", set_code="SDK-EN020", rarity="Common",
                              entries=[CollectionEntry(quantity=0, language="EN")]),  # qty 0 -> skipped
        ]),
    ])


class TestCollectOwnedPrintings(unittest.TestCase):
    def test_collects_distinct_set_code_language_rarity_tuples(self):
        with patch.object(svc.persistence, 'list_collections', return_value=['c.json']), \
             patch.object(svc.persistence, 'load_collection', return_value=_collection()):
            pending = svc._collect_owned_printings()

        self.assertEqual(set(pending.keys()), {
            ("TDGS-EN040", "EN", "Ultra Rare"),
            ("TDGS-EN040", "DE", "Ultra Rare"),
        })
        self.assertEqual(pending[("TDGS-EN040", "EN", "Ultra Rare")], "Stardust Dragon")


class TestDownloadOwnedPrintingImages(unittest.TestCase):
    def test_summary_counts_downloaded_and_skipped(self):
        pending = {("TDGS-EN040", "EN", "Ultra Rare"): "Stardust Dragon",
                   ("LOB-EN005", "EN", "Ultra Rare"): "Dark Magician"}

        async def fake_resolve(name, set_code, lang, rarity=None):
            return f"https://img/{set_code}-{lang}-{rarity}.png"

        async def fake_ensure(set_code, lang, url, rarity=""):
            return f"/local/{set_code}"

        # One already cached (LOB), one needs download (TDGS).
        def exists(set_code, lang, rarity=""):
            return set_code == "LOB-EN005"

        with patch.object(svc, '_collect_owned_printings', return_value=pending), \
             patch.object(svc.image_manager, 'printing_image_exists', side_effect=exists), \
             patch.object(svc.image_manager, 'ensure_printing_image', side_effect=fake_ensure), \
             patch.object(svc.YugipediaService, 'get_set_printing_image_url', side_effect=fake_resolve):
            summary = asyncio.run(svc.download_owned_printing_images())

        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['skipped'], 1)       # LOB already cached
        self.assertEqual(summary['downloaded'], 1)    # TDGS downloaded
        self.assertEqual(summary['failed'], 0)


if __name__ == '__main__':
    unittest.main()
