import unittest

import season
from cards_season import season_section


def move(gw, out, inn, time):
    return {"event": gw, "element_out": out, "element_in": inn, "time": time,
            "element_in_cost": 60, "element_out_cost": 60}


def hist(gw, cost=0, bench=0):
    return {"event": gw, "event_transfers_cost": cost, "points_on_bench": bench}


# Points per finished gameweek: player 1 sold for 2 in GW3, 2 sold for 3 in GW5.
POINTS = {
    1: {1: 2, 2: 8, 3: 1, 4: 0},
    2: {1: 4, 2: 6, 3: 1, 4: 0},
    3: {1: 10, 2: 2, 3: 3, 4: 5},
    4: {1: 6, 2: 7, 3: 2, 4: 1},
    5: {1: 1, 2: 0, 3: 9, 4: 2},
    6: {1: 3, 2: 4, 3: 6, 4: 2},
}


class LedgerTests(unittest.TestCase):
    def ledger(self, transfers, history=None, chips=()):
        history = history or [hist(gw) for gw in POINTS]
        return season.transfer_ledger(transfers, history, POINTS, chips)

    def test_chained_signing_is_held_until_sold_again(self):
        rows = self.ledger([move(3, 1, 2, "a"), move(5, 2, 3, "b")])
        first, second = rows
        # 2 is held GW3-4: 2+7 against 1's 10+6.
        self.assertEqual((first["first"], first["last"], first["weeks"]), (3, 4, 2))
        self.assertEqual((first["pts_in"], first["pts_out"], first["net"]), (9, 16, -7))
        # 3 is held from GW5 to the last finished week: 9+6 against 2's 0+4.
        self.assertEqual((second["weeks"], second["net"]), (2, 11))

    def test_form_before_and_after(self):
        row = self.ledger([move(5, 4, 3, "a")])[0]
        # Four weeks before GW5 for player 3: 1, 1, 3, 2.
        self.assertAlmostEqual(row["form_before"], 7 / 4)
        self.assertAlmostEqual(row["form_after"], 15 / 2)
        early = self.ledger([move(2, 4, 3, "a")])[0]
        self.assertAlmostEqual(early["form_before"], 1.0)  # only GW1 exists before
        self.assertIsNone(self.ledger([move(1, 4, 3, "a")])[0]["form_before"])

    def test_hit_lands_on_the_last_move_of_the_week(self):
        history = [hist(gw, cost=4 if gw == 3 else 0) for gw in POINTS]
        rows = self.ledger([move(3, 4, 3, "b"), move(3, 1, 2, "a")], history)
        by_in = {r["in"]: r for r in rows}
        self.assertEqual(by_in[2]["hit"], 0)          # made first, used the free one
        self.assertEqual(by_in[3]["hit"], 4)
        self.assertEqual(by_in[3]["net"], (3 + 2 + 9 + 6) - (5 + 1 + 2 + 2) - 4)

    def test_free_hit_moves_last_one_week(self):
        rows = self.ledger([move(4, 1, 3, "a")], chips=[{"name": "freehit", "event": 4}])
        self.assertEqual((rows[0]["weeks"], rows[0]["pts_in"], rows[0]["pts_out"]), (1, 2, 6))

    def test_moves_without_a_finished_week_are_left_out(self):
        self.assertEqual(self.ledger([move(7, 1, 2, "a")]), [])
        # Bought and sold again inside one week: never held across a deadline.
        rows = self.ledger([move(3, 1, 2, "a"), move(3, 2, 3, "b")])
        self.assertEqual([r["in"] for r in rows], [3])


def picks(cap, vice, xi, mult=2):
    out = [{"element": pid, "position": i + 1, "is_captain": pid == cap,
            "is_vice_captain": pid == vice, "multiplier": 1} for i, pid in enumerate(xi)]
    next(p for p in out if p["element"] == cap)["multiplier"] = mult
    return {"picks": out}


class CaptaincyTests(unittest.TestCase):
    def test_lost_points_count_the_multiplier(self):
        mins = {gw: {pid: 90 for pid in pts} for gw, pts in POINTS.items()}
        rows = season.captaincy({1: picks(1, 2, [1, 2, 3]), 3: picks(2, 1, [1, 2, 3], mult=3)},
                                POINTS, mins)
        self.assertEqual(rows[0]["best"], 2)
        self.assertEqual(rows[0]["lost"], 8 - 2)
        self.assertEqual((rows[1]["mult"], rows[1]["lost"]), (3, (10 - 2) * 2))

    def test_vice_takes_the_armband_when_the_captain_sits_out(self):
        mins = {6: {1: 0, 2: 90, 3: 90}}
        row = season.captaincy({6: picks(1, 3, [1, 2, 3])}, POINTS, mins)[0]
        self.assertEqual((row["captain"], row["cap_pts"], row["lost"]), (3, 6, 0))
        self.assertEqual(row["best"], 3)  # the vice was also the top scorer

    def test_unfinished_weeks_are_ignored(self):
        self.assertEqual(season.captaincy({9: picks(1, 2, [1, 2])}, POINTS, {}), [])


class ChipTests(unittest.TestCase):
    def test_triple_captain_and_bench_boost_returns(self):
        caps = [{"gw": 3, "cap_pts": 10}]
        out = season.chip_returns([hist(5, bench=12)],
                                  [{"name": "3xc", "event": 3}, {"name": "bboost", "event": 5},
                                   {"name": "wildcard", "event": 6}], caps)
        self.assertEqual([c["gain"] for c in out], [10, 12, None])


class RenderTests(unittest.TestCase):
    def test_missing_review_renders_nothing(self):
        self.assertEqual(season_section(None), "")

    def test_names_are_escaped_and_figures_signed(self):
        ledger = season.transfer_ledger([move(3, 1, 2, "a"), move(5, 4, 3, "b")],
                                        [hist(gw) for gw in POINTS], POINTS)
        players = {pid: {"name": f"P{pid}", "photo": None} for pid in (1, 2, 3, 4)}
        players[2]["name"] = "<b>Évan</b>"
        html = season_section({"upto": 6, "ledger": ledger, "captaincy": [],
                               "chips": [], "bench": 7, "hits": 0, "players": players})
        self.assertIn("&lt;b&gt;Évan&lt;/b&gt;", html)
        self.assertNotIn("<b>Évan</b>", html)
        self.assertIn("Best move · GW5", html)
        self.assertIn("Worst move · GW3", html)
        self.assertIn("−7", html)      # real minus sign on the loss


if __name__ == "__main__":
    unittest.main()
