import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import ApiCard, ApiCardImage, ApiCardSet, CollectionCard, CollectionVariant, CollectionEntry
from src.ui.collection import build_consolidated_vms, build_collector_rows, resolve_printing_image_id
from src.core.config import config_manager


def _make_card() -> ApiCard:
    return ApiCard(
        id=1,
        name="Blue-Eyes White Dragon",
        type="Normal Monster",
        frameType="normal",
        desc="",
        card_images=[
            ApiCardImage(id=100, image_url="u100", image_url_small="s100"),
            ApiCardImage(id=200, image_url="u200", image_url_small="s200"),
            ApiCardImage(id=300, image_url="u300", image_url_small="s300"),
        ],
    )


def _owned(card_id, variants):
    return CollectionCard(card_id=card_id, name="X", variants=variants)


class TestOwnedArtwork(unittest.TestCase):
    def test_owned_image_id_picks_most_owned_variant(self):
        card = _make_card()
        # Own 1 copy of artwork 200 and 3 copies of artwork 300 -> expect 300.
        owned = {
            1: _owned(1, [
                CollectionVariant(variant_id="v200", set_code="A-001", rarity="Common",
                                  image_id=200, entries=[CollectionEntry(quantity=1)]),
                CollectionVariant(variant_id="v300", set_code="B-001", rarity="Common",
                                  image_id=300, entries=[CollectionEntry(quantity=3)]),
            ])
        }
        vms = build_consolidated_vms([card], owned)
        self.assertEqual(len(vms), 1)
        self.assertTrue(vms[0].is_owned)
        self.assertEqual(vms[0].owned_image_id, 300)

    def test_owned_image_id_ignores_invalid_image(self):
        card = _make_card()
        # Owned variant references an image_id not present on the card; with no
        # matching set art, resolution falls back to the card default (100).
        owned = {
            1: _owned(1, [
                CollectionVariant(variant_id="vX", set_code="A-001", rarity="Common",
                                  image_id=999, entries=[CollectionEntry(quantity=5)]),
            ])
        }
        vms = build_consolidated_vms([card], owned)
        self.assertEqual(vms[0].owned_image_id, 100)

    def test_unowned_card_has_no_owned_image(self):
        card = _make_card()
        vms = build_consolidated_vms([card], {})
        self.assertFalse(vms[0].is_owned)
        self.assertIsNone(vms[0].owned_image_id)


class TestMatchOwnedArtworkConfig(unittest.TestCase):
    def test_config_getter_setter_roundtrip(self):
        import tempfile
        from src.core.config import ConfigManager
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'config.json')
        prev = os.environ.get('OPENYUGI_CONFIG_FILE')
        os.environ['OPENYUGI_CONFIG_FILE'] = path
        try:
            cm = ConfigManager()
            self.assertFalse(cm.get_match_owned_artwork())
            cm.set_match_owned_artwork(True)
            self.assertTrue(cm.get_match_owned_artwork())
            # Persisted and re-read by a fresh instance pointed at the same file.
            cm2 = ConfigManager()
            self.assertTrue(cm2.get_match_owned_artwork())
        finally:
            if prev is None:
                os.environ.pop('OPENYUGI_CONFIG_FILE', None)
            else:
                os.environ['OPENYUGI_CONFIG_FILE'] = prev


class TestResolvePrintingImageId(unittest.TestCase):
    def _card_with_set_art(self):
        # Card with 2 artworks; set B-001 printing maps to the alt art (200).
        return ApiCard(
            id=1, name="X", type="Normal Monster", frameType="normal", desc="",
            card_images=[
                ApiCardImage(id=100, image_url="u100", image_url_small="s100"),
                ApiCardImage(id=200, image_url="u200", image_url_small="s200"),
            ],
            card_sets=[
                ApiCardSet(set_name="A", set_code="A-001", set_rarity="Common", card_image_id=100),
                ApiCardSet(set_name="B", set_code="B-001", set_rarity="Common", card_image_id=200),
            ],
        )

    def test_explicit_id_wins(self):
        card = self._card_with_set_art()
        self.assertEqual(resolve_printing_image_id(card, "A-001", "Common", 200), 200)

    def test_resolves_from_matching_set_when_no_explicit_id(self):
        card = self._card_with_set_art()
        # No explicit id -> use the set's art for B-001 (200).
        self.assertEqual(resolve_printing_image_id(card, "B-001", "Common", None), 200)

    def test_falls_back_to_default_when_unknown(self):
        card = self._card_with_set_art()
        self.assertEqual(resolve_printing_image_id(card, "ZZZ-999", "Common", None), 100)


class TestCollectorRowOwnedArtwork(unittest.TestCase):
    def _card(self):
        return ApiCard(
            id=1, name="X", type="Normal Monster", frameType="normal", desc="",
            card_images=[
                ApiCardImage(id=100, image_url="u100", image_url_small="s100"),
                ApiCardImage(id=200, image_url="u200", image_url_small="s200"),
            ],
            card_sets=[
                ApiCardSet(set_name="A", set_code="A-001", set_rarity="Common", card_image_id=100),
            ],
        )

    def test_owned_row_uses_explicit_art_when_setting_on(self):
        card = self._card()
        owned = {1: CollectionCard(card_id=1, name="X", variants=[
            CollectionVariant(variant_id="v", set_code="A-001", rarity="Common",
                              image_id=200, entries=[CollectionEntry(quantity=1)]),
        ])}
        from unittest.mock import patch
        with patch.object(config_manager, 'get_match_owned_artwork', return_value=True):
            rows = build_collector_rows([card], owned, "en")
        owned_rows = [r for r in rows if r.is_owned]
        self.assertTrue(owned_rows)
        self.assertEqual(owned_rows[0].image_id, 200)
        self.assertEqual(owned_rows[0].image_url, "s200")


if __name__ == '__main__':
    unittest.main()
