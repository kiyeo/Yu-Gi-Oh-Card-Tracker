
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from src.services.yugipedia_service import YugipediaService, DeckCard, StructureDeck

class TestYugipediaService(unittest.TestCase):
    def setUp(self):
        self.service = YugipediaService()

    def test_parse_wikitext_simple(self):
        text = """{{Set page header}}
{{Set list|region=EN|rarities=C|print=Reprint|
SDAZ-EN001; Tri-Brigade Mercourier; UR; New
SDAZ-EN002; Springans Kitt; UR; New
SDAZ-EN004; Fallen of Albaz
}}"""
        result = self.service._parse_wikitext(text)
        self.assertIn('main', result)
        self.assertEqual(len(result['main']), 3)
        self.assertEqual(result['main'][0].code, "SDAZ-EN001")
        self.assertEqual(result['main'][0].rarity, "Ultra Rare") # Mapped
        self.assertEqual(result['main'][2].rarity, "Common") # Default

    def test_parse_wikitext_with_bonus(self):
        text = """{{Set page header}}

== Bonus cards ==
{{Set list|region=EN|rarities=Secret Rare, Quarter Century Secret Rare|print=New|
SDWD-EN041; Maiden of White
}}

== Preconstructed Deck ==
{{Set list|region=EN|rarities=Common|print=Reprint|qty=1|
SDWD-EN001; Blue-Eyes White Dragon
}}"""
        result = self.service._parse_wikitext(text)
        self.assertIn('main', result)
        self.assertIn('bonus', result)
        self.assertEqual(len(result['main']), 1)
        self.assertEqual(len(result['bonus']), 2)

        self.assertEqual(result['bonus'][0].code, "SDWD-EN041")
        # Now keeps both rarities instead of just picking the first
        # Sorted by name (Maiden of White) which is the same, so order is preserved
        self.assertEqual(result['bonus'][0].rarity, "Secret Rare")
        self.assertEqual(result['bonus'][1].rarity, "Quarter Century Secret Rare")
        self.assertEqual(result['main'][0].code, "SDWD-EN001")

    def test_parse_wikitext_leading_whitespace_header(self):
        # Header has leading space
        text = """{{Set page header}}

 == Bonus cards ==
{{Set list|
SDWD-EN041; Maiden of White
}}
"""
        result = self.service._parse_wikitext(text)
        self.assertIn('bonus', result)
        self.assertEqual(len(result['bonus']), 1)
        self.assertEqual(result['bonus'][0].code, "SDWD-EN041")

    def test_parse_wikitext_defaults(self):
         text = """{{Set list|rarities=Super Rare|
TEST-EN001; Card 1
TEST-EN002; Card 2; Common
}}"""
         result = self.service._parse_wikitext(text)
         self.assertEqual(result['main'][0].rarity, "Super Rare")
         self.assertEqual(result['main'][1].rarity, "Common")

    def test_parse_wikitext_qty(self):
         text = """{{Set list|qty=2|
TEST-EN001; Card 1
TEST-EN002; Card 2;;; 3
}}"""
         result = self.service._parse_wikitext(text)
         self.assertEqual(result['main'][0].quantity, 2)
         self.assertEqual(result['main'][1].quantity, 3)

    def test_parse_card_table(self):
        text = """{{CardTable2
| name = Stardust Dragon
| types = Dragon / Synchro / Effect
| atk = 2500
| def = 2000
| level = 8
| attribute = WIND
| database_id = 12345
| en_sets =
CODE-EN001; Test Set; Ultra Rare
CODE-EN002; Test Set 2; Common, Rare
}}"""
        result = self.service._parse_card_table(text, "Stardust_Dragon")
        self.assertEqual(result['name'], "Stardust Dragon")
        self.assertEqual(result['type'], "Synchro Monster")
        self.assertEqual(result['atk'], 2500)
        self.assertEqual(result['database_id'], 12345)
        self.assertEqual(len(result['sets']), 3) # Ultra, Common, Rare
        self.assertEqual(result['sets'][0]['set_code'], "CODE-EN001")
        self.assertEqual(result['sets'][1]['set_code'], "CODE-EN002")
        self.assertEqual(result['sets'][1]['set_rarity'], "Common")
        self.assertEqual(result['sets'][2]['set_rarity'], "Rare")

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_all_decks_deduplication(self, mock_get):
        # Setup mock responses
        # We expect 3 calls for the 3 categories

        # Helper to create mock response
        def create_mock_response(members):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "query": {
                    "categorymembers": members
                }
            }
            return mock_resp

        # Category 1: Structure Decks
        # Contains Deck A and Deck B
        cat1_members = [
            {'pageid': 101, 'title': 'Structure Deck: A', 'ns': 0},
            {'pageid': 102, 'title': 'Structure Deck: B', 'ns': 0}
        ]

        # Category 2: Starter Decks
        # Contains Deck C
        cat2_members = [
            {'pageid': 103, 'title': 'Starter Deck: C', 'ns': 0}
        ]

        # Category 3: Preconstructed Decks
        # Contains Deck B (duplicate) and Deck D (new)
        cat3_members = [
            {'pageid': 102, 'title': 'Structure Deck: B', 'ns': 0}, # Duplicate of 102
            {'pageid': 104, 'title': 'Speed Duel: D', 'ns': 0}
        ]

        # Configure side_effect for requests.get
        # The service calls them concurrently, but we can inspect the params to return correct data
        # However, asyncio.gather runs them.

        def side_effect(url, params=None, headers=None):
            if params['cmtitle'] == "Category:TCG_Structure_Decks":
                return create_mock_response(cat1_members)
            elif params['cmtitle'] == "Category:TCG_Starter_Decks":
                return create_mock_response(cat2_members)
            elif params['cmtitle'] == "Category:Preconstructed_Decks":
                return create_mock_response(cat3_members)
            return MagicMock(status_code=404)

        mock_get.side_effect = side_effect

        # Run the async method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.service.get_all_decks())
        loop.close()

        # Verification
        # Total unique decks should be 4: A, B, C, D
        self.assertEqual(len(results), 4)

        # Check titles and types
        # Sort order is by title.
        # "Speed Duel: D", "Starter Deck: C", "Structure Deck: A", "Structure Deck: B"
        # Alphabetical:
        # 1. Speed Duel: D
        # 2. Starter Deck: C
        # 3. Structure Deck: A
        # 4. Structure Deck: B

        titles = [d.title for d in results]
        self.assertEqual(titles, sorted(["Structure Deck: A", "Structure Deck: B", "Starter Deck: C", "Speed Duel: D"]))

        # Check types
        deck_map = {d.title: d for d in results}
        self.assertEqual(deck_map["Structure Deck: A"].deck_type, 'STRUCTURE')
        self.assertEqual(deck_map["Starter Deck: C"].deck_type, 'STARTER')
        self.assertEqual(deck_map["Speed Duel: D"].deck_type, 'PRECON')

        # Deck B could be STRUCTURE or PRECON depending on which one was processed first/kept.
        # Logic says: results = results[0] + results[1] + results[2]
        # results[0] is STRUCTURE. results[2] is PRECON.
        # Deduplication keeps first occurrence.
        # So Deck B should be STRUCTURE.
        self.assertEqual(deck_map["Structure Deck: B"].deck_type, 'STRUCTURE')

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_set_printing_image_url_prefers_first_edition(self, mock_get):
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:StardustDragon-TDGS-EN-UR-UE.png"},
                {"title": "File:StardustDragon-TDGS-EN-UR-1E.png"},
                {"title": "File:StardustDragon-TDGS-JP-C.jpg"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//StardustDragon-TDGS-EN-UR-1E.png"}
            ]}}}
        }
        # First call = search, second = imageinfo for the chosen file.
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url("Stardust Dragon", "TDGS-EN040", "EN")
        )
        loop.close()

        self.assertEqual(url, "https://ms.yugipedia.com//StardustDragon-TDGS-EN-UR-1E.png")
        # The second request must target the 1E file via imageinfo.
        second_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_params["prop"], "imageinfo")
        self.assertEqual(second_params["titles"], "File:StardustDragon-TDGS-EN-UR-1E.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_set_printing_image_url_region_fallback(self, mock_get):
        # Only NA-region files exist (old set); EN maps to NA fallback.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:Sogen-SDK-NA-C-1E.jpg"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//Sogen-SDK-NA-C-1E.jpg"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url("Sogen", "SDK-EN020", "EN")
        )
        loop.close()
        self.assertEqual(url, "https://ms.yugipedia.com//Sogen-SDK-NA-C-1E.jpg")

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_set_printing_image_url_no_match(self, mock_get):
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {"query": {"search": []}}
        mock_get.return_value = search_resp

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url("Nonexistent", "ZZZ-EN999", "EN")
        )
        loop.close()
        self.assertIsNone(url)

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_file_image_url_success(self, mock_get):
        # Mirrors the MediaWiki imageinfo response shape for a File: page.
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "12345": {
                        "ns": 6,
                        "title": "File:StardustDragon-CT05-EN-ScR-LE.png",
                        "imageinfo": [
                            {
                                "url": "https://ms.yugipedia.com//StardustDragon-CT05-EN-ScR-LE.png",
                                "descriptionurl": "https://yugipedia.com/wiki/File:StardustDragon-CT05-EN-ScR-LE.png",
                            }
                        ],
                    }
                }
            }
        }
        mock_get.return_value = mock_resp

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_file_image_url("StardustDragon-CT05-EN-ScR-LE.png")
        )
        loop.close()

        self.assertEqual(url, "https://ms.yugipedia.com//StardustDragon-CT05-EN-ScR-LE.png")

        # Verify the imageinfo API was queried with the File: title.
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        self.assertEqual(params["prop"], "imageinfo")
        self.assertEqual(params["iiprop"], "url")
        self.assertEqual(params["titles"], "File:StardustDragon-CT05-EN-ScR-LE.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_file_image_url_adds_file_prefix(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"query": {"pages": {"1": {"imageinfo": [{"url": "https://x/y.png"}]}}}}
        mock_get.return_value = mock_resp

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Pass a title that already has the File: prefix — it must not be doubled.
        loop.run_until_complete(self.service.get_file_image_url("File:Already-Prefixed.png"))
        loop.close()

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["titles"], "File:Already-Prefixed.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_file_image_url_missing(self, mock_get):
        # Missing files come back with pid "-1" and a "missing" marker.
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "-1": {
                        "ns": 6,
                        "title": "File:DoesNotExist.png",
                        "missing": "",
                    }
                }
            }
        }
        mock_get.return_value = mock_resp

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(self.service.get_file_image_url("DoesNotExist.png"))
        loop.close()

        self.assertIsNone(url)

    def test_get_file_image_url_empty_input(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(self.service.get_file_image_url(""))
        loop.close()
        self.assertIsNone(url)

    @patch('src.services.yugipedia_service.requests.get')
    def test_get_set_printing_image_url_prefers_matching_rarity(self, mock_get):
        # Same set/region has multiple rarities; must pick the owned rarity's file.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:CyberEsper-CDIP-EN-C-1E.jpg"},
                {"title": "File:CyberEsper-CDIP-EN-UtR-1E.jpg"},
                {"title": "File:CyberEsper-CDIP-EN-SR-1E.jpg"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//CyberEsper-CDIP-EN-UtR-1E.jpg"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url(
                "Cyber Esper", "CDIP-EN045", "EN", rarity="Ultimate Rare"
            )
        )
        loop.close()

        self.assertEqual(url, "https://ms.yugipedia.com//CyberEsper-CDIP-EN-UtR-1E.jpg")
        second_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_params["titles"], "File:CyberEsper-CDIP-EN-UtR-1E.jpg")

    def test_rarity_code_from_filename(self):
        s = self.service
        self.assertEqual(
            s._rarity_code_from_filename("File:CyberEsper-CDIP-EN-UtR-1E.jpg", "CDIP", "EN"),
            "UtR",
        )
        self.assertEqual(
            s._rarity_code_from_filename("File:Sogen-SDK-NA-C-1E.jpg", "SDK", "NA"),
            "C",
        )
        self.assertIsNone(
            s._rarity_code_from_filename("File:Other-ABC-EN-R.png", "CDIP", "EN")
        )

    @patch('src.services.yugipedia_service.requests.get')
    def test_excludes_giant_card_novelty_variant(self, mock_get):
        # A Giant Card (-GC) exists alongside the standard file; pick standard.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:Tsukuyomi-SD6-EN-C-UE-GC.jpg"},
                {"title": "File:Tsukuyomi-SD6-EN-C-1E.png"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//Tsukuyomi-SD6-EN-C-1E.png"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url("Tsukuyomi", "SD6-EN011", "EN", rarity="Common")
        )
        loop.close()
        self.assertEqual(url, "https://ms.yugipedia.com//Tsukuyomi-SD6-EN-C-1E.png")
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["titles"],
                         "File:Tsukuyomi-SD6-EN-C-1E.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_excludes_video_game_variant_uses_region_fallback(self, mock_get):
        # The -VG promo (no rarity) must be skipped; the real EU PScR picked.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:Salamandra-SDD-EN-VG.png"},
                {"title": "File:Salamandra-SDD-EU-PScR-UE.png"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//Salamandra-SDD-EU-PScR-UE.png"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url("Salamandra", "SDD-EN003", "EN",
                                                    rarity="Prismatic Secret Rare")
        )
        loop.close()
        self.assertEqual(url, "https://ms.yugipedia.com//Salamandra-SDD-EU-PScR-UE.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_return_meta_reports_resolved_edition(self, mock_get):
        # Request Unlimited but only a Limited file exists -> url returned,
        # resolved edition reported as Limited Edition.
        search_resp = MagicMock(); search_resp.status_code = 200
        search_resp.json.return_value = {"query": {"search": [
            {"title": "File:StardustDragon-CT05-EN-ScR-LE.png"},
        ]}}
        info_resp = MagicMock(); info_resp.status_code = 200
        info_resp.json.return_value = {"query": {"pages": {"1": {"imageinfo": [
            {"url": "https://x/LE.png"}]}}}}
        mock_get.side_effect = [search_resp, info_resp]

        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        url, resolved = loop.run_until_complete(
            self.service.get_set_printing_image_url(
                "Stardust Dragon", "CT05-EN002", "EN",
                rarity="Secret Rare", edition="Unlimited Edition", return_meta=True)
        )
        loop.close()
        self.assertEqual(url, "https://x/LE.png")
        self.assertEqual(resolved, "Limited Edition")

    def test_edition_code_from_filename(self):
        s = self.service
        self.assertEqual(s._edition_code_from_filename("File:CyberEsper-CDIP-EN-UtR-1E.jpg"), "1E")
        self.assertEqual(s._edition_code_from_filename("File:StardustDragon-CT05-EN-ScR-LE.png"), "LE")
        self.assertEqual(s._edition_code_from_filename("File:Foo-ABC-EN-C-UE.jpg"), "UE")
        self.assertIsNone(s._edition_code_from_filename("File:Foo-ABC-EN-C.jpg"))

    @patch('src.services.yugipedia_service.requests.get')
    def test_resolves_limited_edition_only_printing(self, mock_get):
        # Promo that only exists as Limited Edition must still resolve.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:StardustDragon-CT05-EN-ScR-LE.png"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//StardustDragon-CT05-EN-ScR-LE.png"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url(
                "Stardust Dragon", "CT05-EN002", "EN", rarity="Secret Rare"
            )
        )
        loop.close()
        self.assertEqual(url, "https://ms.yugipedia.com//StardustDragon-CT05-EN-ScR-LE.png")

    @patch('src.services.yugipedia_service.requests.get')
    def test_prefers_requested_edition(self, mock_get):
        # Both 1E and LE exist; requesting Limited Edition must pick LE.
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "query": {"search": [
                {"title": "File:Foo-ABCD-EN-UR-1E.png"},
                {"title": "File:Foo-ABCD-EN-UR-LE.png"},
            ]}
        }
        imageinfo_resp = MagicMock()
        imageinfo_resp.status_code = 200
        imageinfo_resp.json.return_value = {
            "query": {"pages": {"1": {"imageinfo": [
                {"url": "https://ms.yugipedia.com//Foo-ABCD-EN-UR-LE.png"}
            ]}}}
        }
        mock_get.side_effect = [search_resp, imageinfo_resp]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        url = loop.run_until_complete(
            self.service.get_set_printing_image_url(
                "Foo", "ABCD-EN001", "EN", rarity="Ultra Rare", edition="Limited Edition"
            )
        )
        loop.close()
        self.assertEqual(url, "https://ms.yugipedia.com//Foo-ABCD-EN-UR-LE.png")
        second_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_params["titles"], "File:Foo-ABCD-EN-UR-LE.png")

    def test_map_rarity_corrected_and_complete(self):
        s = self.service
        # Previously-incorrect mappings now fixed.
        self.assertEqual(s._map_rarity("UScR"), "Ultra Secret Rare")   # was "Ultimate Rare"
        self.assertEqual(s._map_rarity("GR"), "Ghost Rare")            # was "Gold Rare"
        self.assertEqual(s._map_rarity("GUR"), "Gold Rare")            # Gold Rare is GUR
        expected = {
            "C": "Common", "NR": "Normal Rare", "R": "Rare", "SR": "Super Rare",
            "UR": "Ultra Rare", "ScR": "Secret Rare", "ScUR": "Secret Ultra Rare",
            "PScR": "Prismatic Secret Rare", "EScR": "Extra Secret Rare",
            "PlScR": "Platinum Secret Rare", "20ScR": "20th Secret Rare",
            "10000ScR": "10000 Secret Rare", "QCScR": "Quarter Century Secret Rare",
            "UtR": "Ultimate Rare", "CR": "Collector's Rare", "StR": "Starlight Rare",
            "HGR": "Holographic Rare", "PR": "Parallel Rare", "NPR": "Normal Parallel Rare",
            "SPR": "Super Parallel Rare", "UPR": "Ultra Parallel Rare",
            "ScPR": "Secret Parallel Rare", "EScPR": "Extra Secret Parallel Rare",
            "HGPR": "Holographic Parallel Rare", "GScR": "Gold Secret Rare",
            "PGR": "Premium Gold Rare", "PlR": "Platinum Rare", "SFR": "Starfoil Rare",
            "MSR": "Mosaic Rare", "SHR": "Shatterfoil Rare",
        }
        for abbr, full in expected.items():
            self.assertEqual(s._map_rarity(abbr), full, f"{abbr} should map to {full}")

    def test_map_rarity_full_names_passthrough(self):
        s = self.service
        for full in ["Secret Rare", "Ultra Secret Rare", "Ghost Rare", "Platinum Rare"]:
            self.assertEqual(s._map_rarity(full), full)

    def test_map_rarity_unknown_passthrough(self):
        self.assertEqual(self.service._map_rarity("WeirdRarity"), "WeirdRarity")


if __name__ == '__main__':
    unittest.main()
