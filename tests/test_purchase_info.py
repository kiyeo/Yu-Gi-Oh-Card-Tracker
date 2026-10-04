import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.models import (
    Collection, CollectionCard, CollectionVariant, CollectionEntry,
    ApiCard, ApiCardImage,
)
from src.services.collection_editor import CollectionEditor


class TestScanTimestampField(unittest.TestCase):
    def test_scan_timestamp_defaults_none_and_is_independent(self):
        e = CollectionEntry(quantity=1)
        self.assertIsNone(e.scan_timestamp)
        self.assertIsNone(e.purchase_date)
        e.scan_timestamp = "2026-01-01T00:00:00"
        self.assertIsNone(e.purchase_date)  # not clobbered

    def test_roundtrip_preserves_both(self):
        e = CollectionEntry(quantity=1, purchase_date="2025-05-05", scan_timestamp="2026-01-01T00:00:00")
        reloaded = CollectionEntry(**e.model_dump())
        self.assertEqual(reloaded.purchase_date, "2025-05-05")
        self.assertEqual(reloaded.scan_timestamp, "2026-01-01T00:00:00")


class TestSetEntryPurchaseInfo(unittest.TestCase):
    def _collection(self):
        return Collection(name="c", cards=[
            CollectionCard(card_id=1, name="X", variants=[
                CollectionVariant(variant_id="v1", set_code="LOB-EN001", rarity="Ultra Rare", entries=[
                    CollectionEntry(quantity=2, language="EN", condition="Near Mint",
                                    edition="1st Edition", first_edition=True, storage_location="Binder"),
                    CollectionEntry(quantity=1, language="EN", condition="Near Mint",
                                    edition="Unlimited Edition", first_edition=False, storage_location="Binder"),
                ]),
            ]),
        ])

    def test_updates_only_targeted_entry(self):
        col = self._collection()
        ok = CollectionEditor.set_entry_purchase_info(
            col, card_id=1, variant_id="v1", language="EN", condition="Near Mint",
            storage_location="Binder", edition="1st Edition", first_edition=True,
            purchase_price=12.50, purchase_date="2025-03-01",
        )
        self.assertTrue(ok)
        entries = col.cards[0].variants[0].entries
        first = next(e for e in entries if e.edition == "1st Edition")
        unl = next(e for e in entries if e.edition == "Unlimited Edition")
        self.assertEqual(first.purchase_price, 12.50)
        self.assertEqual(first.purchase_date, "2025-03-01")
        # The other stack is untouched, and quantities are preserved.
        self.assertEqual(unl.purchase_price, 0.0)
        self.assertIsNone(unl.purchase_date)
        self.assertEqual(first.quantity, 2)
        self.assertEqual(unl.quantity, 1)

    def test_returns_false_when_entry_absent(self):
        col = self._collection()
        ok = CollectionEditor.set_entry_purchase_info(
            col, card_id=1, variant_id="v1", language="DE", condition="Near Mint",
            storage_location="Binder", edition="1st Edition", first_edition=True,
            purchase_price=5.0,
        )
        self.assertFalse(ok)

    def test_only_sets_provided_fields(self):
        col = self._collection()
        # Set only price; date stays None.
        CollectionEditor.set_entry_purchase_info(
            col, card_id=1, variant_id="v1", language="EN", condition="Near Mint",
            storage_location="Binder", edition="Unlimited Edition", first_edition=False,
            purchase_price=3.0,
        )
        unl = next(e for e in col.cards[0].variants[0].entries if e.edition == "Unlimited Edition")
        self.assertEqual(unl.purchase_price, 3.0)
        self.assertIsNone(unl.purchase_date)

    def test_multi_stack_card_each_stack_addressable(self):
        # Ryko-style: 3 distinct stacks across two variants (different sets),
        # each independently editable by (variant_id, lang, cond, edition, storage).
        col = Collection(name="c", cards=[
            CollectionCard(card_id=99, name="Ryko, Lightsworn Hunter", variants=[
                CollectionVariant(variant_id="va", set_code="LODT-EN035", rarity="Ultra Rare", entries=[
                    CollectionEntry(quantity=1, language="EN", condition="Near Mint",
                                    edition="1st Edition", first_edition=True, storage_location="Binder A"),
                    CollectionEntry(quantity=2, language="EN", condition="Played",
                                    edition="Unlimited Edition", first_edition=False, storage_location="Bulk"),
                ]),
                CollectionVariant(variant_id="vb", set_code="BP02-EN044", rarity="Mosaic Rare", entries=[
                    CollectionEntry(quantity=1, language="DE", condition="Near Mint",
                                    edition="Unlimited Edition", first_edition=False, storage_location=None),
                ]),
            ]),
        ])
        # Enumerate all owned stacks (mirrors the UI list logic).
        stacks = [(v, e) for c in col.cards if c.card_id == 99 for v in c.variants for e in v.entries if e.quantity > 0]
        self.assertEqual(len(stacks), 3)

        # Edit each stack's purchase info independently.
        targets = [
            ("va", "EN", "Near Mint", "1st Edition", True, "Binder A", 9.99, "2025-01-01"),
            ("va", "EN", "Played", "Unlimited Edition", False, "Bulk", 1.50, "2025-02-02"),
            ("vb", "DE", "Near Mint", "Unlimited Edition", False, None, 4.25, "2025-03-03"),
        ]
        for vid, lang, cond, ed, fe, store, price, date in targets:
            ok = CollectionEditor.set_entry_purchase_info(
                col, card_id=99, variant_id=vid, language=lang, condition=cond,
                storage_location=store, edition=ed, first_edition=fe,
                purchase_price=price, purchase_date=date,
            )
            self.assertTrue(ok, f"stack {vid}/{lang}/{cond}/{ed} should be addressable")

        # Verify each landed on the right stack and didn't bleed into others.
        all_entries = [e for c in col.cards for v in c.variants for e in v.entries]
        prices = sorted(e.purchase_price for e in all_entries)
        self.assertEqual(prices, [1.50, 4.25, 9.99])


if __name__ == '__main__':
    unittest.main()
