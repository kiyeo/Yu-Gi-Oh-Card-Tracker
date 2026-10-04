from src.core.models import Collection, CollectionCard, CollectionVariant, CollectionEntry, PurchaseLot, ApiCard
from src.core.utils import generate_variant_id
from typing import Optional
from datetime import date


def _lot_date(purchase_date: Optional[str]) -> str:
    """Resolve a lot's purchase date: use the provided one, else today (ISO)."""
    if purchase_date:
        return purchase_date
    return date.today().isoformat()


def _edition_from(first_edition: bool, edition: Optional[str]) -> str:
    """Resolve the effective edition string from the (edition, first_edition)
    inputs, defaulting sensibly for callers that only pass first_edition."""
    if edition:
        return edition
    return "1st Edition" if first_edition else "Unlimited Edition"


class CollectionEditor:
    @staticmethod
    def _drain_lots(entry: CollectionEntry, amount: int) -> None:
        """Remove `amount` copies from an entry's purchase lots, oldest first.

        Lots that reach zero are dropped. The caller should call
        entry.sync_quantity() afterwards (or rely on apply_change doing so).
        """
        remaining = amount
        for lot in list(entry.purchases):
            if remaining <= 0:
                break
            take = min(lot.quantity, remaining)
            lot.quantity -= take
            remaining -= take
        entry.purchases = [lot for lot in entry.purchases if lot.quantity > 0]

    @staticmethod
    def get_quantity(
        collection: Collection,
        card_id: int,
        variant_id: Optional[str] = None,
        set_code: Optional[str] = None,
        rarity: Optional[str] = None,
        image_id: Optional[int] = None,
        language: str = 'EN',
        condition: str = 'Near Mint',
        first_edition: bool = False,
        storage_location: Optional[str] = None,
        edition: Optional[str] = None,
    ) -> int:
        """
        Returns the quantity of a specific card entry (specific storage location).
        """
        eff_edition = _edition_from(first_edition, edition)
        target_card = next((c for c in collection.cards if c.card_id == card_id), None)
        if not target_card:
            return 0

        target_variant_id = variant_id
        if not target_variant_id and set_code and rarity:
             target_variant_id = generate_variant_id(card_id, set_code, rarity, image_id)

        if not target_variant_id:
            return 0

        target_variant = next((v for v in target_card.variants if v.variant_id == target_variant_id), None)
        if not target_variant:
            return 0

        target_entry = next((e for e in target_variant.entries
                             if e.language == language and
                                e.condition == condition and
                                e.edition == eff_edition and
                                e.storage_location == storage_location), None)

        return target_entry.quantity if target_entry else 0

    @staticmethod
    def get_total_quantity(
        collection: Collection,
        card_id: int,
        variant_id: Optional[str] = None,
        set_code: Optional[str] = None,
        rarity: Optional[str] = None,
        image_id: Optional[int] = None,
        language: str = 'EN',
        condition: str = 'Near Mint',
        first_edition: bool = False,
        edition: Optional[str] = None,
    ) -> int:
        """
        Returns the total quantity of a card configuration across all storage locations.
        """
        eff_edition = _edition_from(first_edition, edition)
        target_card = next((c for c in collection.cards if c.card_id == card_id), None)
        if not target_card:
            return 0

        target_variant_id = variant_id
        if not target_variant_id and set_code and rarity:
             target_variant_id = generate_variant_id(card_id, set_code, rarity, image_id)

        if not target_variant_id:
            return 0

        target_variant = next((v for v in target_card.variants if v.variant_id == target_variant_id), None)
        if not target_variant:
            return 0

        total = 0
        for e in target_variant.entries:
            if (e.language == language and
                e.condition == condition and
                e.edition == eff_edition):
                total += e.quantity
        return total

    @staticmethod
    def apply_change(
        collection: Collection,
        api_card: ApiCard,
        set_code: str,
        rarity: str,
        language: str,
        quantity: int,
        condition: str,
        first_edition: bool,
        image_id: Optional[int] = None,
        variant_id: Optional[str] = None,
        mode: str = 'SET',
        storage_location: Optional[str] = None,
        edition: Optional[str] = None,
        purchase_price: Optional[float] = None,
        purchase_date: Optional[str] = None,
    ) -> bool:
        """
        Applies a change (add, set, remove) to a collection.
        Returns True if the collection was modified, False otherwise.
        """
        eff_edition = _edition_from(first_edition, edition)
        eff_first = (eff_edition == "1st Edition")
        modified = False

        # 1. Find or Create CollectionCard
        target_card = None
        for c in collection.cards:
            if c.card_id == api_card.id:
                target_card = c
                break

        if not target_card:
            # If removing/setting 0 and it doesn't exist, do nothing
            if quantity <= 0 and mode == 'SET':
                return False
            # Only create if we are adding positive amount
            if (mode == 'ADD' and quantity <= 0) or (mode == 'SET' and quantity <= 0):
                return False

            target_card = CollectionCard(card_id=api_card.id, name=api_card.name)
            collection.cards.append(target_card)
            modified = True

        # 2. Determine Variant ID
        target_variant_id = variant_id
        if not target_variant_id:
             target_variant_id = generate_variant_id(api_card.id, set_code, rarity, image_id)

        # 3. Find or Create CollectionVariant
        target_variant = None
        for v in target_card.variants:
            if v.variant_id == target_variant_id:
                target_variant = v
                break

        if not target_variant:
             # Need to add if quantity > 0
             should_add = False
             if mode == 'SET' and quantity > 0: should_add = True
             elif mode == 'ADD' and quantity > 0: should_add = True

             if should_add:
                 target_variant = CollectionVariant(
                     variant_id=target_variant_id,
                     set_code=set_code,
                     rarity=rarity,
                     image_id=image_id
                 )
                 target_card.variants.append(target_variant)
                 modified = True

        if target_variant:
            # 4. Find or Create CollectionEntry
            target_entry = None
            for e in target_variant.entries:
                if (e.condition == condition and
                    e.language == language and
                    e.edition == eff_edition and
                    e.storage_location == storage_location):
                    target_entry = e
                    break

            # 5. Determine the target total quantity for this stack.
            current_quantity = target_entry.quantity if target_entry else 0
            if mode == 'SET':
                final_quantity = quantity
            elif mode == 'ADD':
                final_quantity = current_quantity + quantity
            else:
                final_quantity = quantity

            delta = final_quantity - current_quantity

            # 6. Apply the change at the LOT level.
            if final_quantity > 0:
                if not target_entry:
                    # New stack: a single lot carrying the acquisition cost.
                    target_entry = CollectionEntry(
                        condition=condition,
                        language=language,
                        edition=eff_edition,
                        first_edition=eff_first,
                        storage_location=storage_location,
                        purchases=[PurchaseLot(
                            quantity=final_quantity,
                            purchase_price=purchase_price if purchase_price is not None else 0.0,
                            purchase_date=_lot_date(purchase_date),
                        )],
                    )
                    target_entry.sync_quantity()
                    target_variant.entries.append(target_entry)
                    modified = True
                elif delta > 0:
                    # Adding copies: a NEW lot captures this acquisition's cost
                    # (so a later purchase keeps its own price/date).
                    target_entry.purchases.append(PurchaseLot(
                        quantity=delta,
                        purchase_price=purchase_price if purchase_price is not None else 0.0,
                        purchase_date=_lot_date(purchase_date),
                    ))
                    target_entry.sync_quantity()
                    modified = True
                elif delta < 0:
                    # Removing copies: drain oldest lots first (FIFO).
                    CollectionEditor._drain_lots(target_entry, -delta)
                    target_entry.sync_quantity()
                    modified = True
                # delta == 0: nothing to do.
            else:
                # Target quantity is zero: remove the whole stack.
                if target_entry:
                    target_variant.entries.remove(target_entry)
                    modified = True

            # 7. Cleanup Empty Variant
            if not target_variant.entries:
                target_card.variants.remove(target_variant)
                modified = True

        # 8. Cleanup Empty Card
        if not target_card.variants:
            if target_card in collection.cards:
                collection.cards.remove(target_card)
                modified = True

        return modified

    @staticmethod
    def move_card(
        collection: Collection,
        api_card: ApiCard,
        set_code: str,
        rarity: str,
        language: str,
        condition: str,
        first_edition: bool,
        from_storage: Optional[str],
        to_storage: Optional[str],
        quantity: int = 1,
        image_id: Optional[int] = None,
        variant_id: Optional[str] = None,
        edition: Optional[str] = None,
    ) -> bool:
        """
        Moves a specific quantity of a card from one storage location to another.
        """
        if from_storage == to_storage:
            return False

        eff_edition = _edition_from(first_edition, edition)

        # Verify availability
        available = CollectionEditor.get_quantity(
            collection, api_card.id, variant_id, set_code, rarity, image_id,
            language, condition, first_edition, from_storage, edition=eff_edition
        )

        if available < quantity:
            return False

        # Remove from Source
        removed = CollectionEditor.apply_change(
            collection, api_card, set_code, rarity, language, -quantity,
            condition, first_edition, image_id, variant_id, mode='ADD',
            storage_location=from_storage, edition=eff_edition
        )

        # Add to Target
        added = CollectionEditor.apply_change(
            collection, api_card, set_code, rarity, language, quantity,
            condition, first_edition, image_id, variant_id, mode='ADD',
            storage_location=to_storage, edition=eff_edition
        )

        return removed or added

    @staticmethod
    def rename_storage_location(collection: Collection, old_name: str, new_name: str) -> bool:
        """
        Updates all references of a storage location in the collection to a new name.
        Returns True if any changes were made.
        """
        if old_name == new_name:
            return False

        modified = False
        for card in collection.cards:
            for variant in card.variants:
                for entry in variant.entries:
                    if entry.storage_location == old_name:
                        entry.storage_location = new_name
                        modified = True

        return modified

    @staticmethod
    def set_lot_purchase_info(
        collection: Collection,
        card_id: int,
        variant_id: str,
        language: str,
        condition: str,
        storage_location: Optional[str],
        lot_index: int,
        edition: Optional[str] = None,
        first_edition: bool = False,
        purchase_price: Optional[float] = None,
        purchase_date: Optional[str] = None,
    ) -> bool:
        """Update the price/date of ONE purchase lot within a stack.

        The stack is identified by (variant_id, language, condition, edition,
        storage_location); the lot by `lot_index`. Quantity and all other
        fields are untouched. Returns True if the lot was found and modified.
        """
        eff_edition = _edition_from(first_edition, edition)

        target_card = next((c for c in collection.cards if c.card_id == card_id), None)
        if not target_card:
            return False
        target_variant = next((v for v in target_card.variants if v.variant_id == variant_id), None)
        if not target_variant:
            return False
        target_entry = next(
            (e for e in target_variant.entries
             if e.language == language
             and e.condition == condition
             and e.edition == eff_edition
             and e.storage_location == storage_location),
            None,
        )
        if not target_entry:
            return False
        if lot_index < 0 or lot_index >= len(target_entry.purchases):
            return False

        lot = target_entry.purchases[lot_index]
        modified = False
        if purchase_price is not None and lot.purchase_price != purchase_price:
            lot.purchase_price = purchase_price
            modified = True
        if purchase_date is not None and lot.purchase_date != purchase_date:
            lot.purchase_date = purchase_date
            modified = True
        if modified:
            # Refresh the compat mirrors (primary lot) on the entry.
            target_entry.sync_quantity()
        return modified
