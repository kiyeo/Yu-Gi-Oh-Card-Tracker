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
        k1 = ImageManager.printing_key("TDGS-EN040", "en")
        k2 = ImageManager.printing_key("TDGS-EN040", "EN")
        self.assertEqual(k1, k2)  # language normalized to upper
        self.assertNotIn("/", k1)
        self.assertTrue(k1.startswith("TDGS-EN040_EN"))

    def test_exists_and_url_reflect_cache(self):
        set_code, lang = "LOB-EN001", "EN"
        self.assertFalse(self.mgr.printing_image_exists(set_code, lang))
        self.assertIsNone(self.mgr.get_printing_image_url(set_code, lang))

        # Simulate a cached file.
        path = self.mgr.get_printing_image_path(set_code, lang)
        with open(path, 'wb') as f:
            f.write(b"jpegdata")

        self.assertTrue(self.mgr.printing_image_exists(set_code, lang))
        self.assertEqual(
            self.mgr.get_printing_image_url(set_code, lang),
            f"/printings/{ImageManager.printing_key(set_code, lang)}.jpg",
        )


if __name__ == '__main__':
    unittest.main()
