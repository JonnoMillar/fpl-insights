"""The player profile: every face opens it, and every hook has a record."""

import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

import analysis
import cards_league
import components
import playerprofile
import season
from cards_season import season_section
from tests.test_season import POINTS, hist, move

ROOT = Path(__file__).resolve().parent.parent
PHOTO = "data:image/webp;base64,AAAA"


def profiles(*ids, always=()):
    return {"players": {i: {"n": f"P{i}"} for i in ids}, "always": list(always),
            "teams": {}, "tiles": {}, "strip": {}, "fixtures": {}, "opta": {}}


class IslandTests(unittest.TestCase):
    def test_keeps_only_the_players_the_page_shows(self):
        html = f'<img class="cut" src="{PHOTO}" data-player="7" role="button">'
        out = playerprofile.island(html, profiles(7, 8, 9, always=[9]))
        data = json.loads(re.search(r">(.*)</script>", out).group(1))
        self.assertEqual(sorted(data["players"]), ["7", "9"])

    def test_a_face_that_opens_nothing_stops_the_build(self):
        with self.assertRaises(ValueError):
            playerprofile.island(f'<div><img class="face" src="{PHOTO}" alt=""></div>', profiles(7))

    def test_a_hook_without_a_record_stops_the_build(self):
        with self.assertRaises(ValueError):
            playerprofile.island('<button data-player="5">Five</button>', profiles(7))

    def test_hook_on_a_wrapper_counts_and_nav_faces_are_exempt(self):
        html = (f'<div data-player="7"><span><img class="cut" src="{PHOTO}"></span></div>'
                f'<button class="wk"><span class="faces"><img class="face" src="{PHOTO}"></span></button>'
                f'<button class="deck-idx"><img class="face" src="{PHOTO}"></button>'
                f'<img class="crestimg" src="{PHOTO}">')
        self.assertEqual(playerprofile.unhooked(html), [])

    def test_record_is_script_safe(self):
        out = playerprofile.island('<b data-player="1"></b>',
                                   {**profiles(1), "players": {1: {"n": "</script><x>"}}})
        self.assertEqual(out.count("</script>"), 1)


class RenderedFaceTests(unittest.TestCase):
    """Real renderers, fed small fixtures: every portrait they draw opens a profile."""

    def assertAllHooked(self, html, ids):
        self.assertIn("<img", html)
        self.assertEqual(playerprofile.unhooked(html), [])
        self.assertTrue(set(map(int, playerprofile.HOOK.findall(html))) <= set(ids))

    def test_season_review(self):
        ledger = season.transfer_ledger([move(3, 1, 2, "a"), move(5, 4, 3, "b")],
                                        [hist(gw) for gw in POINTS], POINTS)
        players = {pid: {"id": pid, "name": f"P{pid}", "photo": PHOTO} for pid in (1, 2, 3, 4)}
        html = season_section({"upto": 6, "ledger": ledger, "captaincy": [], "chips": [],
                               "bench": 7, "hits": 0, "players": players})
        self.assertAllHooked(html, players)

    def test_league_watchlist_and_rivals(self):
        watch = [{"id": 11, "name": "W", "duties": "", "home": True, "opponent": "ARS",
                  "pos": "MID", "club": "CHE", "price": 6.0, "ep": 30.0, "owned_pct": 2.0, "league": 0}]
        rival = [{"id": 12, "name": "R", "pos": "FWD", "club": "LIV", "points": 9,
                  "starters": 2, "captains": 1, "weeks": 1}]
        photos = {11: PHOTO, 12: PHOTO}
        html = (cards_league.differential_watchlist_card(watch, photos, 8, 6)
                + cards_league.rivals_card(rival, rival, 5, photos))
        self.assertAllHooked(html, {11, 12})

    def test_transfer_deck(self):
        figs = {"form": 4.0, "chance": 0.3, "fix": 6.0, "chance_label": "xGI/90"}
        single = {"out": SimpleNamespace(name="Old", element={"id": 21}),
                  "in": {"id": 22, "web_name": "New"}, "out_photo": PHOTO, "in_photo": PHOTO,
                  "opp": None, "spend": 0.0, "in_club": "ARS", "price": 7.0,
                  "in_score": {"total": 20.0}, "out_score": {"total": 15.0},
                  "figs": (figs, figs), "gain": 5.0}
        html = components.transfer_deck([single], [], end_gw=17)
        self.assertAllHooked(html, {21, 22})
        self.assertIn('data-player="21"', html)


class SourceTests(unittest.TestCase):
    PORTRAIT = re.compile(r"<img class=\"(?:[^\"]* )?(cut|face|df-photo|rv-photo)[\" ]")
    # Faces inside a navigation button (a week tile, a deck index entry).
    NAV = ('class="face" src="{photos[m["in"]]}" alt=""', "face_html = ")

    def test_every_portrait_site_carries_the_hook(self):
        for path in [*ROOT.glob("*.py"), *ROOT.glob("*.js")]:
            lines = path.read_text(encoding="utf-8").splitlines()
            for n, line in enumerate(lines):
                if not self.PORTRAIT.search(line) or any(x in line for x in self.NAV):
                    continue
                near = " ".join(lines[n:n + 3])
                with self.subTest(site=f"{path.name}:{n + 1}"):
                    self.assertTrue("hook(" in near or "data-player" in near, line.strip())


class FixtureTests(unittest.TestCase):
    def test_missing_projection_and_confirmed_blank_are_distinct(self):
        ctx = analysis.Ctx(boot={})
        ctx.teams = {1: {"short_name": "ARS", "name": "Arsenal"},
                     2: {"short_name": "NFO", "name": "Nottingham Forest"}}
        ctx.fixtures = [{"event": 7, "team_h": 1, "team_a": 2}]
        cells = playerprofile.club_fixtures(ctx, {}, 7, weeks=2)[1]
        self.assertEqual(cells, [{"gw": 7, "na": 1}, {"gw": 8, "blank": 1}])

    def test_rated_fixture_takes_fpl_opponent_and_venue(self):
        ctx = analysis.Ctx(boot={})
        ctx.teams = {1: {"short_name": "ARS", "name": "Arsenal"},
                     2: {"short_name": "NFO", "name": "Nottingham Forest"}}
        ctx.fixtures = [{"event": 7, "team_h": 1, "team_a": 2}]
        proj = {("ARS", 7): {"opp": "NFO", "ven": "H", "cs": 40, "g": 2.0},
                ("NFO", 7): {"opp": "ARS", "ven": "H", "cs": 10, "g": 0.8}}
        ars, nfo = (playerprofile.club_fixtures(ctx, proj, 7, weeks=1)[t][0] for t in (1, 2))
        self.assertEqual((ars["opp"], ars["h"]), (2, 1))
        self.assertEqual(nfo, {"gw": 7, "na": 1})   # projection says home, FPL says away


if __name__ == "__main__":
    unittest.main()
