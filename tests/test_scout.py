"""
Unit tests for scout.py - the first tests in this repo (see plan
docs/superpowers/plans/2026-09-08-scout-section-plan.md, phase 0).

stdlib unittest only, no pytest - zero third-party dependencies is a
project value (see README), and that applies to the test runner too.

Run with, from the repo root:
    python -m unittest discover -s tests -t .
"""

import unittest
from unittest import mock

import analysis
import scout


def make_ctx(players=None, teams=None, events=None, fixtures=None):
    ctx = analysis.Ctx(boot={})
    ctx.players = players or {}
    ctx.teams = teams or {}
    ctx.events = events or []
    ctx.fixtures = fixtures or []
    return ctx


def make_defender(pid, team, web_name="Player", minutes=270, starts=3,
                   defcon_per90=8.0, xgi_per90=0.1, xgc_per90=1.0,
                   bps=90, bonus=0, yellow=0, red=0, status="a",
                   chance=None, transfers_in=0, transfers_out=0,
                   now_cost=50, ownership="10.0"):
    return {
        "id": pid, "web_name": web_name, "team": team, "element_type": 2,
        "minutes": minutes, "starts": starts,
        "defensive_contribution": 0,  # season total unused by raw_rows directly
        "defensive_contribution_per_90": defcon_per90,
        "expected_goal_involvements_per_90": xgi_per90,
        "expected_goals_conceded_per_90": xgc_per90,
        "bps": bps, "bonus": bonus,
        "yellow_cards": yellow, "red_cards": red,
        "now_cost": now_cost, "selected_by_percent": ownership,
        "transfers_in_event": transfers_in, "transfers_out_event": transfers_out,
        "corners_and_indirect_freekicks_order": None,
        "direct_freekicks_order": None, "penalties_order": None,
        "status": status, "chance_of_playing_next_round": chance, "news": "",
    }


class PercentileRankTests(unittest.TestCase):
    def test_ties_split_the_difference(self):
        # Three equal values: each sits at the pool's midpoint, not at
        # whichever end a naive "count strictly below" would put it.
        vals = [5.0, 5.0, 5.0]
        self.assertAlmostEqual(scout.percentile_rank(vals, 5.0), 50.0)

    def test_single_value_pool(self):
        self.assertEqual(scout.percentile_rank([5.0], 5.0), 100.0)

    def test_empty_pool_does_not_raise(self):
        self.assertEqual(scout.percentile_rank([], 5.0), 0.0)

    def test_lowest_and_highest(self):
        vals = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(scout.percentile_rank(vals, 1.0), 12.5)
        self.assertEqual(scout.percentile_rank(vals, 4.0), 87.5)


class ZScoreTests(unittest.TestCase):
    def test_zero_variance_pool_returns_zero_not_nan(self):
        vals = [3.0, 3.0, 3.0]
        self.assertEqual(scout.zscore(vals, 3.0), 0.0)

    def test_single_value_pool_returns_zero(self):
        self.assertEqual(scout.zscore([3.0], 3.0), 0.0)

    def test_above_mean_is_positive(self):
        vals = [1.0, 2.0, 3.0]
        self.assertGreater(scout.zscore(vals, 3.0), 0.0)


class ApplyDerivationsTests(unittest.TestCase):
    """apply_derivations is pure over plain row dicts, so it is tested
    directly against hand-built rows rather than through raw_rows - this
    is the part scout.js has to port line-for-line, so its formulas are
    exercised in isolation from the FPL data shape."""

    def _row(self, pid, xgc90, xgi90=0.1, defcon_hit_rate=0.5, start_rate=0.8,
              minutes=300, minutes_per_start=90.0, bps90=20.0, cards90=0.0,
              defcon90=8.0, bonus90=0.0, xp=0.0, xg90=0.05, xa90=0.05):
        return {
            "id": pid, "xgc90": xgc90, "xgi90": xgi90,
            "xg90": xg90, "xa90": xa90,
            "defconHitRate": defcon_hit_rate, "startRate": start_rate,
            "minutes": minutes, "minutesPerStart": minutes_per_start,
            "bps90": bps90, "cards90": cards90, "defcon90": defcon90,
            "bonus90": bonus90, "xp": xp,
        }

    def test_solidity_is_inverted_low_xgc_scores_high(self):
        rows = [self._row(1, xgc90=0.3), self._row(2, xgc90=0.9),
                self._row(3, xgc90=1.5)]
        scout.apply_derivations(rows, archetypes={})
        by_id = {r["id"]: r for r in rows}
        self.assertGreater(by_id[1]["solidityPct"], by_id[2]["solidityPct"])
        self.assertGreater(by_id[2]["solidityPct"], by_id[3]["solidityPct"])

    def test_xgc90_percentile_is_also_inverted(self):
        # xgc90 is flagged invert=True in METRICS - the heatmap column and
        # the bubble-size metric must agree on which end is good.
        rows = [self._row(1, xgc90=0.3), self._row(2, xgc90=1.5)]
        scout.apply_derivations(rows, archetypes={})
        by_id = {r["id"]: r for r in rows}
        self.assertGreater(by_id[1]["percentiles"]["xgc90"],
                            by_id[2]["percentiles"]["xgc90"])

    def test_percentile_is_relative_to_the_pool_passed_in(self):
        # The same player's percentile changes depending on who else is in
        # the filtered pool - recomputing per filter change is the whole
        # point (spec §2.1), so a stale percentile from a bigger pool must
        # never leak through.
        strong_pool = [self._row(1, xgc90=0.9)] + [
            self._row(100 + i, xgc90=0.4) for i in range(4)
        ]
        weak_pool = [self._row(1, xgc90=0.9)] + [
            self._row(200 + i, xgc90=1.6) for i in range(4)
        ]
        scout.apply_derivations(strong_pool, archetypes={})
        scout.apply_derivations(weak_pool, archetypes={})
        pct_in_strong_pool = strong_pool[0]["percentiles"]["xgc90"]
        pct_in_weak_pool = weak_pool[0]["percentiles"]["xgc90"]
        self.assertNotEqual(pct_in_strong_pool, pct_in_weak_pool)
        self.assertGreater(pct_in_weak_pool, pct_in_strong_pool)

    def test_zero_variance_metric_does_not_raise(self):
        rows = [self._row(i, xgc90=1.0, cards90=0.0) for i in range(5)]
        scout.apply_derivations(rows, archetypes={})
        for r in rows:
            self.assertEqual(r["z"]["cards90"], 0.0)

    def test_archetype_requires_top_third_percentile(self):
        # Five rows, one clear leader on xgi90 - only the top third (the
        # ~66.7th percentile and above) should qualify for the archetype
        # driven by it, per spec §2.
        rows = [self._row(i, xgc90=1.0, xgi90=v, minutes=400)
                for i, v in enumerate([0.05, 0.1, 0.15, 0.2, 0.9])]
        scout.apply_derivations(rows, archetypes={"attacking": "xgi90"})
        tagged = {r["id"] for r in rows if "attacking" in r["archetypes"]}
        self.assertIn(4, tagged)   # the 0.9 outlier
        self.assertNotIn(0, tagged)  # the weakest

    def test_archetype_suppressed_below_sample_gate(self):
        # A player who would otherwise top the pool on the driving metric,
        # but has not played enough minutes for the number to mean
        # anything (plan §2.1) - must not carry the badge.
        rows = [self._row(1, xgc90=1.0, xgi90=0.9, minutes=45),
                self._row(2, xgc90=1.0, xgi90=0.1, minutes=400),
                self._row(3, xgc90=1.0, xgi90=0.1, minutes=400)]
        scout.apply_derivations(rows, archetypes={"attacking": "xgi90"})
        by_id = {r["id"]: r for r in rows}
        self.assertNotIn("attacking", by_id[1]["archetypes"])

    def test_solidity_pct_archetype_key(self):
        # 'solidity_pct' is not a METRICS entry - it is looked up straight
        # off r['solidityPct'] via the percentiles dict, not through the
        # metric-field table. If that wiring breaks, every row silently
        # fails to qualify for the archetype rather than raising.
        rows = [self._row(i, xgc90=v, minutes=400)
                for i, v in enumerate([1.6, 1.2, 0.9, 0.5, 0.2])]
        scout.apply_derivations(rows, archetypes={"cleanSheet": "solidity_pct"})
        tagged = {r["id"] for r in rows if "cleanSheet" in r["archetypes"]}
        self.assertIn(4, tagged)  # lowest xGC, best solidity
        self.assertNotIn(0, tagged)


class RawRowsTests(unittest.TestCase):
    def _ctx(self, extra_fixtures=()):
        players = {1: make_defender(1, team=10, starts=3, minutes=270)}
        teams = {10: {"short_name": "AAA"}, 20: {"short_name": "BBB"}}
        fixtures = [
            {"id": 1, "event": 1, "team_h": 10, "team_a": 20,
             "finished": True, "finished_provisional": True, "started": True},
            {"id": 2, "event": 2, "team_h": 20, "team_a": 10,
             "finished": True, "finished_provisional": True, "started": True},
            {"id": 3, "event": 3, "team_h": 10, "team_a": 20,
             "finished": True, "finished_provisional": True, "started": True},
        ] + list(extra_fixtures)
        return make_ctx(players=players, teams=teams, fixtures=fixtures)

    def test_defcon_hit_rate_denominator_is_starts_not_appearances(self):
        # One started match hitting the threshold, one substitute cameo
        # that would drag the rate down if it were counted in the
        # denominator (spec §3.1 / plan §2 deliberately reads STARTS only).
        ctx = self._ctx()
        live = {1: [
            {"gw": 1, "status": "started", "defconHit": True, "minutes": 90},
            {"gw": 2, "status": "subbedOn", "defconHit": False, "minutes": 12},
        ]}
        rows = scout.raw_rows(ctx, "DEF", live)
        row = rows[0]
        self.assertEqual(row["defconHitN"], 1)
        self.assertEqual(row["defconHits"], 1)
        self.assertEqual(row["defconHitRate"], 1.0)

    def test_zero_starts_does_not_divide_by_zero(self):
        ctx = self._ctx()
        players = ctx.players
        players[2] = make_defender(2, team=10, starts=0, minutes=12)
        live = {2: [{"gw": 1, "status": "subbedOn", "defconHit": False, "minutes": 12}]}
        rows = scout.raw_rows(ctx, "DEF", live, min_minutes=1)
        row = next(r for r in rows if r["id"] == 2)
        self.assertEqual(row["defconHitRate"], 0.0)
        self.assertEqual(row["minutesPerStart"], 0.0)
        self.assertEqual(row["startRate"], 0.0)

    def test_first_start_mid_season_keeps_both_denominators(self):
        # The club has three played fixtures (gw1-3); this player's first
        # start is gw2. Two rates come out of that and they answer different
        # questions, so both are kept.
        #
        # `startRate` is his share of the club's whole season, because that is
        # the one a manager is actually asking about ("does he start?") and
        # the since-first-start figure answers it wrongly in September: a man
        # who has started one of his club's three reads 1/1 = 100%, which put
        # rotation risks at the top of a leaderboard called "Nailed on".
        #
        # `startRateSinceFirst` keeps spec §2.1's protection for a January
        # signing, and `_apply_filters` filters on whichever is kinder - so
        # nobody is excluded from the pool for matches played before he
        # arrived, while the column still shows the strict number.
        ctx = self._ctx()
        live = {1: [
            {"gw": 1, "status": "unplayed", "defconHit": False, "minutes": 0},
            {"gw": 2, "status": "started", "defconHit": False, "minutes": 90},
            {"gw": 3, "status": "started", "defconHit": False, "minutes": 90},
        ]}
        ctx.players[1]["starts"] = 2
        ctx.players[1]["minutes"] = 180
        rows = scout.raw_rows(ctx, "DEF", live)
        row = rows[0]
        self.assertEqual(row["teamMatchesSinceFirstStart"], 2)
        self.assertEqual(row["teamMatches"], 3)
        self.assertEqual(row["startRate"], 0.667)
        self.assertEqual(row["startRateSinceFirst"], 1.0)
        # Generous denominator, so he survives a filter his strict rate fails.
        self.assertEqual(
            [r["id"] for r in scout._apply_filters(rows, {"minStartRate": 0.9})],
            [1],
        )

    def test_thin_sample_is_flagged(self):
        # A single start is arithmetic, not evidence: every rate on the row is
        # off one match. The leaderboards drop him outright; the pool table
        # keeps him and marks him, so a 100% off one start never renders the
        # same as a 100% off ten.
        ctx = self._ctx()
        live = {1: [{"gw": 3, "status": "started", "defconHit": True,
                     "minutes": 101}]}
        ctx.players[1]["starts"] = 1
        ctx.players[1]["minutes"] = 101
        row = scout.raw_rows(ctx, "DEF", live, min_minutes=1)[0]
        self.assertTrue(row["thin"])
        self.assertEqual(row["startRate"], 0.333)
        self.assertEqual(row["defconHitRate"], 1.0)
        # Minutes per start caps at 90: FPL counts stoppage, and an uncapped
        # average made a cameo read as more durable than an ever-present.
        self.assertEqual(row["minutesPerStart"], 90.0)
        self.assertEqual(scout._eligible([row]), [])

    def test_min_minutes_filters_out_unplayed_players(self):
        ctx = self._ctx()
        ctx.players[2] = make_defender(2, team=10, starts=0, minutes=0)
        rows = scout.raw_rows(ctx, "DEF", {}, min_minutes=1)
        self.assertNotIn(2, [r["id"] for r in rows])

    def test_wrong_position_excluded(self):
        ctx = self._ctx()
        midfielder = make_defender(2, team=10)
        midfielder["element_type"] = 3
        ctx.players[2] = midfielder
        rows = scout.raw_rows(ctx, "DEF", {})
        self.assertNotIn(2, [r["id"] for r in rows])


class FixtureRowsTests(unittest.TestCase):
    def test_blank_gameweek_keeps_columns_aligned(self):
        # club has a fixture in gw4 and gw6 but not gw5 (a blank) - the
        # output must still carry three rows so a table built from it does
        # not silently shift gw6 into gw5's column.
        proj = {
            ("AAA", 4): {"cs": 40.0, "g": 1.2, "opp": "BBB", "ven": "H"},
            ("AAA", 6): {"cs": 30.0, "g": 1.0, "opp": "CCC", "ven": "A"},
            ("BBB", 4): {"cs": 20.0, "g": 1.8, "opp": "AAA", "ven": "A"},
            ("CCC", 6): {"cs": 25.0, "g": 1.5, "opp": "AAA", "ven": "H"},
        }
        rows = scout.fixture_rows("AAA", proj, start_gw=4, weeks=3)
        self.assertEqual([r["gw"] for r in rows], [4, 5, 6])
        self.assertTrue(rows[1].get("blank"))
        self.assertFalse(rows[0].get("blank", False))
        self.assertFalse(rows[2].get("blank", False))

    def test_difficulty_points_opposite_directions(self):
        # spec §3.2: a fixture that suppresses clean sheets (strong
        # opponent, so this club's own cs% is low) should make contributions
        # *easier* to hit (the opponent attacks more, so more clearances/
        # tackles) - the two rows must move in opposite directions for the
        # same fixture, never together.
        proj = {
            ("AAA", 4): {"cs": 8.0, "g": 0.8, "opp": "BBB", "ven": "H"},
            ("BBB", 4): {"cs": 50.0, "g": 2.2, "opp": "AAA", "ven": "A"},
        }
        rows = scout.fixture_rows("AAA", proj, start_gw=4, weeks=1)
        row = rows[0]
        # Hard to keep a clean sheet against a side expected to score 2.2...
        self.assertGreaterEqual(row["cleanSheetDifficulty"], 4)
        # ...but that same high-xG opponent means plenty to defend against,
        # so hitting the DEFCON threshold should read as comparatively easy.
        self.assertLessEqual(row["defconDifficulty"], 2)


class SeasonLiveTests(unittest.TestCase):
    def _ctx(self):
        players = {100: make_defender(100, team=1)}
        teams = {1: {"short_name": "AAA"}, 2: {"short_name": "BBB"}}
        fixtures = [
            {"id": 10, "event": 1, "team_h": 1, "team_a": 2},
            {"id": 11, "event": 2, "team_h": 2, "team_a": 1},
        ]
        events = [{"id": 1, "finished": True}, {"id": 2, "finished": False}]
        return make_ctx(players=players, teams=teams, events=events, fixtures=fixtures)

    def _live_response(self, fixture_id, minutes, starts, defcon=0,
                        extra_fixture_id=None):
        explain = [{"fixture": fixture_id, "stats": []}]
        if extra_fixture_id is not None:
            explain.append({"fixture": extra_fixture_id, "stats": []})
        return {"elements": [{
            "id": 100,
            "stats": {
                "minutes": minutes, "starts": starts,
                "total_points": 6, "defensive_contribution": defcon,
                "clean_sheets": 1, "goals_conceded": 0, "bonus": 0,
                "bps": 20, "yellow_cards": 0, "red_cards": 0,
                "expected_goals_conceded": "0.3",
                "expected_goal_involvements": "0.0",
            },
            "explain": explain,
        }]}

    def test_opponent_and_venue_join_via_fixture(self):
        ctx = self._ctx()
        responses = {
            1: self._live_response(10, minutes=90, starts=1),
            2: self._live_response(11, minutes=90, starts=1),
        }
        with mock.patch.object(scout.fplapi, "event_live",
                                side_effect=lambda gw, ttl=None: responses[gw]):
            live = scout.season_live(ctx, 2)
        matches = live[100]
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["opp"], "BBB")
        self.assertTrue(matches[0]["home"])
        self.assertEqual(matches[1]["opp"], "BBB")
        self.assertFalse(matches[1]["home"])

    def test_status_classification(self):
        ctx = self._ctx()
        cases = {
            1: self._live_response(10, minutes=90, starts=1),   # started
        }
        with mock.patch.object(scout.fplapi, "event_live",
                                side_effect=lambda gw, ttl=None: cases.get(gw, {"elements": []})):
            live = scout.season_live(ctx, 1)
        self.assertEqual(live[100][0]["status"], "started")

        cases = {1: self._live_response(10, minutes=15, starts=0)}
        with mock.patch.object(scout.fplapi, "event_live",
                                side_effect=lambda gw, ttl=None: cases[gw]):
            live = scout.season_live(ctx, 1)
        self.assertEqual(live[100][0]["status"], "subbedOn")

        cases = {1: self._live_response(10, minutes=0, starts=0)}
        with mock.patch.object(scout.fplapi, "event_live",
                                side_effect=lambda gw, ttl=None: cases[gw]):
            live = scout.season_live(ctx, 1)
        self.assertEqual(live[100][0]["status"], "unplayed")

    def test_double_gameweek_uses_only_first_fixture(self):
        # Documented DGW blindness (plan §1 / quality-audit L1): a second
        # `explain` entry must not be joined against, matching the rest of
        # the codebase's current behaviour rather than silently disagreeing
        # with it inside this one module.
        ctx = self._ctx()
        cases = {1: self._live_response(10, minutes=90, starts=1, extra_fixture_id=11)}
        with mock.patch.object(scout.fplapi, "event_live",
                                side_effect=lambda gw, ttl=None: cases[gw]):
            live = scout.season_live(ctx, 1)
        self.assertEqual(len(live[100]), 1)
        self.assertEqual(live[100][0]["opp"], "BBB")  # from fixture 10, not 11

    def test_finished_week_cached_longer_than_current_week(self):
        ctx = self._ctx()
        calls = []

        def fake_event_live(gw, ttl=None):
            calls.append((gw, ttl))
            return {"elements": []}

        with mock.patch.object(scout.fplapi, "event_live", side_effect=fake_event_live):
            scout.season_live(ctx, 2, ttl=555)
        self.assertIn((1, scout.FINISHED_LIVE_TTL), calls)  # gw1 is finished
        self.assertIn((2, 555), calls)                       # gw2 is not


class GreyscaleAccessibilityTests(unittest.TestCase):
    """Mechanical form of spec §1's acceptance test: "render each chart in
    greyscale; if it is still readable, it passes." """

    def test_percentile_scale_passes_greyscale(self):
        bgs = [bg for _, bg, _ in scout.PERCENTILE_SCALE]
        self.assertTrue(scout.greyscale_readable(bgs))

    def test_percentile_scale_luminance_is_monotonic(self):
        # A sequential scale has to *read* as sequential without colour:
        # each step strictly darker than the last, so "further down the
        # column is a bigger number" survives a greyscale render.
        lums = [scout.relative_luminance(bg) for _, bg, _ in scout.PERCENTILE_SCALE]
        self.assertEqual(lums, sorted(lums, reverse=True))

    def test_percentile_scale_text_contrast(self):
        # Every (bg, fg) pairing has to clear WCAG AA for body text. The
        # dark end of a single-hue ramp is exactly where a ramp designed
        # by eye tends to fail this.
        for _edge, bg, fg in scout.PERCENTILE_SCALE:
            lb, lf = scout.relative_luminance(bg), scout.relative_luminance(fg)
            hi, lo = max(lb, lf), min(lb, lf)
            self.assertGreaterEqual((hi + 0.05) / (lo + 0.05), 4.5, bg + " on " + fg)

    def test_percentile_tone_covers_the_whole_range(self):
        for pct in (0, 19.9, 20, 55, 80, 99.9, 100):
            bg, fg = scout.percentile_tone(pct)
            self.assertTrue(bg.startswith("#") and fg.startswith("#"))

    def test_ticker_scale_still_passes_greyscale(self):
        # The shipped rose-teal ramp this section deliberately reuses for
        # fixture difficulty (plan §2.5) - if this ever regresses, both the
        # existing ticker and this section's fixture rows lose the property
        # at once.
        import ticker
        bgs = [bg for _, bg, _ in ticker.SCALE]
        self.assertTrue(scout.greyscale_readable(bgs))

    def test_radius_mapping_spans_the_documented_range(self):
        self.assertEqual(scout.radius_for_percentile(0), 5.0)
        self.assertEqual(scout.radius_for_percentile(100), 22.0)
        self.assertGreater(scout.radius_for_percentile(75), scout.radius_for_percentile(25))

    def test_radius_mapping_clamps_out_of_range_input(self):
        self.assertEqual(scout.radius_for_percentile(-10), 5.0)
        self.assertEqual(scout.radius_for_percentile(150), 22.0)


class PositionConfigTests(unittest.TestCase):
    """Every lab is driven by its POSITIONS entry, and scout.js trusts the
    keys it is sent. A typo here is a blank column or a NaN axis in the
    browser, not an exception, so it is caught here instead."""

    PERCENTILE_KEYS = set(scout.METRICS) | {"solidity_pct"}
    FIXTURE_FIELDS = {"cleanSheetDifficulty", "defconDifficulty", "attackDifficulty"}

    def test_every_outfield_position_has_a_lab(self):
        self.assertEqual(set(scout.POSITIONS), {"DEF", "MID", "FWD"})

    def test_config_keys_are_real_metrics(self):
        for pos, cfg in scout.POSITIONS.items():
            with self.subTest(pos=pos):
                for key in cfg.metrics + cfg.zbars + cfg.card_tiles + [cfg.hero_y]:
                    self.assertIn(key, scout.METRICS)
                self.assertIn(cfg.size_metric, self.PERCENTILE_KEYS)
                for metric in cfg.archetypes.values():
                    self.assertIn(metric, self.PERCENTILE_KEYS)
                self.assertEqual(set(cfg.archetypes), set(cfg.archetype_labels))
                if cfg.hero_x != scout.HERO_X_DEFCON:
                    self.assertIn(cfg.hero_x, scout.METRICS)

    def test_fixture_config_names_real_difficulty_fields(self):
        for pos, cfg in scout.POSITIONS.items():
            with self.subTest(pos=pos):
                self.assertEqual(len(cfg.fixture_lists), 2)
                for fl in cfg.fixture_lists:
                    self.assertIn(fl["fx"], self.FIXTURE_FIELDS)
                for field_name, _ in cfg.ticker_rows:
                    self.assertIn(field_name, self.FIXTURE_FIELDS)

    def test_fixed_hero_axis_is_not_gated(self):
        # Only the DefCon axis swaps with sample size; an attacking lab's
        # x-axis is xG however little football has been played.
        rows = [{"minutes": 10}, {"minutes": 20}]
        self.assertEqual(scout.hero_x_key(rows, "xg90"), "xg90")
        self.assertEqual(scout.hero_x_key(rows), "defcon90")


class AttackingRowsTests(unittest.TestCase):
    def _ctx(self):
        mid = make_defender(1, team=10, web_name="Mid", minutes=270, starts=3)
        mid["element_type"] = 3
        mid.update({"expected_goals_per_90": 0.42, "expected_assists_per_90": 0.21,
                    "goals_scored": 2, "assists": 1})
        fixtures = [{"id": 1, "event": 1, "team_h": 10, "team_a": 20,
                     "finished": True, "finished_provisional": True, "started": True}]
        return make_ctx(players={1: mid},
                        teams={10: {"short_name": "AAA"}, 20: {"short_name": "BBB"}},
                        fixtures=fixtures)

    def test_midfielder_row_carries_attacking_fields(self):
        row = scout.raw_rows(self._ctx(), "MID", {})[0]
        self.assertEqual((row["xg90"], row["xa90"]), (0.42, 0.21))
        self.assertEqual((row["goals"], row["assists"]), (2, 1))

    def test_pool_payload_carries_the_position_config(self):
        data = scout.pool(self._ctx(), "MID", {}, proj={})
        self.assertEqual(data["heroX"], "xg90")
        self.assertEqual(data["sizeMetric"], "defcon90")
        self.assertIn("finisher", data["archetypeLabels"])
        self.assertEqual(len(data["rows"]), 1)


class AttackDifficultyTests(unittest.TestCase):
    def test_attack_difficulty_follows_the_clubs_own_xg(self):
        proj = {
            ("AAA", 4): {"cs": 30.0, "g": 2.3, "opp": "BBB", "ven": "H"},
            ("AAA", 5): {"cs": 30.0, "g": 0.6, "opp": "CCC", "ven": "A"},
            ("BBB", 4): {"cs": 30.0, "g": 1.0, "opp": "AAA", "ven": "A"},
            ("CCC", 5): {"cs": 30.0, "g": 1.0, "opp": "AAA", "ven": "H"},
        }
        easy, hard = scout.fixture_rows("AAA", proj, start_gw=4, weeks=2)
        self.assertEqual(easy["attackDifficulty"], 1)
        self.assertEqual(hard["attackDifficulty"], 5)


class LeaderGroupsTests(unittest.TestCase):
    def _row(self, pid, xg90, xa90=0.1, minutes=300, bps90=20.0):
        return {
            "id": pid, "webName": f"P{pid}", "teamShort": "AAA",
            "minutes": minutes, "xg90": xg90, "xa90": xa90, "xgi90": xg90 + xa90,
            "xgc90": 1.0, "goals": 1, "assists": 0, "bonus": 2, "bps90": bps90,
            "defcon90": 5.0, "defconHitRate": 0.0, "defconHits": 0,
            "defconHitN": 3, "startRate": 1.0, "starts": 3, "teamMatches": 3,
            "minutesPerStart": 90.0,
        }

    def test_each_position_gets_four_boards(self):
        rows = [self._row(i, xg90=i / 10) for i in range(1, 8)]
        for pos, titles in {
            "DEF": ["Defensive contribution", "Threat going forward",
                    "Concede the least", "Nailed on"],
            "MID": ["Goal threat", "Chance creation",
                    "Defensive contribution", "Nailed on"],
            "FWD": ["Goal threat", "Chance creation", "Bonus magnet", "Nailed on"],
        }.items():
            with self.subTest(pos=pos):
                groups = scout.leader_groups(rows, pos=pos)
                self.assertEqual([g["title"] for g in groups], titles)

    def test_goal_threat_ranks_on_xg_and_drops_cameos(self):
        rows = [self._row(1, xg90=0.3), self._row(2, xg90=0.9),
                self._row(3, xg90=2.0, minutes=40)]
        goals = scout.leader_groups(rows, pos="FWD", owned_ids={1})[0]
        self.assertEqual([r[0] for r in goals["rows"]], ["P2", "P1"])
        self.assertEqual(goals["rows"][0][2], "0.90 · 1G")
        self.assertTrue(goals["rows"][1][3])  # owned flag rides along


if __name__ == "__main__":
    unittest.main()
