import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import CollectionEntry, ApiCard, ApiCardImage, Collection
from src.services.collection_editor import CollectionEditor


class TestEditionMigration(unittest.TestCase):
    def test_old_first_edition_true_migrates(self):
        e = CollectionEntry(first_edition=True, quantity=1)
        self.assertEqual(e.edition, "1st Edition")
        self.assertTrue(e.first_edition)

    def test_old_first_edition_false_migrates(self):
        e = CollectionEntry(first_edition=False, quantity=1)
        self.assertEqual(e.edition, "Unlimited Edition")
        self.assertFalse(e.first_edition)

    def test_edition_only_sets_first_edition(self):
        e = CollectionEntry(edition="1st Edition", quantity=1)
        self.assertTrue(e.first_edition)
        e2 = CollectionEntry(edition="Limited Edition", quantity=1)
        self.assertFalse(e2.first_edition)
        self.assertEqual(e2.edition, "Limited Edition")

    def test_default_is_unlimited(self):
        e = CollectionEntry(quantity=1)
        self.assertEqual(e.edition, "Unlimited Edition")
        self.assertFalse(e.first_edition)

    def test_both_provided_edition_wins_for_limited(self):
        # Limited edition with first_edition False stays Limited.
        e = CollectionEntry(edition="Limited Edition", first_edition=False, quantity=1)
        self.assertEqual(e.edition, "Limited Edition")


class TestEditorEditionIdentity(unittest.TestCase):
    def _card(self):
        return ApiCard(
            id=1, name="X", type="Normal Monster", frameType="normal", desc="",
            card_images=[ApiCardImage(id=10, image_url="u", image_url_small="s")],
        )

    def test_editions_are_distinct_entries(self):
        col = Collection(name="c", cards=[])
        card = self._card()
        # Add 1 of each edition for the same set/rarity/lang/condition.
        for ed in ["1st Edition", "Unlimited Edition", "Limited Edition"]:
            CollectionEditor.apply_change(
                col, card, set_code="LOB-EN001", rarity="Ultra Rare",
                language="EN", quantity=1, condition="Near Mint",
                first_edition=(ed == "1st Edition"), mode="ADD", edition=ed,
            )
        variant = col.cards[0].variants[0]
        editions = sorted(e.edition for e in variant.entries)
        self.assertEqual(editions, ["1st Edition", "Limited Edition", "Unlimited Edition"])
        # Each entry has quantity 1 (not merged).
        self.assertTrue(all(e.quantity == 1 for e in variant.entries))

    def test_same_edition_merges(self):
        col = Collection(name="c", cards=[])
        card = self._card()
        for _ in range(3):
            CollectionEditor.apply_change(
                col, card, set_code="LOB-EN001", rarity="Ultra Rare",
                language="EN", quantity=1, condition="Near Mint",
                first_edition=False, mode="ADD", edition="Limited Edition",
            )
        variant = col.cards[0].variants[0]
        self.assertEqual(len(variant.entries), 1)
        self.assertEqual(variant.entries[0].quantity, 3)
        self.assertEqual(variant.entries[0].edition, "Limited Edition")

    def test_first_edition_only_still_works(self):
        # Backward-compat: caller passes only first_edition, no edition kwarg.
        col = Collection(name="c", cards=[])
        card = self._card()
        CollectionEditor.apply_change(
            col, card, set_code="LOB-EN001", rarity="Ultra Rare",
            language="EN", quantity=2, condition="Near Mint",
            first_edition=True, mode="ADD",
        )
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.edition, "1st Edition")
        self.assertTrue(entry.first_edition)


if __name__ == '__main__':
    unittest.main()
