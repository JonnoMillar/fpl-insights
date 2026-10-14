"""Regression cases from the CV-readiness audit; no network access required."""

import itertools
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import analysis
import cards_common
import cards_league
import cards_planning
import cards_squad
import chips
import dashboard
import fplapi
import squadbuilder
import transfers
import ticker
from tests.test_transfers import full_fifteen


def make_reports(pool):
    ctx = analysis.Ctx(boot={})
    positions = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    reports, scores = [], {}
    for row in pool:
        el = {"id": row["id"], "element_type": positions[row["pos"]],
              "team": row["club"], "web_name": str(row["id"]),
              "now_cost": round(row["price"] * 10), "status": "a",
              "minutes": 540, "starts": 6, "transfers_in_event": 0}
        ctx.players[el["id"]] = el
        ctx.teams[el["team"]] = {"short_name": el["team"], "name": el["team"]}
        reports.append(SimpleNamespace(element=el, pos=row["pos"], team=row["club"],
                                       price=row["price"], name=str(row["id"])))
        scores[el["id"]] = {"total": row["value"], "opponent": "OPP", "home": True}
    return ctx, reports, scores


class DocumentTests(unittest.TestCase):
    def test_embedded_json_cannot_close_its_script(self):
        name = '</script><script>window.probe=1</script> & "João"'
        data = {"gws": [1, 2, 3, 4, 5], "managers": 2, "series": [
            {"name": name, "mine": False, "points": [1] * 5, "position": [2] * 5},
            {"name": "Normal", "mine": True, "points": [2] * 5, "position": [1] * 5}]}
        html = cards_league.league_position_card(data)
        self.assertEqual(html.count('<script'), 1)
        encoded = cards_common.script_json(data)
        self.assertNotIn('<', encoded)
        self.assertEqual(json.loads(encoded), data)

    def test_hosted_output_has_a_real_document_and_metadata(self):
        fields = ["pitch", "pick_pitch", "squad_table", "findings", "market", "best_xi",
                  "kneejerk", "verdicts", "transfers", "pairings", "captaincy", "chip_planner",
                  "ticker", "fixture_runs", "leaders", "price_watch", "scatter", "elite",
                  "league_table", "position_chart", "template", "carousel", "differentials",
                  "watchlist", "rivals", "ownership", "chips", "scout", "dialog"]
        data = dict.fromkeys(fields, "")
        data.update(ctx=analysis.Ctx(boot={}), team_name="Test squad", manager="Manager",
                    league_name="League", entry_history={}, gw=6, next_gw=7,
                    league_size=8, my_rank=4, generated="14 Oct 2026", source_health={})
        html = dashboard.render(data, standalone=True)
        self.assertTrue(html.startswith('<!doctype html>'))
        self.assertIn('lang="en"', html)
        self.assertIn('name="viewport"', html)
        self.assertIn('name="description"', html)
        self.assertIn('<title>FPL Insights', html)


class SelectionTests(unittest.TestCase):
    def test_owned_selection_matches_exhaustive_maximum_regardless_of_prices(self):
        pool = full_fifteen()
        pool[0].update(price=4, value=100)
        pool[1].update(price=7, value=2)
        exact = max(sum(p["value"] for p in xi) for xi in itertools.combinations(pool, 11)
                    if sum(p["pos"] == "GKP" for p in xi) == 1
                    and tuple(sum(p["pos"] == pos for p in xi)
                              for pos in ("DEF", "MID", "FWD")) in squadbuilder.FORMATIONS)
        chosen = squadbuilder.owned_xi(pool)
        self.assertEqual(chosen["value"], exact)
        self.assertIn(1, {p["id"] for p in chosen["xi"]})
        self.assertEqual(transfers._xi_value(pool), exact)

    def test_pair_gain_is_the_combined_squad_change(self):
        pool = full_fifteen()
        ctx, reports, scores = make_reports(pool)
        for pid, value in ((98, 50), (99, 49)):
            ctx.players[pid] = {"id": pid, "element_type": 3, "team": "NEW",
                                "now_cost": 50, "status": "a", "minutes": 540, "web_name": str(pid)}
            scores[pid] = {"total": value, "opponent": "OPP", "home": True}
        ctx.teams["NEW"] = {"name": "New", "short_name": "NEW"}
        with patch.object(transfers, "case_score", side_effect=lambda el, *a, **k: scores[el["id"]]), \
             patch.object(transfers, "positional_priors", return_value={}):
            pairs = transfers.pair_suggestions(ctx, reports, {}, 7, {}, {}, limit=2)
        self.assertTrue(pairs)
        for pair in pairs:
            sold = {leg["out"].element["id"] for leg in pair["legs"]}
            after = [p for p in pool if p["id"] not in sold]
            after += [transfers._candidate_pool_row(leg["in"], ctx, leg["in_score"]["total"])
                      for leg in pair["legs"]]
            raw = sum(leg["in_score"]["total"] - leg["out_score"]["total"] for leg in pair["legs"])
            expected = transfers._xi_value(after) - transfers._xi_value(pool)
            expected += transfers.BENCH_AUTOSUB_ALLOWANCE * raw
            self.assertAlmostEqual(pair["gain"], expected)
            self.assertAlmostEqual(pair["after_hit"], expected - 4)

    def test_current_price_cannot_fund_a_move_that_sell_price_cannot(self):
        pool = full_fifteen()
        pool[7]["price"] = 6.0
        ctx, reports, scores = make_reports(pool)
        ctx.players[98] = {"id": 98, "element_type": 3, "team": "NEW", "now_cost": 91,
                           "minutes": 540, "status": "a", "web_name": "Incoming"}
        ctx.teams["NEW"] = {"name": "New", "short_name": "NEW"}
        scores[98] = {"total": 50, "opponent": "OPP", "home": True}
        sold = {r.element["id"]: r.price for r in reports}
        sold[reports[7].element["id"]] = 5.5
        with patch.object(transfers, "case_score", side_effect=lambda el, *a, **k: scores[el["id"]]), \
             patch.object(transfers, "positional_priors", return_value={}):
            self.assertTrue(transfers.suggest(ctx, reports, {}, 7, {}, {}, bank=3.1))
            self.assertEqual(transfers.suggest(ctx, reports, {}, 7, {}, {}, bank=3.1, sell_values=sold), [])

    def test_buy_and_avoid_do_not_overlap(self):
        ctx, reports, scores = make_reports(full_fifteen())
        for pid, value in ((98, 40), (99, 36)):
            ctx.players[pid] = {"id": pid, "element_type": 3, "team": "NEW",
                                "now_cost": 50, "web_name": str(pid), "transfers_in_event": 500000}
            scores[pid] = {"total": value, "opponent": "OPP", "home": True}
        ctx.teams["NEW"] = {"name": "New", "short_name": "NEW"}
        board = transfers.verdict_board(ctx, reports, scores, bank=3)
        self.assertTrue(board["avoid"])
        self.assertFalse({r["id"] for r in board["buy"]} & {r["id"] for r in board["avoid"]})


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.ctx = analysis.Ctx(boot={})
        self.ctx.teams = {1: {"short_name": "ARS", "name": "Arsenal"},
                          2: {"short_name": "NFO", "name": "Nottingham Forest"}}
        self.ctx.fixtures = [{"event": 7, "team_h": 1, "team_a": 2,
                              "kickoff_time": "2026-10-17T15:00:00Z"}]
        self.el = {"id": 1, "team": 1, "element_type": 2, "minutes": 540, "photo": "123.png",
                   "web_name": "Player", "now_cost": 50, "selected_by_percent": "10", "status": "a"}
        self.report = analysis.PlayerReport(self.el, "DEF", "ARS", [], [])
        self.market = {"ARS": {"opp": "NFO", "home": True, "kickoff": "2026-10-17T15:00",
                               "xg": 2, "cs": 40, "total": 3}}

    def test_market_is_not_repeated_into_a_blank_or_double_week(self):
        for score in (lambda gw: analysis.expected_points(self.report, self.ctx, {}, gw, self.market),
                      lambda gw: transfers.candidate_score(self.el, self.ctx, {}, gw, self.market, {})):
            self.assertIsNotNone(score(7))
            self.assertIsNone(score(8))
        self.ctx.fixtures.append(dict(self.ctx.fixtures[0]))
        self.assertEqual(self.ctx.scoring_fixture(self.el, {}, 7, self.market), (None, None))

    def test_wrong_date_or_venue_market_is_rejected(self):
        for changed in ({"home": False}, {"kickoff": "2026-11-17T15:00"}):
            with self.subTest(changed=changed):
                market = {"ARS": {**self.market["ARS"], **changed}}
                self.assertEqual(self.ctx.scoring_fixture(self.el, {}, 7, market), (None, None))

    def test_missing_projection_and_confirmed_blank_have_distinct_dialog_states(self):
        payload = cards_squad.player_payload(self.report, self.ctx, {}, None, 7, {})
        self.assertTrue(payload["fixtures"][0]["unavailable"])
        self.assertTrue(payload["fixtures"][1]["blank"])

    def test_pick_team_can_render_without_fixture_projections(self):
        self.assertIn('Unavailable', cards_common.pos_fixture_pill('DEF', None, None, 0, 0))
        self.assertIn('Unavailable', ticker.rating_pill(None, None, 0))

    def test_lineup_from_the_old_club_is_unknown(self):
        self.ctx.predicted = {"123": "Aston Villa", "124": "Arsenal"}
        self.assertIsNone(self.ctx.is_predicted(self.el))
        self.ctx.predicted["123"] = "Arsenal"
        self.assertTrue(self.ctx.is_predicted(self.el))
        del self.ctx.predicted["123"]
        self.assertFalse(self.ctx.is_predicted(self.el))

    def test_next_event_does_not_skip_the_upcoming_week_or_invent_gw39(self):
        self.ctx.events = [{"id": 1, "is_next": True}]
        self.assertEqual(self.ctx.next_event(), 1)
        self.ctx.events = [{"id": 38, "finished": True}]
        self.assertIsNone(self.ctx.next_event())


class ChipTests(unittest.TestCase):
    def test_triple_captain_and_timing_copy_are_consistent(self):
        tc = {"player": SimpleNamespace(name="Captain"), "gw": 7, "ep": 8,
              "confidence": "flexible", "series": [(7, 8), (8, 7.9), (9, 2)]}
        html = cards_planning.chip_planner_card(None, tc, None, None, {}, [], [], None, {}, {}, {}, {}, 7)
        self.assertIn('24.0 with Triple Captain', html)
        self.assertIn('8.0 more than a normal captaincy', html)
        self.assertIn('timing is flexible', html)
        self.assertNotIn('clearly ahead', html)

    def test_bench_boost_checks_full_squad_and_proposes_one_move(self):
        ctx, reports, _ = make_reports(full_fifteen())
        sale_values = {r.element["id"]: r.price for r in reports}
        with patch.object(analysis, "expected_points", return_value={"total": 2}), \
             patch.object(transfers, "suggest", return_value=[]) as suggest:
            chips.bench_boost(ctx, reports[-4:], {}, {}, {}, 7, bank=3.1,
                              full_squad=reports, sell_values=sale_values)
        kwargs = suggest.call_args.kwargs
        self.assertEqual(kwargs["limit"], 1)
        self.assertEqual(kwargs["full_squad"], reports)
        self.assertEqual(kwargs["sell_values"], sale_values)

    def test_bench_boost_fixture_pills_use_target_week(self):
        ctx, reports, _ = make_reports(full_fifteen())
        bb = {"gw": 13, "transfers": []}
        with patch.object(cards_planning, "_fixture_pill_for", return_value="") as pill:
            cards_planning.bench_boost_pitch(bb, reports[-4:], ctx, {}, {}, {}, {}, 7)
        self.assertTrue(all(call.args[-1] == 13 for call in pill.call_args_list))


if __name__ == "__main__":
    unittest.main()
