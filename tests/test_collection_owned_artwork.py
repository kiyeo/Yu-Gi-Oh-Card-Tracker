import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import ApiCard, ApiCardImage, CollectionCard, CollectionVariant, CollectionEntry
from src.ui.collection import build_consolidated_vms


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
        # Owned variant references an image_id not present on the card -> ignored.
        owned = {
            1: _owned(1, [
                CollectionVariant(variant_id="vX", set_code="A-001", rarity="Common",
                                  image_id=999, entries=[CollectionEntry(quantity=5)]),
            ])
        }
        vms = build_consolidated_vms([card], owned)
        self.assertIsNone(vms[0].owned_image_id)

    def test_unowned_card_has_no_owned_image(self):
        card = _make_card()
        vms = build_consolidated_vms([card], {})
        self.assertFalse(vms[0].is_owned)
        self.assertIsNone(vms[0].owned_image_id)


class TestMatchOwnedArtworkConfig(unittest.TestCase):
    def test_config_getter_setter_roundtrip(self):
        import tempfile
        import importlib
        tmp = tempfile.mkdtemp()
        os.environ['OPENYUGI_CONFIG_FILE'] = os.path.join(tmp, 'config.json')
        import src.core.config as cfg
        importlib.reload(cfg)
        cm = cfg.ConfigManager()
        # Default is False.
        self.assertFalse(cm.get_match_owned_artwork())
        cm.set_match_owned_artwork(True)
        self.assertTrue(cm.get_match_owned_artwork())
        # Persisted and re-read.
        cm2 = cfg.ConfigManager()
        self.assertTrue(cm2.get_match_owned_artwork())
        os.environ.pop('OPENYUGI_CONFIG_FILE', None)


if __name__ == '__main__':
    unittest.main()
