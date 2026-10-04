# Collection Manager

The Collection tab is the heart of your inventory management. It allows you to view, filter, sort, and edit every card you own.

![Collection View](images/collection_view.png)

## 1. Views
You can toggle between two main viewing modes using the buttons in the header:

### Consolidated View
- **Purpose**: Best for gameplay and deck building.
- **Display**: Groups all printings of a card together (e.g., "Total Owned: 5" for Blue-Eyes White Dragon).
- **Action**: Clicking a card opens the **Single Card View** to manage specific printings.

### Collectors View
- **Purpose**: Best for valuation and trading.
- **Display**: Lists every specific printing separately (e.g., "LOB-001 (Ultra) - 1x", "SDK-001 (Starter) - 1x").

## 2. Filters
Click the **Filter Button** (icon with sliders) on the right to open the Advanced Filter Pane.

![Filter Pane](images/filter_pane.png)

- **Search**: Text search for name, description, or set code.
- **Attributes**: Filter by Card Type, Attribute, Level, Race, Archetype.
- **Stats**: Sliders for ATK, DEF, Price, and Owned Quantity.
- **Condition**: Filter by specific card conditions (Near Mint, Played, etc.).

## 3. Adding & Editing Cards
Clicking on any card opens the **Single Card View**.

![Single Card View](images/single_card_view.png)

This dialog allows precise management of a card's inventory.
- **Add/Remove**: Adjust quantity for specific sets (the **Manage Inventory** / **Add to Inventory** section). Each ADD creates a new purchase lot and captures the **Price** and **Date** entered in the editor (date defaults to today); you can edit these later in **Purchase info**.
- **Variant Selection**: Choose Set Code, Rarity, Condition, Language, and Edition.
- **Edition**: Each copy records its print edition — **1st Edition**, **Unlimited Edition**, or **Limited Edition**. Copies that differ only by edition are tracked as separate stacks. In the card badges, 1st Edition shows as `1st`, Limited as `LTD`, and Unlimited is left blank.
- **Storage**: Assign the card to a specific Box or Binder directly from this view.
- **Purchase info**: Opens a sub-dialog listing **one row per purchase** across every owned stack of the card, each with its own editable **purchase price** and **purchase date**. Because each acquisition is a separate lot, buying another copy later keeps its own cost instead of overwriting the earlier one. Editing price/date never changes quantity. (The scanner records its own separate `scan_timestamp`, so scanning never overwrites a real purchase date.)
- **Save**: Commits changes to your collection.

## 4. Owned printing artwork (optional)

Enable **Match owned printing layout** in **Settings → Application** to display owned cards using the actual image of the printing you own (resolved from Yugipedia by set code), which reflects that era's card layout/frame rather than the generic illustration.

- Run **Settings → Data management → Download owned printing images** first to cache them; this needs a network connection.
- Cards without a cached printing image fall back to the default artwork.
- Reload the Collection page after toggling the setting.
