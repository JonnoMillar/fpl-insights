import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

import fplapi
from next_action import choose


def week(gw, moves=(), hits=0, chip=None, gain=8.0, ft=1):
    return {"gw": gw, "moves": [{"out_name": o, "in_name": n} for o, n in moves],
            "hits": hits, "chip": chip, "gain": gain if moves else None,
            "ft_before": ft}


def plan(*weeks):
    return {"weeks": list(weeks), "start_gw": weeks[0]["gw"],
            "end_gw": weeks[-1]["gw"], "show_weeks": 3}


class ActionTests(unittest.TestCase):
    def test_first_week_moves_are_the_action_with_their_hit(self):
        p = plan(week(8, [("A", "B"), ("C", "D")], hits=1, gain=12.1), week(9))
        action = choose(p, 1, True, 8)
        self.assertEqual(action["label"], "Make 2 transfers (−4)")
        self.assertEqual(action["target"], "plan-gw-8")
        self.assertIn("A → B; C → D", action["detail"])
        self.assertIn("after the hit", action["detail"])

    def test_roll_names_the_next_planned_move_within_view(self):
        p = plan(week(8), week(9), week(10, [("Hall", "Vuskovic")]))
        action = choose(p, 1, True, 8)
        self.assertEqual(action["label"], "Roll 1 free transfer")
        self.assertIn("GW10, Hall → Vuskovic", action["detail"])
        self.assertEqual(action["target"], "plan-gw-10")

    def test_roll_without_moves_and_the_cap(self):
        p = plan(week(8), week(9), week(10), week(11, [("X", "Y")]))
        self.assertIn("No move clears", choose(p, 1, True, 8)["detail"])
        capped = choose(p, 5, True, 8)
        self.assertEqual(capped["label"], "No transfer this week")
        self.assertIn("five-transfer cap", capped["detail"])

    def test_unverified_inputs_and_ended_season_withhold_moves(self):
        p = plan(week(8, [("A", "B")]))
        for supported, free, pl in [(False, 2, p), (True, None, p), (True, 1, None)]:
            self.assertIn("unavailable", choose(pl, free, supported, 8)["detail"])
        self.assertIsNone(choose(p, 1, True, 39)["target"])

    def test_planned_chip_leads_the_action(self):
        p = plan(week(8, chip="bboost"), week(9))
        self.assertEqual(choose(p, 1, True, 8)["label"], "Play Bench Boost")
        p = plan(week(8, [("A", "B")], chip="bboost"), week(9))
        self.assertEqual(choose(p, 1, True, 8)["label"], "Play Bench Boost, make 1 transfer")

    def test_free_hit_must_be_unused_known_and_strong_this_week(self):
        fh = ("freehit", "Free Hit", {"gw": 8, "gap": 10, "confidence": "strong"})
        p = plan(week(8), week(9))
        self.assertEqual(choose(p, 1, True, 8, [fh], {})["target"], "chip-freehit")
        for used in [None, {"freehit": 4}]:
            self.assertNotEqual(choose(p, 1, True, 8, [fh], used)["target"], "chip-freehit")
        self.assertNotEqual(choose(p, 1, True, 9, [fh], {})["target"], "chip-freehit")


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
