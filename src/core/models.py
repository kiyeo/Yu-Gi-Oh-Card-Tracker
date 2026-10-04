from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator
import uuid

# --- Collection Models ---

class PurchaseLot(BaseModel):
    """A single acquisition within a stack: N copies bought at one price/date.

    A stack (CollectionEntry) can hold multiple lots, so buying more copies of
    the same printing later records a separate historical cost rather than
    overwriting the earlier purchase.
    """
    quantity: int = 1
    purchase_price: Optional[float] = 0.0
    purchase_date: Optional[str] = None


class CollectionEntry(BaseModel):
    condition: Literal["Mint", "Near Mint", "Excellent", "Good", "Light Played", "Played", "Poor", "Damaged"] = "Near Mint"
    language: str = "EN"
    # Explicit print edition. Source of truth going forward. `first_edition`
    # is kept as a derived/compatibility mirror (edition == "1st Edition").
    edition: Literal["1st Edition", "Unlimited Edition", "Limited Edition"] = "Unlimited Edition"
    first_edition: bool = False
    quantity: int = 1
    storage_location: Optional[str] = Field(None, description="e.g., Box A, Row 2")
    # Per-acquisition historical cost. `purchase_price`/`purchase_date` below are
    # kept as compatibility mirrors of the first lot; `purchases` is the source
    # of truth. `quantity` is kept equal to the sum of lot quantities.
    purchases: List[PurchaseLot] = []
    purchase_price: Optional[float] = 0.0
    market_value: Optional[float] = 0.0
    purchase_date: Optional[str] = None
    # Separate from purchase_date: set by the scanner as an acquisition/scan
    # timestamp so a real purchase_date is never overwritten.
    scan_timestamp: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _reconcile_edition(cls, data):
        """Keep `edition` and `first_edition` consistent, migrating old data.

        - Old files have only `first_edition`: derive edition from it
          (True -> "1st Edition", False -> "Unlimited Edition").
        - New callers may set `edition`: derive first_edition from it.
        - If both are present and disagree, `edition` wins when it is explicitly
          a non-default value; otherwise `first_edition` is honored.
        """
        if not isinstance(data, dict):
            return data

        edition = data.get("edition")
        first = data.get("first_edition")

        if edition is None and first is not None:
            data["edition"] = "1st Edition" if first else "Unlimited Edition"
        elif edition is not None and first is None:
            data["first_edition"] = (edition == "1st Edition")
        elif edition is not None and first is not None:
            # Both provided. Trust `edition` as the richer field, but if edition
            # is the default while first_edition says 1st, honor first_edition.
            if edition == "Unlimited Edition" and first:
                data["edition"] = "1st Edition"
            else:
                data["first_edition"] = (edition == "1st Edition")
        # If neither provided, defaults apply (Unlimited / False), already
        # consistent.
        return data

    @model_validator(mode="after")
    def _reconcile_purchases(self):
        """Migrate legacy data to lots and keep quantity/mirrors consistent.

        - If no lots exist, synthesize one from the legacy quantity +
          purchase_price + purchase_date (so old files Just Work).
        - Keep `quantity` equal to the sum of lot quantities.
        - Mirror the first lot's price/date into the legacy scalar fields for
          any reader not yet migrated to `purchases`.
        """
        if not self.purchases:
            self.purchases = [PurchaseLot(
                quantity=max(0, self.quantity),
                purchase_price=self.purchase_price,
                purchase_date=self.purchase_date,
            )]
        # Keep the stack quantity in sync with its lots.
        self.quantity = sum(max(0, lot.quantity) for lot in self.purchases)
        # Compatibility mirrors of the primary (first) lot.
        primary = self.purchases[0]
        self.purchase_price = primary.purchase_price
        self.purchase_date = primary.purchase_date
        return self

    def sync_quantity(self) -> None:
        """Recompute `quantity` from lots and refresh the compat mirrors.

        Callers that mutate `purchases` directly should call this afterwards.
        """
        self.purchases = [lot for lot in self.purchases if lot.quantity > 0]
        self.quantity = sum(lot.quantity for lot in self.purchases)
        if self.purchases:
            self.purchase_price = self.purchases[0].purchase_price
            self.purchase_date = self.purchases[0].purchase_date


class StorageDefinition(BaseModel):
    name: str
    type: str = "Box" # Box, Binder, Sealed Product
    description: Optional[str] = ""
    image_path: Optional[str] = None
    set_code: Optional[str] = None

class CollectionVariant(BaseModel):
    variant_id: str
    set_code: str
    rarity: str
    image_id: Optional[int] = None
    entries: List[CollectionEntry] = []

    @property
    def total_quantity(self) -> int:
        return sum(e.quantity for e in self.entries)

class CollectionCard(BaseModel):
    card_id: int
    name: str
    variants: List[CollectionVariant] = []

    @property
    def total_quantity(self) -> int:
        return sum(v.total_quantity for v in self.variants)

class Collection(BaseModel):
    name: str
    description: Optional[str] = ""
    cards: List[CollectionCard] = []
    storage_definitions: List[StorageDefinition] = []

    @property
    def total_cards(self) -> int:
        return sum(c.total_quantity for c in self.cards)

class Deck(BaseModel):
    name: str = "New Deck"
    main: List[int] = []
    extra: List[int] = []
    side: List[int] = []

# --- Legacy Models (Deprecated) ---
# Keeping these temporarily to prevent immediate ImportErrors in other files during refactoring
class CardMetadata(BaseModel):
    set_code: str
    rarity: str
    image_id: Optional[int] = None
    language: str = "EN"
    condition: str = "Near Mint"
    first_edition: bool = False
    market_value: float = 0.0

class Card(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    quantity: int = 1
    image_url: Optional[str] = None
    metadata: CardMetadata

# --- API/Database Models ---

class ApiCardImage(BaseModel):
    id: int
    image_url: str
    image_url_small: str
    image_url_cropped: Optional[str] = None

class ApiCardSet(BaseModel):
    variant_id: Optional[str] = None
    set_name: str
    set_code: str
    set_rarity: str
    set_rarity_code: Optional[str] = None
    set_price: Optional[str] = None
    image_id: Optional[int] = Field(None, alias='card_image_id')
    cardmarket_url: Optional[str] = None

    model_config = {
        "populate_by_name": True
    }

class ApiCardPrice(BaseModel):
    cardmarket_price: Optional[str] = None
    tcgplayer_price: Optional[str] = None
    ebay_price: Optional[str] = None
    amazon_price: Optional[str] = None
    coolstuffinc_price: Optional[str] = None

class ApiCard(BaseModel):
    id: int
    name: str
    type: str
    frameType: str
    desc: str
    typeline: Optional[List[str]] = None
    race: Optional[str] = None
    atk: Optional[int] = None
    def_: Optional[int] = Field(None, alias="def")
    level: Optional[int] = None
    scale: Optional[int] = None
    linkval: Optional[int] = None
    linkmarkers: Optional[List[str]] = None
    attribute: Optional[str] = None
    archetype: Optional[str] = None
    card_images: List[ApiCardImage] = []
    card_sets: List[ApiCardSet] = []
    card_prices: List[ApiCardPrice] = []

    @property
    def is_extra_deck(self) -> bool:
        """
        Determines if the card belongs in the Extra Deck.
        Checks for Fusion, Synchro, XYZ, or Link in the card type.
        """
        extra_types = ["Fusion", "Synchro", "XYZ", "Link"]
        return any(t in self.type for t in extra_types)

    def get_best_image_id(self) -> int:
        """
        Returns the best available image ID for the card.
        Prioritizes official images, then custom variant images, then falls back to card ID.
        """
        if self.card_images:
            return self.card_images[0].id

        # Check variants for custom images (e.g. imported cards)
        if self.card_sets:
            for s in self.card_sets:
                if s.image_id:
                    return s.image_id

        return self.id

    def matches_category(self, category: str) -> bool:
        """
        Checks if the card belongs to the specified monster category (e.g., 'Normal', 'Effect', 'Synchro').
        Handles special logic for 'Normal' vs 'Effect' distinction for Extra Deck monsters.
        """
        # Use typeline if available
        if self.typeline is not None:
            if category == "Effect":
                return "Effect" in self.typeline
            elif category == "Normal":
                if "Normal" in self.typeline:
                    return True
                # Check for Non-Effect Extra Deck / Ritual
                # Synchro/Fusion/XYZ/Link/Ritual without "Effect" in typeline are "Normal" (Non-Effect).
                is_extra_or_ritual = any(t in self.type for t in ["Synchro", "Fusion", "XYZ", "Link", "Ritual"])
                if is_extra_or_ritual and "Effect" not in self.typeline:
                    return True
                return False
            else:
                return category in self.type or category in self.typeline

        # Fallback Legacy Logic
        card_type = self.type
        if category == "Effect":
            # Special logic for Effect:
            # 1. Explicitly in type string
            if "Effect" in card_type: return True
            # 2. Implied by Extra Deck / Ritual / Pendulum types (unless Normal is present)
            implied_types = ["Synchro", "Fusion", "XYZ", "Link", "Ritual", "Pendulum"]
            if any(t in card_type for t in implied_types) and "Normal" not in card_type:
                return True
            return False
        else:
            return category in card_type
