"""Worst cases for the transfer plan, on synthetic squads.

Each test is a decision a manager would call obviously wrong if the plan
made it: spending an enabler on a mid-price bench player, buying a player
into his two hardest fixtures, burning a free transfer on a coin flip,
boosting a bench whose keeper never plays.
"""

import unittest

import planner

CAPS = {"GKP": 4.5, "DEF": 4.5, "MID": 5.0, "FWD": 5.0}
H = 8


def flat(v, n=H):
    return [float(v)] * n


def squad():
    """2/5/5/3, one club each. Bench by value: the non-playing keeper,
    the playing cheap defender, the cheap midfielder who does not play,
    and a 6.0 forward as the twelfth man."""
    rows, values = {}, {}

    def add(pid, pos, price, vals):
        rows[pid] = {"pos": pos, "club": f"C{pid}", "price": price}
        values[pid] = vals if isinstance(vals, list) else flat(vals)

    add(1, "GKP", 5.0, 4.0)
    add(2, "GKP", 4.0, 0.0)          # enabler, never plays
    for pid in (3, 4, 5, 6):
        add(pid, "DEF", 5.5, 4.0)
    add(7, "DEF", 4.0, 3.0)          # enabler who plays
    for pid in (8, 9, 10, 11):
        add(pid, "MID", 7.0, 5.0)
    add(12, "MID", 4.5, 0.5)         # enabler
    add(13, "FWD", 8.0, 5.5)
    add(14, "FWD", 8.0, 5.5)
    add(15, "FWD", 6.0, 4.0)         # twelfth man
    return rows, values


def run(rows, values, bank=0.5, ft=1, chips=(), **kw):
    ids = [p for p in range(1, 16)]
    sell = {p: rows[p]["price"] for p in ids}
    p = planner.Planner(rows, values, ids, sell, bank, ft, CAPS, chips, horizon=H, **kw)
    best = p.run()
    gws = list(range(10, 10 + len(values[1])))
    return p, best, planner.describe(p, best, planner.baseline(p), gws)


def moves(plan):
    return [(w["gw"], m["out"], m["in"]) for w in plan["weeks"] for m in w["moves"]]


class StructureTests(unittest.TestCase):
    def test_enablers_are_the_cheap_bench(self):
        p, _best, _plan = run(*squad())
        self.assertEqual(sorted(p.enablers), [2, 7, 12])

    def test_enabler_is_not_spent_on_a_mid_price_player(self):
        # A 6.0 midfielder who would start, affordable by selling the 4.5
        # enabler. Taken alone it benches a 7.0 midfielder: money moved
        # from the XI to the bench. Not allowed without a cheap arrival.
        rows, values = squad()
        rows[100] = {"pos": "MID", "club": "X", "price": 6.0}
        values[100] = flat(6.0)
        _p, _best, plan = run(rows, values, bank=1.5)
        self.assertNotIn(12, [o for _gw, o, i in moves(plan) if i == 100])
        for w in plan["weeks"]:
            for m in w["moves"]:
                if m["out_cheap"] and not m["in_cheap"]:
                    # Only as a restructure: a cheap player arrives the same week.
                    self.assertTrue(any(x["in_cheap"] and not x["out_cheap"]
                                        for x in w["moves"]))

    def test_restructure_happens_for_an_outstanding_player(self):
        # A 6.0 midfielder far better than the 6.0 forward: sell the cheap
        # midfielder for him, and the 6.0 forward for a cheap forward.
        rows, values = squad()
        rows[100] = {"pos": "MID", "club": "X", "price": 6.0}
        values[100] = flat(9.0)
        rows[101] = {"pos": "FWD", "club": "Y", "price": 4.5}
        values[101] = flat(2.0)
        _p, _best, plan = run(rows, values, bank=0.0, ft=2)
        got = moves(plan)
        self.assertIn((10, 12, 100), got)
        self.assertIn((10, 15, 101), got)

    def test_no_restructure_for_a_modest_upgrade(self):
        # Same shape, but the midfielder is only a little better than the
        # forward he effectively replaces: two transfers for one modest
        # upgrade is not worth making.
        rows, values = squad()
        rows[100] = {"pos": "MID", "club": "X", "price": 6.0}
        values[100] = flat(4.5)
        rows[101] = {"pos": "FWD", "club": "Y", "price": 4.5}
        values[101] = flat(2.0)
        _p, _best, plan = run(rows, values, bank=0.0, ft=2)
        self.assertEqual(moves(plan), [])


class TimingTests(unittest.TestCase):
    def test_waits_out_two_hard_fixtures(self):
        # Better than the defender he replaces, but not in the next two
        # weeks. With one free transfer and nothing else to spend it on,
        # buying him now throws away two weeks of the incumbent.
        rows, values = squad()
        rows[100] = {"pos": "DEF", "club": "X", "price": 5.5}
        values[100] = [2.0, 2.0] + [7.0] * (H - 2)
        _p, _best, plan = run(rows, values)
        got = moves(plan)
        self.assertTrue(got, "the upgrade should still be planned")
        self.assertEqual(got[0][0], 12, got)
        waited = plan["weeks"][2]["moves"][0]["waited"]
        self.assertIsNotNone(waited)
        self.assertGreater(waited["loss"], 0)

    def test_rolls_when_nothing_clears_the_margin(self):
        rows, values = squad()
        rows[100] = {"pos": "DEF", "club": "X", "price": 5.5}
        values[100] = flat(4.15)  # 1.2 points over eight weeks
        _p, _best, plan = run(rows, values)
        self.assertEqual(moves(plan), [])
        self.assertAlmostEqual(plan["gain"], 0.0, places=6)


class AccountingTests(unittest.TestCase):
    def test_bank_club_and_shape_stay_legal(self):
        rows, values = squad()
        # Three great players from one club, one per position; only so many
        # can be signed, and all of them cost money.
        for pid, pos in ((100, "DEF"), (101, "MID"), (102, "FWD"), (103, "MID")):
            rows[pid] = {"pos": pos, "club": "BIG", "price": 7.5}
            values[pid] = flat(8.0)
        rows[3]["club"] = "BIG"   # already own one
        p, best, plan = run(rows, values, bank=1.0, ft=5)
        ids = set(range(1, 16))
        for w in plan["weeks"]:
            for m in w["moves"]:
                ids = (ids - {m["out"]}) | {m["in"]}
            self.assertGreaterEqual(w["bank"], -1e-9)
            clubs = {}
            for pid in ids:
                clubs[rows[pid]["club"]] = clubs.get(rows[pid]["club"], 0) + 1
            self.assertLessEqual(max(clubs.values()), 3)
            shape = sorted(rows[pid]["pos"] for pid in ids)
            self.assertEqual(shape.count("GKP"), 2)
            self.assertEqual(shape.count("DEF"), 5)
            self.assertEqual(shape.count("MID"), 5)
            self.assertEqual(shape.count("FWD"), 3)

    def test_free_transfers_bank_to_five_and_hits_are_charged(self):
        rows, values = squad()
        _p, _best, plan = run(rows, values, ft=4)
        fts = [w["ft_before"] for w in plan["weeks"]]
        self.assertEqual(fts[:3], [4, 5, 5])
        self.assertTrue(all(w["hits"] == 0 for w in plan["weeks"]))

    def test_never_buys_back_or_sells_a_signing(self):
        rows, values = squad()
        rows[100] = {"pos": "DEF", "club": "X", "price": 5.5}
        values[100] = [8.0] * 3 + [1.0] * (H - 3)
        rows[101] = {"pos": "DEF", "club": "Y", "price": 5.5}
        values[101] = [1.0] * 3 + [8.0] * (H - 3)
        _p, _best, plan = run(rows, values, ft=2)
        outs = [o for _gw, o, _i in moves(plan)]
        ins = [i for _gw, _o, i in moves(plan)]
        self.assertFalse(set(outs) & set(ins))
        self.assertEqual(len(ins), len(set(ins)))


class BenchBoostTests(unittest.TestCase):
    def chips(self):
        return [{"key": "bboost", "first": 0, "last": H - 1}]

    def test_boost_goes_to_the_best_bench_week_not_the_first(self):
        rows, values = squad()
        values[7] = [3.0, 3.0, 3.0, 3.0, 3.0, 9.0, 3.0, 3.0]
        _p, _best, plan = run(rows, values, chips=self.chips())
        played = [w["gw"] for w in plan["weeks"] if w["chip"] == "bboost"]
        self.assertEqual(played, [15])

    def test_non_playing_keeper_is_replaced_before_the_boost(self):
        # A cheap keeper who starts, at the same money. Worth nothing in
        # normal weeks (a reserve keeper never comes on), but the whole
        # point of Bench Boost week is that he plays.
        rows, values = squad()
        rows[100] = {"pos": "GKP", "club": "X", "price": 4.5}
        values[100] = flat(3.5)
        values[7] = [3.0] * 5 + [9.0] + [3.0] * 2
        _p, _best, plan = run(rows, values, chips=self.chips(), bank=0.5, ft=2)
        boost = next(w for w in plan["weeks"] if w["chip"] == "bboost")
        self.assertIn(100, boost["bench"])
        self.assertNotIn(2, boost["bench"])

    def test_chip_held_past_the_plan_is_reported(self):
        rows, values = squad()
        long = H + 4
        for pid in values:
            values[pid] = values[pid] + [values[pid][-1]] * 4
        values[7] = [3.0] * H + [3.0, 12.0, 3.0, 3.0]
        _p, _best, plan = run(rows, values,
                              chips=[{"key": "bboost", "first": 0, "last": long - 1}])
        self.assertFalse(any(w["chip"] for w in plan["weeks"]))
        self.assertEqual(plan["held_chips"][0]["gw"], 10 + H + 1)


if __name__ == "__main__":
    unittest.main()
