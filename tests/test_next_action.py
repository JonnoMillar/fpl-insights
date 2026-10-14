import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import urllib.error

import fplapi
from next_action import choose


def swap(gain=10):
    return {"gain": gain, "out": SimpleNamespace(name="Out"), "in": {"web_name": "In"}}


class ActionTests(unittest.TestCase):
    def test_single_and_pair_include_the_actual_hit(self):
        single = swap(10)
        pair = {"gain": 15, "legs": [swap(), swap()]}
        self.assertEqual(choose([single], [pair], 1, True, 7)["target"], "transfer-0")
        self.assertEqual(choose([single], [pair], 2, True, 7)["target"], "pair-0")

    def test_roll_margin_and_cap(self):
        self.assertEqual(choose([swap(2)], [], 1, True, 7)["label"], "Roll 1 free transfer")
        self.assertIn("five-transfer cap", choose([], [], 5, True, 7)["detail"])
        self.assertEqual(choose([], [], 0, True, 7)["label"], "Hold your squad")

    def test_unverified_inputs_and_ended_season_withhold_moves(self):
        for supported, free in [(False, 2), (True, None)]:
            self.assertIn("unavailable", choose([swap(30)], [], free, supported, 7)["detail"])
        self.assertIsNone(choose([], [], 1, True, 39)["target"])

    def test_chip_must_be_unused_known_and_strong_this_week(self):
        chip = ("3xc", "Triple Captain", {"gw": 7, "ep": 10, "confidence": "strong"})
        self.assertEqual(choose([], [], 1, True, 7, [chip], {})["target"], "chip-3xc")
        for used in [None, {"3xc": 4}]:
            self.assertEqual(choose([], [], 1, True, 7, [chip], used)["target"], "action-method")
        self.assertEqual(choose([], [], 1, True, 8, [chip], {})["target"], "action-method")

    def test_tagged_kneejerk_pair_does_not_replace_window_comparison(self):
        pair = {"gain": 100, "legs": [swap(), swap()], "tag": "Kneejerk"}
        self.assertEqual(choose([swap()], [pair], 2, True, 7)["target"], "transfer-0")


class PortraitTests(unittest.TestCase):
    def test_official_code_and_club_version_key(self):
        with patch.object(fplapi, "_asset", return_value=None) as asset:
            fplapi.photo_data_uri({"code": 123, "photo": "wrong.jpg", "team_code": 7})
        self.assertEqual(asset.call_args_list[0].args,
                         (fplapi.PHOTO_URL.format(pid="123"), "portrait25_123_7.png"))
        self.assertIn("placeholder", asset.call_args_list[1].args[0])

    def test_temporary_code_uses_placeholder(self):
        with patch.object(fplapi, "_asset", return_value=None) as asset:
            fplapi.photo_data_uri({"code": 123, "has_temporary_code": True})
        self.assertEqual(asset.call_count, 1)
        self.assertIn("placeholder", asset.call_args.args[0])

    def test_refreshes_expired_images_and_caches_missing_answers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, patch.object(fplapi, "ASSET_DIR", Path(directory)):
            path = Path(directory) / "photo.png"
            path.write_bytes(b"old")
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b"new"
            with patch.object(fplapi.urllib.request, "urlopen", return_value=response) as request:
                self.assertEqual(fplapi._asset("https://example.com/p.png", "photo.png", ttl=-1), b"new")
                self.assertEqual(fplapi._asset("https://example.com/p.png", "photo.png", ttl=86400), b"new")
                self.assertEqual(request.call_count, 1)
            error = urllib.error.HTTPError("url", 404, "missing", {}, None)
            with patch.object(fplapi.urllib.request, "urlopen", side_effect=error) as request:
                for _ in range(2):
                    self.assertIsNone(fplapi._asset("https://example.com/m.png", "missing.png", ttl=86400))
                self.assertEqual(request.call_count, 1)
                # An authoritative missing answer must not resurrect an old
                # cached portrait on the next call's failure cooldown.
                for _ in range(2):
                    self.assertIsNone(fplapi._asset("https://example.com/p.png", "photo.png", ttl=-1))
                self.assertEqual(request.call_count, 2)
            error.close()
