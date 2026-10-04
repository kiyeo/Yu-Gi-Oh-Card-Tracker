import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import (
    Collection, CollectionCard, CollectionVariant, CollectionEntry, PurchaseLot,
    ApiCard, ApiCardImage,
)
from src.services.collection_editor import CollectionEditor


def _card(card_id=1, name="X"):
    return ApiCard(id=card_id, name=name, type="Normal Monster", frameType="normal",
                   desc="", card_images=[ApiCardImage(id=10, image_url="u", image_url_small="s")])


class TestScanTimestampField(unittest.TestCase):
    def test_scan_timestamp_independent_of_purchase_date(self):
        e = CollectionEntry(quantity=1)
        e.scan_timestamp = "2026-01-01T00:00:00"
        self.assertIsNone(e.purchase_date)


class TestLotMigration(unittest.TestCase):
    def test_legacy_entry_migrates_to_single_lot(self):
        e = CollectionEntry(quantity=3, purchase_price=5.0, purchase_date="2025-01-01")
        self.assertEqual(len(e.purchases), 1)
        self.assertEqual(e.purchases[0].quantity, 3)
        self.assertEqual(e.purchases[0].purchase_price, 5.0)
        self.assertEqual(e.purchases[0].purchase_date, "2025-01-01")
        self.assertEqual(e.quantity, 3)

    def test_quantity_is_sum_of_lots(self):
        e = CollectionEntry(purchases=[
            PurchaseLot(quantity=2, purchase_price=5.0),
            PurchaseLot(quantity=1, purchase_price=8.0),
        ])
        self.assertEqual(e.quantity, 3)
        # Compat mirror reflects the first (primary) lot.
        self.assertEqual(e.purchase_price, 5.0)

    def test_roundtrip_preserves_lots(self):
        e = CollectionEntry(purchases=[
            PurchaseLot(quantity=2, purchase_price=5.0, purchase_date="2025-01-01"),
            PurchaseLot(quantity=1, purchase_price=8.0, purchase_date="2025-06-01"),
        ])
        reloaded = CollectionEntry(**e.model_dump())
        self.assertEqual(len(reloaded.purchases), 2)
        self.assertEqual(reloaded.quantity, 3)
        self.assertEqual(reloaded.purchases[1].purchase_price, 8.0)


class TestApplyChangeLots(unittest.TestCase):
    def test_add_creates_new_lot_with_its_own_price(self):
        col = Collection(name="c", cards=[])
        card = _card()
        # First purchase: 2 @ 5.0
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 2,
                                      "Near Mint", False, mode="ADD",
                                      edition="Unlimited Edition",
                                      purchase_price=5.0, purchase_date="2025-01-01")
        # Later purchase of the SAME stack: 1 @ 8.0 -> new lot, not merged.
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 1,
                                      "Near Mint", False, mode="ADD",
                                      edition="Unlimited Edition",
                                      purchase_price=8.0, purchase_date="2025-06-01")
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.quantity, 3)
        self.assertEqual(len(entry.purchases), 2)
        self.assertEqual(entry.purchases[0].purchase_price, 5.0)
        self.assertEqual(entry.purchases[1].purchase_price, 8.0)

    def test_subtract_drains_oldest_lots_first(self):
        col = Collection(name="c", cards=[])
        card = _card()
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 2,
                                      "Near Mint", False, mode="ADD",
                                      purchase_price=5.0, purchase_date="2025-01-01")
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 2,
                                      "Near Mint", False, mode="ADD",
                                      purchase_price=8.0, purchase_date="2025-06-01")
        # Remove 3 -> drains the first lot (2) then 1 from the second.
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", -3,
                                      "Near Mint", False, mode="ADD")
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.quantity, 1)
        self.assertEqual(len(entry.purchases), 1)
        self.assertEqual(entry.purchases[0].purchase_price, 8.0)  # oldest fully drained

    def test_new_lot_defaults_date_to_today(self):
        import datetime
        col = Collection(name="c", cards=[])
        card = _card()
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 1,
                                      "Near Mint", False, mode="ADD", purchase_price=5.0)
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.purchases[0].purchase_date, datetime.date.today().isoformat())

    def test_explicit_date_is_respected(self):
        col = Collection(name="c", cards=[])
        card = _card()
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 1,
                                      "Near Mint", False, mode="ADD",
                                      purchase_price=5.0, purchase_date="2024-12-25")
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.purchases[0].purchase_date, "2024-12-25")

    def test_remove_all_deletes_stack(self):
        col = Collection(name="c", cards=[])
        card = _card()
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 2,
                                      "Near Mint", False, mode="ADD", purchase_price=5.0)
        CollectionEditor.apply_change(col, card, "LOB-EN001", "Ultra Rare", "EN", 0,
                                      "Near Mint", False, mode="SET")
        self.assertEqual(col.cards, [])


class TestSetLotPurchaseInfo(unittest.TestCase):
    def test_edits_single_lot_only(self):
        col = Collection(name="c", cards=[
            CollectionCard(card_id=1, name="X", variants=[
                CollectionVariant(variant_id="v1", set_code="LOB-EN001", rarity="Ultra Rare", entries=[
                    CollectionEntry(language="EN", condition="Near Mint",
                                    edition="Unlimited Edition", storage_location="Binder",
                                    purchases=[
                                        PurchaseLot(quantity=2, purchase_price=5.0, purchase_date="2025-01-01"),
                                        PurchaseLot(quantity=1, purchase_price=8.0, purchase_date="2025-06-01"),
                                    ]),
                ]),
            ]),
        ])
        ok = CollectionEditor.set_lot_purchase_info(
            col, card_id=1, variant_id="v1", language="EN", condition="Near Mint",
            storage_location="Binder", lot_index=1, edition="Unlimited Edition",
            purchase_price=9.99, purchase_date="2025-07-07",
        )
        self.assertTrue(ok)
        entry = col.cards[0].variants[0].entries[0]
        self.assertEqual(entry.purchases[0].purchase_price, 5.0)   # untouched
        self.assertEqual(entry.purchases[1].purchase_price, 9.99)  # edited
        self.assertEqual(entry.purchases[1].purchase_date, "2025-07-07")
        self.assertEqual(entry.quantity, 3)  # unchanged

    def test_bad_lot_index_returns_false(self):
        col = Collection(name="c", cards=[
            CollectionCard(card_id=1, name="X", variants=[
                CollectionVariant(variant_id="v1", set_code="LOB-EN001", rarity="Ultra Rare", entries=[
                    CollectionEntry(language="EN", condition="Near Mint",
                                    edition="Unlimited Edition", storage_location="Binder",
                                    purchases=[PurchaseLot(quantity=1, purchase_price=5.0)]),
                ]),
            ]),
        ])
        self.assertFalse(CollectionEditor.set_lot_purchase_info(
            col, 1, "v1", "EN", "Near Mint", "Binder", lot_index=5,
            edition="Unlimited Edition", purchase_price=1.0))


if __name__ == '__main__':
    unittest.main()
