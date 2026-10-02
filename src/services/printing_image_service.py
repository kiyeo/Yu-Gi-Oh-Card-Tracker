"""Batch download of era-accurate per-printing card images from Yugipedia.

Used by Settings → Data management. Iterates every owned printing across all
collections, resolves each distinct (set_code, language) to a Yugipedia File:
image, and caches it under data/printings (served at /printings). The image of
a specific printing inherently reflects that era's card layout/frame.
"""

import asyncio
import logging
from typing import Callable, Dict, Optional, Tuple

from src.core.persistence import persistence
from src.services.image_manager import image_manager
from src.services.yugipedia_service import YugipediaService

logger = logging.getLogger(__name__)

# Default language used when an entry doesn't specify one.
_DEFAULT_LANGUAGE = "EN"


def _collect_owned_printings() -> Dict[Tuple[str, str, str], str]:
    """Return {(set_code, language_upper, rarity): card_name} for all owned
    printings, deduplicated across every collection file. Only printings with a
    real set code are included (custom/unknown entries are skipped).
    """
    pending: Dict[Tuple[str, str, str], str] = {}

    for filename in persistence.list_collections():
        try:
            collection = persistence.load_collection(filename)
        except Exception as e:  # a single bad file shouldn't abort the batch
            logger.warning(f"Skipping unreadable collection {filename}: {e}")
            continue

        if not collection:
            continue

        for card in collection.cards:
            card_name = card.name
            for variant in card.variants:
                set_code = (variant.set_code or "").strip()
                if not set_code or set_code in ("N/A",):
                    continue
                rarity = (variant.rarity or "").strip()
                # Languages actually owned for this printing.
                languages = {
                    (e.language or _DEFAULT_LANGUAGE).strip().upper()
                    for e in variant.entries
                    if e.quantity > 0
                }
                if not languages:
                    continue
                for lang in languages:
                    key = (set_code, lang, rarity)
                    pending.setdefault(key, card_name)

    return pending


async def download_owned_printing_images(
    progress_callback: Optional[Callable[[float], None]] = None,
    concurrency: int = 5,
) -> Dict[str, int]:
    """Resolve + cache printing images for all owned printings.

    Returns a summary dict: {"total", "downloaded", "skipped", "failed"}.
    Already-cached printings are skipped. Resolution/download failures are
    counted but do not abort the batch.
    """
    pending = await asyncio.to_thread(_collect_owned_printings)

    # Skip ones already cached.
    todo = {
        (set_code, lang, rarity): name
        for (set_code, lang, rarity), name in pending.items()
        if not image_manager.printing_image_exists(set_code, lang, rarity)
    }

    total = len(todo)
    skipped = len(pending) - total
    summary = {"total": len(pending), "downloaded": 0, "skipped": skipped, "failed": 0}

    if total == 0:
        if progress_callback:
            progress_callback(1.0)
        return summary

    service = YugipediaService()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    completed = 0
    lock = asyncio.Lock()

    async def _one(set_code: str, lang: str, rarity: str, card_name: str):
        nonlocal completed
        async with semaphore:
            try:
                url = await service.get_set_printing_image_url(card_name, set_code, lang, rarity)
                if url and await image_manager.ensure_printing_image(set_code, lang, url, rarity):
                    async with lock:
                        summary["downloaded"] += 1
                else:
                    async with lock:
                        summary["failed"] += 1
            except Exception as e:
                logger.debug(f"Printing fetch failed {card_name}/{set_code}/{lang}/{rarity}: {e}")
                async with lock:
                    summary["failed"] += 1
            finally:
                async with lock:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / total)

    await asyncio.gather(*[
        _one(set_code, lang, rarity, name)
        for (set_code, lang, rarity), name in todo.items()
    ])

    return summary
