import os
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.services.image_manager import ImageManager


class TestPrintingImageHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mgr = ImageManager(images_dir=os.path.join(self.tmp, 'images'))
        # Redirect printing cache into the temp dir.
        self.mgr.printings_dir = os.path.join(self.tmp, 'printings')
        os.makedirs(self.mgr.printings_dir, exist_ok=True)

    def test_printing_key_is_sanitized_and_stable(self):
        k1 = ImageManager.printing_key("TDGS-EN040", "en", "Ultra Rare")
        k2 = ImageManager.printing_key("TDGS-EN040", "EN", "Ultra Rare")
        self.assertEqual(k1, k2)  # language normalized to upper
        self.assertNotIn("/", k1)
        self.assertTrue(k1.startswith("TDGS-EN040_EN"))

    def test_rarity_distinguishes_keys(self):
        k_ur = ImageManager.printing_key("CDIP-EN045", "EN", "Ultimate Rare")
        k_c = ImageManager.printing_key("CDIP-EN045", "EN", "Common")
        self.assertNotEqual(k_ur, k_c)

    def test_exists_and_url_reflect_cache(self):
        set_code, lang, rarity = "LOB-EN001", "EN", "Ultra Rare"
        self.assertFalse(self.mgr.printing_image_exists(set_code, lang, rarity))
        self.assertIsNone(self.mgr.get_printing_image_url(set_code, lang, rarity))

        # Simulate a cached file.
        path = self.mgr.get_printing_image_path(set_code, lang, rarity)
        with open(path, 'wb') as f:
            f.write(b"jpegdata")

        self.assertTrue(self.mgr.printing_image_exists(set_code, lang, rarity))
        self.assertEqual(
            self.mgr.get_printing_image_url(set_code, lang, rarity),
            f"/printings/{ImageManager.printing_key(set_code, lang, rarity)}.jpg",
        )


if __name__ == '__main__':
    unittest.main()
