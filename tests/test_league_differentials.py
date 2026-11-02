"""Your differentials: lowest overall ownership, enablers excluded."""

import unittest

import analysis
import cards_league


def make_ctx(specs):
    """specs: (id, element_type, now_cost, selected_by_percent) rows."""
    ctx = analysis.Ctx(boot={})
    ctx.teams[1] = {"short_name": "AAA", "name": "Alpha"}
    for pid, etype, cost, pct in specs:
        ctx.players[pid] = {
            "id": pid, "element_type": etype, "team": 1, "web_name": f"P{pid}",
            "now_cost": cost, "cost_change_start": 0, "total_points": 10 + pid,
            "selected_by_percent": str(pct), "expected_goal_involvements": "1.0"}
    return ctx


def league_of(ctx, mine, others=()):
    own = {}
    for pid in ctx.players:
        owners = (["Me"] if pid in mine else []) + (
            ["Rival"] if pid in others else [])
        if owners:
            own[pid] = {"owners": owners, "starters": owners, "captains": []}
    return own


class YourDifferentialsTests(unittest.TestCase):
    def setUp(self):
        # Defenders (type 2): cheapest start 4.0, so an enabler is <= 4.5.
        # Cheapest MID start 5.0 -> enabler <= 5.5; FWD floor 4.5 -> <= 5.0.
        self.ctx = make_ctx([
            (1, 2, 40, 0.5),    # DEF at the floor, 0.5% owned: enabler
            (2, 2, 45, 0.9),    # DEF at floor + 0.5: still an enabler
            (3, 3, 50, 0.4),    # MID at the floor: enabler
            (4, 2, 55, 12.0),   # DEF, not cheap
            (5, 3, 80, 3.0),    # MID
            (6, 4, 70, 7.5),    # FWD
            (7, 3, 120, 40.0),  # MID
            (8, 4, 90, 1.5),    # FWD, not mine
            (9, 3, 55, 2.0),    # MID at floor + 0.5: enabler
            (10, 4, 45, 20.0),  # sets the FWD floor; nobody owns him
        ])

    def test_enablers_excluded_and_lowest_overall_ownership_first(self):
        own = league_of(self.ctx, mine={1, 2, 3, 4, 5, 6, 7, 9}, others={4, 7})
        got = cards_league.your_differentials(own, self.ctx, "Me")
        self.assertEqual([pid for pid, _ in got], [5, 6, 4])

    def test_league_owner_count_is_carried_not_used_for_ranking(self):
        own = league_of(self.ctx, mine={4, 5, 6}, others={5, 6})
        got = dict(cards_league.your_differentials(own, self.ctx, "Me"))
        self.assertEqual(got, {5: 2, 6: 2, 4: 1})
        self.assertEqual(
            [pid for pid, _ in cards_league.your_differentials(own, self.ctx, "Me")],
            [5, 6, 4])

    def test_players_you_do_not_own_never_appear(self):
        own = league_of(self.ctx, mine={7}, others={8})
        self.assertEqual(
            [pid for pid, _ in cards_league.your_differentials(own, self.ctx, "Me")],
            [7])

    def test_card_shows_three_with_both_ownership_figures(self):
        own = league_of(self.ctx, mine={1, 4, 5, 6, 7})
        html = cards_league.differential_card(
            own, {"Me": 1, "Rival": 2}, self.ctx, "Me", {})
        self.assertEqual(html.count('class="df-card"'), 3)
        self.assertNotIn(">P1<", html)
        self.assertIn("3.0%", html)
        self.assertIn("1/2", html)

    def test_nothing_eligible_renders_nothing(self):
        own = league_of(self.ctx, mine={1, 2, 3})
        self.assertEqual(cards_league.differential_card(
            own, {"Me": 1}, self.ctx, "Me", {}), "")


if __name__ == "__main__":
    unittest.main()
