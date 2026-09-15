"""Regression cover for the transfer board's XI-based comparisons.

The bug these exist for was invisible on the page: `squadbuilder.best_xi`
returns None for a pool it cannot field an eleven from, `_xi_value` reported
that as 0.0, and every `_xi_swap_gain` therefore came out as 0.0 - 0.0 = 0.
Nothing errored. The Sell column simply read "nothing this week" every week
while Suggested transfers listed six sells directly beneath it.
"""

import unittest

import squadbuilder
import transfers


def pool_row(pid, pos, club, price, value):
    return {"id": pid, "pos": pos, "club": club, "price": price, "value": value}


def full_fifteen():
    """A legal squad: 2 GKP, 5 DEF, 5 MID, 3 FWD, spread across clubs."""
    rows = []
    pid = 1
    for pos, n in (("GKP", 2), ("DEF", 5), ("MID", 5), ("FWD", 3)):
        for i in range(n):
            rows.append(pool_row(pid, pos, f"C{pid % 7}", 5.0, 4.0 + i))
            pid += 1
    return rows


class XiValueTests(unittest.TestCase):
    def test_full_squad_has_a_value(self):
        self.assertIsNotNone(transfers._xi_value(full_fifteen()))

    def test_pool_that_cannot_field_an_xi_is_none_not_zero(self):
        # One goalkeeper short. best_xi fills a bench first and that bench
        # wants a second keeper, so no formation completes. Reported as 0.0
        # this silently zeroed every gain on the board.
        short = [r for r in full_fifteen() if r["pos"] != "GKP"][:14]
        self.assertIsNone(squadbuilder.best_xi(short, budget=1e9))
        self.assertIsNone(transfers._xi_value(short))

    def test_swap_gain_is_none_when_the_base_is_unknown(self):
        incoming = pool_row(99, "MID", "C9", 5.0, 30.0)
        self.assertIsNone(
            transfers._xi_swap_gain(full_fifteen(), None, 1, incoming))

    def test_a_bigger_upgrade_earns_more(self):
        own = full_fifteen()
        base = transfers._xi_value(own)
        worst_mid = min((r for r in own if r["pos"] == "MID"),
                        key=lambda r: r["value"])
        small = pool_row(98, worst_mid["pos"], worst_mid["club"], 5.0,
                         worst_mid["value"] + 2.0)
        big = pool_row(99, worst_mid["pos"], worst_mid["club"], 5.0,
                       worst_mid["value"] + 20.0)
        gain_small = transfers._xi_swap_gain(own, base, worst_mid["id"], small)
        gain_big = transfers._xi_swap_gain(own, base, worst_mid["id"], big)
        self.assertIsNotNone(gain_big)
        self.assertGreater(gain_big, gain_small)
        self.assertGreater(gain_big, 0)

    def test_a_bench_upgrade_is_worth_less_than_the_raw_gap(self):
        """The whole point of scoring a swap through the best XI (L2).

        A player who does not make the eleven can be replaced by someone far
        better on paper and change very little about what actually gets
        picked, so the XI gain has to come out below the raw difference
        between the two men's own totals."""
        own = full_fifteen()
        base = transfers._xi_value(own)
        bench_mid = min((r for r in own if r["pos"] == "MID"),
                        key=lambda r: r["value"])
        incoming_value = bench_mid["value"] + 30.0
        incoming = pool_row(99, "MID", bench_mid["club"], 5.0, incoming_value)
        gain = transfers._xi_swap_gain(own, base, bench_mid["id"], incoming)
        self.assertIsNotNone(gain)
        self.assertLess(gain, incoming_value - bench_mid["value"])


class RankSwapOptionsTests(unittest.TestCase):
    def _options(self, own):
        worst = min((r for r in own if r["pos"] == "MID"),
                    key=lambda r: r["value"])
        rows = [pool_row(100 + i, "MID", "C9", 5.0, worst["value"] + 5 * (i + 1))
                for i in range(3)]
        return worst, [{"raw_gain": r["value"] - worst["value"], "row": r}
                       for r in rows]

    def test_ranks_by_xi_gain_when_an_xi_can_be_built(self):
        own = full_fifteen()
        worst, options = self._options(own)
        ranked = transfers._rank_swap_options(
            own, transfers._xi_value(own), worst["id"], options, 10)
        gains = [o["gain"] for o in ranked]
        self.assertEqual(gains, sorted(gains, reverse=True))
        self.assertGreater(gains[0], 0)

    def test_falls_back_to_the_raw_gain_rather_than_reporting_no_gain(self):
        # A caller that cannot build an XI still has to rank its options.
        # Zeroing them was the failure this whole module's bug came from.
        own = [r for r in full_fifteen() if r["pos"] != "GKP"][:14]
        worst, options = self._options(own)
        ranked = transfers._rank_swap_options(own, None, worst["id"], options, 10)
        self.assertTrue(all(o["gain"] == o["raw_gain"] for o in ranked))
        self.assertTrue(all(o["gain"] > 0 for o in ranked))


if __name__ == "__main__":
    unittest.main()
