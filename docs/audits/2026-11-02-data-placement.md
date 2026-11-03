# Data placement audit (2 November 2026)

Read-only analysis for the dedupe pass. Nothing in the code was changed.

**Source.** Cached build `python cli.py dashboard`-equivalent (`dashboard.build` at `ttl=10**9`, price history redirected to scratch) written to `.cache/ui/audit.html`, GW9 snapshot of 02 Nov 2026 13:47 UTC, every source OK. Visible text was extracted per tab and checked against the card modules and JS. Figures quoted below are from that build.

**Rule applied.** Squad = what to do this week. Planning = the next weeks. League = rivals. Scout = finding players. Per-player detail goes to the player profile (the merged squad dialog and Scout card). Figures, not sentences. One home per stat.

**Summary**
- **60 items** across the page, four tabs and two dialogs (plus 6 chapter headings). **18 duplicate groups.** The worst: "who to buy" is shown in **9 places** (G1), fixtures in **10 cards** plus a one-line "next" in five more (G4), your squad's season stats in **9** (G3), and there are two scatters and two leaderboards (G6, G7).
- **Planning carries three tabs' worth of content.** Its "This week" chapter (odds, highest XI, knee-jerk) and the captaincy radar belong to Squad or nowhere. Its "The wider market" chapter (leaders, value scatter, elite) belongs to Scout. After the moves it is plan, deck, chips, fixture runs, price watch.
- **The Squad findings column is mostly repeats.** 11 of its 12 cards repeat the squad table, the player dialog, the Up next panel or a Planning card. Only Predicted line-ups is a this-week decision.
- **Same label, different number** (section 3). "Your XI next week" reads 62.7, 56.1, 48.2 and 70.9 in four cards. The Wildcard's +70.1 and the plan's +45.5 cover the same GW10–17 window. These are scorer issues, not placement, but a dedupe that keeps the wrong copy will hide them.
- **86 explainer lines** (section 4): 53 visible, 33 already behind an "i" or a collapsed card. Recommendation: cut 50, turn 22 into figures with a 1–3 word label, keep 12 behind the "i", keep About collapsed, and keep the one mandatory caveat line visible.

---

## 1. Inventory

Columns: **#** · **Item** (as it reads on the page) · **Shows** (this build) · **Source** · **Also at** (same or near-same information elsewhere; IDs refer to rows in this section). *Hidden* = behind a tab, toggle, "i" or collapsed card.

### Page-wide (outside the tab panels)

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| X1 | Side rail "GW 9" | current gameweek | [dashboard.py:433](../../dashboard.py:433) | X2, S1 label |
| X2 | Top bar stamp | "Gameweek 9 · 02 Nov 2026, 13:47 UTC" | [dashboard.py:439](../../dashboard.py:439) | X1, X5 |
| X3 | Intro: manager line + team name h1 | "Jonno Millar's Fantasy Premier League squad", "SAVIN KLUIVERT RAYAN" | [dashboard.py:443](../../dashboard.py:443) | — |
| X4 | About & methods (collapsed) | 3 paragraphs + link | [dashboard.py:451](../../dashboard.py:451)–456 | README |
| X5 | Status line | "Snapshot: …" (JS age) + published-squad and no-double-gameweek caveat | [dashboard.py:462](../../dashboard.py:462)–464 | X2 (time), P1 lab, S7 strips (caveat) |
| X6 | Source warning (only on failure) | missing sources | [dashboard.py:229](../../dashboard.py:229) | — |
| X7 | Footer link | "source and phone alerts" | [dashboard.py:582](../../dashboard.py:582) | X3 "Source code" link |

### Squad tab (reading order as built)

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| S1 | Score card | GW9 **34** pts, 42 average, "8 below", verdict sentence ("1 still to play — Hall. You need 8 more…") | [dashboard.py:328](../../dashboard.py:328), `week_verdict` [:149](../../dashboard.py:149) | L5 GW column, S7 Last-GW pitch |
| S2 | Season tile | **600**, rank 499,114, ▼333k | [dashboard.py:335](../../dashboard.py:335) | L1 shows **598** for the same total (section 3) |
| S3 | League tile | **5th** of 8, ▼3 places | [dashboard.py:338](../../dashboard.py:338) | L1 (place, of 8), L5 rank column |
| S4 | Up next panel | **62.7** xP GW10 with captain (65.7 with transfers); "2 to check": Cherki predicted bench, João Pedro injured 0%; bank 2.1m, sells for 98.1m | [dashboard.py:341](../../dashboard.py:341)–349 | S10 line-ups, S19 Availability, S7 Breakdown (56.1 = 62.7 − captain), P10 Best XI "48.2", P1 GW10 squad "70.9" |
| S5 | The next move | "Make 2 transfers", **+30.4** over 8 GW; João Pedro → Isak, Cherki → Tavernier, opponent crest, form sentence | [dashboard.py:351](../../dashboard.py:351)–397, reason [next_action.py:10](../../next_action.py:10) | P1 GW10 stage (same moves, same +30.4), P2 deck (Isak card), P5 Buy (Isak, Tavernier), P5 Sell (Cherki, João Pedro), S7 preview toggle + IN badges, S7 mobile line |
| S6 | Captain card | Calafiori v Hull (H), **6.6** "projected, before doubling" | [dashboard.py:400](../../dashboard.py:400)–416 | P4 radar legend "6.6 pts proj", S7 pitch "C", P1 stage squad "C" |
| S7 | Starting XI card | 3 views: Season (pts / per game / xGI per card), Next GW (xP, opponent, CS% or team xG per card; Breakdown panel 56.1; Preview transfers switch "+3.0 xP"), Last GW; strips "Published squad" ×2, "Current squad · 5–3–2" | [dashboard.py:467](../../dashboard.py:467)–503, [cards_squad.py:52](../../cards_squad.py:52), [:137](../../cards_squad.py:137), [components.py:47](../../components.py:47) | S8 table (pts, xGI, xP), S5 moves, S6 captain, D1 dialog, P9 odds (CS%), X5 caveat |
| S8 | Squad detail (collapsed table) | 15 rows × Pos, Club, Price, Own, Min, Pts, xG, xA, xGI, xGI/90, DC/90, xP, Starting, Next 3 | [cards_squad.py:258](../../cards_squad.py:258) | S7, S10–S21, D1 (all per-player), P8 ticker (Next 3) |
| S9 | Chapter "What the numbers say" | heading only | [dashboard.py:515](../../dashboard.py:515) | — |
| S10 | Predicted line-ups | ring **10 of 15**; Full / XI / Bench tabs; "Not predicted to start": Cherki, João Pedro, Dubravka, Hughes; "No side yet": Hall + next-3 pills | [cards_squad.py:399](../../cards_squad.py:399) | S4 "2 to check", S8 Starting, S19, S20, D1 tag, S7 pips |
| S11 | Attacking returns | G+A per player (Groß 9, Haaland 9 …) | [cards_squad.py:517](../../cards_squad.py:517) | D1 goals/assists tiles, S8 xG/xA |
| S12 | Big chances created | Groß 7 "of 24 chances" … | [cards_squad.py:547](../../cards_squad.py:547) | P12 leaders (same metric, all players), D1 Opta tiles |
| S13 | Fixture swings | Hard run: FUL "FDR 3.7" + 3 rating pills | [cards_squad.py:590](../../cards_squad.py:590) | P7, P8, C3, S8 Next 3, D1 fixtures |
| S14 | Goals against expected goals | dumbbell, "1 v 3.97" … | [cards_squad.py:709](../../cards_squad.py:709), [components.py:114](../../components.py:114) | D1 "Goals 5, 3.97 expected" |
| S15 | Defensive contribution | Diop "8.9 / 10", "5 of 9" … | [components.py:173](../../components.py:173) | S8 DC/90, D1 DefCon tile, P12, C1 |
| S16 | Set pieces | Penalties / Free kicks / Corners takers | [components.py:255](../../components.py:255) | D1 set pieces, P2 deck duty icons, L9 duty badges, D2 flags |
| S17 | Price movement | last 7 days: Rogers 7.9 → 8.1 … | [components.py:307](../../components.py:307) | P13 price watch (+ "yours" tag and banner), D1 season change |
| S18 | Availability | João Pedro INJURED 0% + news | [analysis.py:645](../../analysis.py:645) | S4, S10, D1 alert |
| S19 | Rotation risk | Hughes started 0 of 4, 10 min a game | [analysis.py:720](../../analysis.py:720) | S10 (Hughes "not predicted"), D1 minutes tile |
| S20 | Big chances missed | "1 missed from 9 shots (2 on target)" … | [analysis.py:784](../../analysis.py:784) | D1 Opta tiles |
| S21 | How they did last season (collapsed) | 2 players | [cards_squad.py:798](../../cards_squad.py:798), [analysis.py:827](../../analysis.py:827) | D1 "Last season" block |

### Planning tab

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| P0 | Chapter "Your moves" | heading | [dashboard.py:520](../../dashboard.py:520) | — |
| P1 | Transfer plan | lab "The plan · GW10–17, from the last published squad"; "8 WEEKS, MAPPED."; 3 FT; 8 week tiles; stage per week (GW10 "TWO IN, NO HIT", +30.4 xP to GW17, moves with "Projects 45.8 to GW10–17, João Pedro 18.2", squad pitch per week "70.9 xP"); summary **+45.5**, 535 over window, cheap slots Dubravka, Hughes | [cards_plan.py:268](../../cards_plan.py:268) | S5 (GW10 moves), P2, P6 (chips), P16 method |
| P2 | Deck "NINE MORE WORTH A LOOK." | 9 options, pairs and singles, gain over next 5 GW; includes the plan's own Isak and Rudoni moves ("In the transfer plan for GW10") and Van Hecke (single and pair) | [components.py:538](../../components.py:538) | S5, P1, P5 (same names and figures: Manzambi 34.8 / +19.7, Isak 33.9 / +18.6), P11 knee-jerk (Van Hecke) |
| P4 | Captaincy decision matrix | radar, 3 candidates (Calafiori 6.6, Konsa 6.5, Mbeumo 6.0) | [cards_planning.py:922](../../cards_planning.py:922), [captaincy.js](../../captaincy.js) | S6 |
| P5 | Buy, sell, keep, avoid | Buy: Manzambi, Palmer, Isak, Tavernier (5 GW totals); Sell: Cherki, João Pedro, Hughes, Diop (+ replacement gain); Keep: 4; Avoid: none | [cards_planning.py:882](../../cards_planning.py:882) | P2 (same scorer, same numbers), S5 |
| P6 | Chip planner | FH GW11 "67.9 v 44.3", TC used GW7, BB "Hold: GW18 +14.3", WC GW10–17 "+70.1" Strong | [cards_planning.py:563](../../cards_planning.py:563) | P1 tiles/summary (chips), P16 paragraph 2, P10 (FH is "budgeted version"), L8 |
| P6b | Wildcard rebuild (collapsed) | xP 444.3 → 514.4, fixture rating, xGI, form; Now / Proposed pitches | [cards_planning.py:423](../../cards_planning.py:423) | P6 Wildcard card |
| P7 | Best fixture runs (night band) | next 6 GW, every club; "Expected output" / "FPL difficulty" tabs; best 3 and worst 3 | [ticker.py:426](../../ticker.py:426) | P8, C3, S13 |
| P8 | Fixture outlook | 20-club ticker, 0–10 rating, Games selector, Target toggle | [ticker.py:287](../../ticker.py:287), [ticker.js](../../ticker.js) | P7, C3, S8 Next 3, S13 |
| P8a | Chapter "This week" | heading | [dashboard.py:531](../../dashboard.py:531) | — |
| P9 | What the odds mean for gameweek 10 | best attack 1.91 (Mbeumo), likeliest CS 60% (Calafiori, Raya), least likely 19% (Hall) | [ticker.py:519](../../ticker.py:519) | S7 Next-GW cards (CS 60%, team xG per player), D1 xP block |
| P10 | Highest predicted points XI | 69.3, 4 of 11 yours, costs 87.6m, "Your eleven projects 48.2" | [cards_planning.py:699](../../cards_planning.py:699) | P6 Free Hit (budgeted version), S4 (62.7) |
| P11 | The knee-jerk | Van Hecke 15 in GW9, price, owned, bought, next 5.0 / 31.5, verdict sentence | [cards_planning.py:785](../../cards_planning.py:785) | P2 (Van Hecke cards), L7 Scoring against you (Van Hecke 15) |
| P11a | Chapter "The wider market" | heading | [dashboard.py:536](../../dashboard.py:536) | — |
| P12 | Season leaders | 6 boards, all players: xG, xA, xGI, big chances, fewest xGC, DefCon | [cards_planning.py:224](../../cards_planning.py:224), [components.py:434](../../components.py:434) | C1 (per-position, per 90), S12, S15 |
| P13 | Price watch | Rising / Falling, progress %, forecast, net transfers; banner "Gonzalo … losing value" | [cards_planning.py:50](../../cards_planning.py:50) | S17, D2 "transfers this GW" |
| P14 | Value scatter | all players 60+ min, pick X/Y from 6 measures, position chips | [cards_planning.py:93](../../cards_planning.py:93), [scatter.js](../../scatter.js) | C2 Scout scatter |
| P15 | What proven managers own | "needs ~10 gameweeks" sentence only (insufficient) | [cards_planning.py:160](../../cards_planning.py:160) | — |
| P16 | How the suggested action is chosen (collapsed) | 2 paragraphs of plan and chip rules | [dashboard.py:541](../../dashboard.py:541)–544 | P1 "i" note (same rules), P6 |

### League tab

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| L1 | Place card + gaps | **5th** of 8, **598** points; To the top 46 behind Change Name; Next place up 5 | `league_hero` [dashboard.py:238](../../dashboard.py:238) | S3, S2 (600) |
| L2 | Standings card "Big Dogs Only" | lede "2 of 8 played Free Hit in GW9. You did not…"; table #, Team, Total, GW (Top/Low tags), Captain, Chip, Bench, Hits, XI xGI | [cards_league.py:639](../../cards_league.py:639), [:682](../../cards_league.py:682) | L8 (chips), S1 (GW), S3 |
| L3 | League position over time | line chart, Position / Points | [cards_league.py:587](../../cards_league.py:587), [leaguechart.js](../../leaguechart.js) | L1 |
| L3a | Chapter "What the league owns" | heading | [dashboard.py:560](../../dashboard.py:560) | — |
| L4 | League template | pitch, N/8 and % per slot, "Only 6 of 11 …" | [cards_league.py:169](../../cards_league.py:169) | L4b, L4c (same counts) |
| L4b | The league has these, you do not | De Cuyper 4/8, Tavernier 4/8, N.Jackson 5/8 | [cards_league.py:763](../../cards_league.py:763) | L4, L7 (same three names), P5 Buy (Tavernier) |
| L4c | Who owns whom (carousel) | ring per player owned by 2+, "6 captained him", "You own him"; 18 single-owner hidden | [cards_league.py:63](../../cards_league.py:63) | L4 counts, L6 |
| L6 | Your differentials | Gonzalo, Diop, Hughes …: points, xGI, owned all FPL | [cards_league.py:313](../../cards_league.py:313) | D1 (same stats per player) |
| L9 | Differential watchlist | 6 unowned-in-league players, 5-week score, next fixture, owned % | [cards_league.py:275](../../cards_league.py:275) | P2/P5 (same scorer, "scored the same way as every transfer suggestion") |
| L6a | Chapter "How they are playing it" | heading | [dashboard.py:566](../../dashboard.py:566) | — |
| L7 | Scoring against you | This week / Last 3 weeks; Van Hecke 15 "started by 3 of 7" … | [cards_league.py:507](../../cards_league.py:507) | P11, L4b |
| L8 | Chips used | table, every manager × 4 chips | [cards_league.py:819](../../cards_league.py:819) | L2 Chip column + lede (this week only), P6 |

### Scout tab (per position; DEF shown first)

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| C0 | Position switch | DEF 159, MID 218, FWD 52 | [cards_scout.py:118](../../cards_scout.py:118) | — |
| C1 | "Worth a look" → Leaders | 4 boards per position (DEF: DefCon, xGI/90, xGC/90, Nailed on); visible lede "9 matches in, at most…" | [cards_scout.py:140](../../cards_scout.py:140), `scout.leader_groups` [scout.py:767](../../scout.py:767) | P12 |
| C3 | "Fixture runs" → Kindest and toughest runs | per-position lists (CS / DefCon / goals), horizon 1–8 | [cards_scout.py:54](../../cards_scout.py:54) | P7, P8, S13 |
| C2 | "Explore the pool" → All defenders | filters, scatter (bubble = position metric), heatmap table with xP column | [cards_scout.py:167](../../cards_scout.py:167)–193, [scout.js](../../scout.js) | P14 |
| C4 | Shortlist (after ticking 2+) | z-score bars + fixture ticker for picked players | [cards_scout.py:196](../../cards_scout.py:196) | P8 (fixtures) |

### Player dialogs (the merge input)

| # | Item | Shows | Source | Also at |
|---|---|---|---|---|
| D1 | Squad player dialog (`dialog.pv`) | header (photo, pos, club, price, season ±, owned %, Predicted XI tag); alert; **Expected points, next match** (total, opponent, CS%, part bar, 9 part rows, sentence); **This season** tiles (Points/bonus, Minutes/starts, Goals/xG, Assists/xA, xGI90/xGI, DefCon90, Opta tiles); Set pieces; Next fixtures ×6 (shaded); Match log table + points sparkline; Last season sentence | [playerview.js](../../playerview.js), payload [cards_squad.py:825](../../cards_squad.py:825) | S7, S8, S10–S21, L6 |
| D2 | Scout player card (`dialog.scoutpv`) | header (name, club, price, pos, archetype badges); flags (corners, free kicks, pens, availability, transfers this GW, owned %); **This season**: 5 percentile bullets with counts; **Match by match** strip (G/A/DefCon marks, key); **Last 10 gameweeks**: 3 sparklines | `renderCard` [scout.js:402](../../scout.js:402) | D1, C2 heatmap row |

Field overlap for the merged profile:

| Field | D1 squad | D2 scout | Keep in profile as |
|---|---|---|---|
| Identity, price, owned % | yes | yes | header, once |
| Season price change | yes | — | header figure |
| Transfers this GW | — | yes | header figure |
| Predicted XI / availability | tag + alert | flag | one status icon + news line |
| Set pieces | chips | flags | icons in header |
| Archetype | — | badges | one word under name |
| Next-match xP + parts | yes | — | big number + opponent crest + CS% + team xG; sentence behind "i" |
| Season stats | raw tiles | percentile bullets | raw figure + percentile bar (D2's form) |
| Next fixtures | 6 shaded cells | — (shortlist only) | keep D1's six cells |
| Per-match history | log table + pts sparkline | match strip + 3 sparklines | D2's strip; D1's table behind an expand; drop both sparkline sets |
| Last season | sentence | — | one figure line |

---

## 2. Duplicate groups and the single home

| G | What | Appears in | Single home | Remove elsewhere | Why |
|---|---|---|---|---|---|
| G1 | **Who to buy / sell** | S5, S7 preview, S7 mobile line, P1, P2, P5, P11, P10, L9 | This week's move: **S5**. Later weeks: **P1**. Alternatives: **P2** | P5 card (Buy = P2 singles, Sell = P2 out legs, same scorer and figures; Keep is a non-list; Avoid empty). The plan's own moves from P2. P11 card, folded into its P2 card as a "GW9: 15 pts" tag. P10 card. S7 mobile line (S5 is on screen). | One answer per horizon. Today the same Isak move appears in five cards with three different figures (+30.4, +18.6, 33.9). |
| G2 | **Captain** | S6, P4, S7, P1 stage | **S6** | P4 moves out of Planning. It becomes a click-to-reveal under S6, or is cut. | Captaincy is this week's decision. The radar repeats S6's 6.6. |
| G3 | **Your squad's season stats** | S7 Season view, S8, S11, S12, S14, S15, S20, S21, D1 | Comparison across the 15: **S8** (collapsed table). Per player: **profile** | S11, S12, S14, S15, S20, S21 cards. Their figures are S8 columns or D1 tiles. | They are season reading, not this week's action. S8 already sorts the same numbers. |
| G4 | **Fixtures** | S7 (next opponent), S8 Next 3, S10 pills, S13, P7, P8, P9, C3, C4, D1, P1/P2/P5/L9/P11 one-line "next" | Club runs: **P7** (band) with P8 as its "All 20 clubs" expand. Per player: **profile** next 6. This week: S7 card shows the opponent only | S13 card. S10 pills. S8 Next 3 column. C3 card (position lens becomes a P7 tab). P8 as a separate card. | Eleven fixture views on two scales (0–10 and FPL 1–5) in opposite directions. Several explainers exist only to say which way round a scale runs (section 4). |
| G5 | **Team news** | S4 "2 to check", S10, S18, S19, S8 Starting, S7 pips, D1 | **S10** (ring + named exceptions); S4 keeps names only | S18 (João Pedro is S4 and S10). S19 (Hughes is in S10's "not predicted"). | One availability card. Three cards name the same four players. |
| G6 | **Scatter** | P14, C2 | **C2** (Scout) | P14 card. If price / points-per-£m / ownership axes matter, add them as axis options on C2. | Jonno's own example: nobody scans both. C2 has filters, the heatmap and the shortlist. |
| G7 | **Leaderboards** | P12, C1 | **C1** (Scout) | P12 card. Big chances created (its only metric missing from C1) joins MID/FWD boards or the profile. | Finding players is Scout. P12 is season totals, so it ranks minutes as much as quality. |
| G8 | **Chips** | S5 "Chips" link, P1 tiles + chip line, P6, P6b, P16 para 2, L2 Chip column + lede, L8 | **P6** for your chips, with P1 tiles for planned weeks. **L8** for rivals' chips | P16 para 2. L2 lede (the Chip column holds it). | One card per chip owner. |
| G9 | **Plan rules** | P1 "i" note, P16, P2 lede ("The plan has already weighed them…") | **P1 "i"** | P16 card (repoint S5 "How it's chosen" to P1's "i"). P2 lede. | The same 3-point margin, hit and enabler rules are written twice. |
| G10 | **League place** | S3, L1, L2 rank | **L1** | S3 tile. Season tile S2 keeps the overall rank. | League = rivals. S3 is also the only place 5th is shown with "▼3", which L2's rank column already shows. |
| G11 | **Ownership in your league** | L4, L4b, L4c, L6, L7 | **L4** (template, with "you own" marked) + **L6** (only you) | L4c carousel (same N/8 counts as L4). L4b list (same three names as L7). | Three views of one ownership table. Another session owns League differentials; hand this group to it. |
| G12 | **Prices** | S17, P13, D1 season change, D2 transfers, P11 bought | **P13** for the market; **profile** for one player | S17 card. P13 banner (the "yours" tag on the row says it). | S17 is the past 7 days with no action attached. |
| G13 | **Set pieces** | S16, D1, D2, P2 icons, L9 badges | **Profile** header icons; icons stay on faces in P2/L9 | S16 card | Per-player detail. |
| G14 | **DefCon** | S8 DC/90, S15, D1, P12, C1, C2 | **C1/C2** market, **profile** player | S15 (with G3), P12 (with G7) | Same metric four ways. |
| G15 | **Last gameweek** | S1, S7 Last-GW view, P11, L2 GW column, L7 This week | **S1** + S7 view for you; **L2/L7** for rivals | P11 (with G1) | Last week's haul has no place in "next weeks". |
| G16 | **Odds and this week's market** | P9, S7 Next-GW cards (CS%, team xG), D1 xP block | **S7 cards** | P9 card. "Market v model" can sit in the profile's "i". | P9's three facts are three pitch cards' own numbers. |
| G17 | **Published-squad caveat and time** | X5, X2, P1 lab suffix, S7 "Published squad" ×2, X4 | **X5** | X2 date (keep "Gameweek 9"), P1 "from the last published squad", S7 strips | The caveat stays visible once (design.md rule). |
| G18 | **Player detail dialogs** | D1, D2 | **Profile** (field table above) | Two dialogs and two JSON payloads | Already decided; another session is building it. Faces that don't open a profile today: plan move cut-outs, deck, L4 (except your own), L6, L7, L9, P5, P10, P12, C1, captaincy legend. D1 has payloads for your 15 only. |

---

## 3. Numbers that disagree (found while auditing; not placement)

| What | Values | Where | Note |
|---|---|---|---|
| "Your XI, next week" | 62.7 (with captain), 56.1 (Breakdown, no captain), **48.2**, 70.9 / 65.7 | S4, S7, P10, P1 GW10 squad | 62.7 = 56.1 + captain 6.6, so those two agree. 48.2 is the chips scorer. 70.9 is the plan scorer after transfers. Three scorers, one label. |
| GW10–17 gain | Wildcard **+70.1** v plan **+45.5** | P6, P6b, P1 | Already in HANDOFF "Seen, not fixed". Still live. |
| Season total | **600** v **598** | S2, L1 | `entry_history.total_points` v standings total. Cause not checked. |
| Isak's projection | 45.8 to GW17 (plan) v 33.9 over 5 GW (deck, Buy) | P1, P2, P5 | Different horizons on adjacent cards, no visible horizon change. |
| Plan rule breach | stage summary "Squad for GW10 · 70.9 xP" | P1 | HANDOFF rule: "Plan shows transfers and chips, not weekly team xP". |
| Van Hecke starts | "started by 3 of 7" this week, "2 of 7" over 3 weeks | L7 | Possibly counts different rival sets; not checked. |
| Scout DEF leader | Costinha "8.5 (1/1)" ranks first on hit rate over Richards "11.7 (7/9)" | C1 | A 1-start sample tops the board despite the "180 minutes" floor. |
| Dead code | `ticker.market_card` has no caller | [ticker.py:681](../../ticker.py:681) | Delete in the dedupe pass. |

---

## 4. Explainer and help sentences

Default **cut**. **i** = keep behind `components.info_btn()` as one short line. **keep** = must stay visible. **figure** = replace the sentence with numbers and a 1–3 word label. Rows marked *(card goes)* disappear with a card removed in section 2.

### Visible on the page (53)

| file:line | Text (start) | Item | Verdict |
|---|---|---|---|
| [dashboard.py:463](../../dashboard.py:463) | "Snapshot: … Advice uses your last published squad and bank… Double gameweeks are not planned." | X5 | **keep** (the one home of two required caveats) |
| [dashboard.py:300](../../dashboard.py:300), [:149](../../dashboard.py:149) | "1 still to play — Hall. You need 8 more to reach this week's 42 average." | S1 | figure: "1 to play · Hall" (the "8 below" chip already says the gap) |
| [dashboard.py:344](../../dashboard.py:344) | "projected points, GW10, with captain" | S4 | figure: "xP · with C" |
| [dashboard.py:347](../../dashboard.py:347) | "in the bank, squad sells for 98.1m" | S4 | figure: "bank · sells 98.1m" |
| [dashboard.py:321](../../dashboard.py:321) | "Nobody in the eleven is flagged." | S4 | figure: icon + "0 flagged" |
| [dashboard.py:377](../../dashboard.py:377), [next_action.py:17](../../next_action.py:17)–33 | "Isak has been returning more FPL points recently (form 5.0 versus João Pedro's 3.5)." | S5 | figure: "form 5.0 v 3.5" (or xGI/90 a v b) |
| [dashboard.py:384](../../dashboard.py:384) | "over 8 gameweeks, after hits" | S5 | figure: "xP · GW10–17" |
| [dashboard.py:415](../../dashboard.py:415) | "projected, before doubling" | S6 | figure: "xP" |
| [dashboard.py:490](../../dashboard.py:490)–491 | "Published squad" ×2 | S7 | cut |
| [cards_squad.py:460](../../cards_squad.py:460) | "Every one of them is named in a published side. Nothing to decide here." | S10 | figure: "All named" |
| [cards_squad.py:818](../../cards_squad.py:818) | "2 players · open for the full-season comparison" | S21 | cut *(card goes)* |
| [components.py:165](../../components.py:165) | "Scored / Expected" legend | S14 | cut *(card goes)* |
| [cards_plan.py:326](../../cards_plan.py:326) | "The plan · GW10–17, from the last published squad" | P1 | cut the "from the last published squad" suffix |
| [cards_plan.py:160](../../cards_plan.py:160)–162 | "CRY (A) in GW10. Projects 45.8 to GW10–17, João Pedro 18.2." | P1 | figure: crest + "45.8 v 18.2" |
| [cards_plan.py:104](../../cards_plan.py:104)–136 | "Restructure with … the cheap slot moves from…", "Worth the hit: …", "Waits out GW… where he projects…" | P1 | figure: tags "restructure", "hit: ruled out", "waits GW11–12" |
| [cards_plan.py:249](../../cards_plan.py:249) | "No move clears the bar this week. Save the free transfer: 2 free transfers next week." | P1 | cut (the stage-facts line above says "Roll · 2 free transfers next week") |
| [cards_plan.py:286](../../cards_plan.py:286)–287 | "points against making no transfers, after hits" | P1 | figure: "xP v no moves" |
| [cards_plan.py:337](../../cards_plan.py:337) | "projected over the window" | P1 | figure: "xP" |
| [components.py:633](../../components.py:633) | "Ranked on the next five gameweeks if made now. The plan has already weighed them…" | P2 | cut |
| [components.py:580](../../components.py:580) | "His 34.8 against Cherki's 8.7." | P2 | figure: "34.8 v 8.7" |
| [planner.py:700](../../planner.py:700)–705 | "In the transfer plan for GW10." / "The transfer plan sells Cherki differently: GW10, for Tavernier." | P2 | cut (plan moves leave the deck; the other becomes a "plan: Tavernier" tag) |
| [components.py:582](../../components.py:582), [:604](../../components.py:604) | "to your XI, next five weeks" | P2 | figure: "xP · 5 GW" (or the plan horizon, decision 4) |
| [cards_planning.py:966](../../cards_planning.py:966) | "Hover a shape or a dot for its value." | P4 | cut |
| [cards_planning.py:875](../../cards_planning.py:875)–878 | four column rules ("Not yours, reachable, projects highest." …) | P5 | cut *(card goes)* |
| [cards_planning.py:601](../../cards_planning.py:601) | "Suggested XI projects 67.9 pts against your XI's 44.3 that week." | P6 | figure: "67.9 v 44.3" |
| [cards_planning.py:625](../../cards_planning.py:625) | "The transfer plan keeps it past GW17: its best projected week is GW18, worth 14.3 more…" | P6 | figure: "GW18 · +14.3" |
| [cards_planning.py:633](../../cards_planning.py:633), [:641](../../cards_planning.py:641), [:612](../../cards_planning.py:612) | BB / TC reason sentences (not shown this build) | P6 | figure, same pattern |
| [cards_planning.py:652](../../cards_planning.py:652) | "70.1 pts of upside available over the window." | P6 | figure: "+70.1" |
| [ticker.py:492](../../ticker.py:492)–496 | "Attack and defence combined, out of ten, in absolute terms…" / "FPL's own 1-5 rating, from the opponent alone. Lower is easier." | P7 | cut; one line behind **i** ("0–10 higher is better; FPL 1–5 lower is easier") |
| [ticker.py:401](../../ticker.py:401) | "Rated out of ten… higher is better… CAPITALS are home, lower case away." | P8 | **i** (merge with P7's line) |
| [ticker.py:586](../../ticker.py:586) | odds tiles' unit words "goals priced", "quoted" | P9 | cut *(card goes)* |
| [cards_planning.py:775](../../cards_planning.py:775)–779 | "4 of 11 already yours", "Costs 87.6m … not a squad you can build", "Your eleven projects 48.2 … Read it as where you are behind, not as a target." | P10 | cut *(card goes)* |
| [cards_planning.py:857](../../cards_planning.py:857), [:868](../../cards_planning.py:868), [:819](../../cards_planning.py:819) | "You did not own Van Hecke, and he scored", verdict, "That is close enough to be noise…" | P11 | cut *(card goes; tag on the deck card)* |
| [cards_planning.py:306](../../cards_planning.py:306), [:316](../../cards_planning.py:316), [:320](../../cards_planning.py:320) | leaders notes ("The big figure is big chances…", "xGC totalled this season… Scout ranks the same idea per 90", "Tackles, recoveries…") | P12 | cut *(card goes)* |
| [cards_planning.py:76](../../cards_planning.py:76) | "Both figures are progress towards a price change, which fires at 100%…" | P13 | **i**, one line: "100% = price change; small figure = forecast" |
| [cards_planning.py:60](../../cards_planning.py:60), [:68](../../cards_planning.py:68) | "Gonzalo in your squad is losing value. Selling after the drop costs you the difference." | P13 | cut (row tag "yours" carries it) |
| [cards_planning.py:151](../../cards_planning.py:151)–152 | "Hover or click any dot…", legend | P14 | cut *(card goes)* |
| [cards_planning.py:168](../../cards_planning.py:168) | "Elite ownership needs ~10 gameweeks…" | P15 | cut: render nothing while insufficient |
| [cards_league.py:677](../../cards_league.py:677) | "2 of 8 played Free Hit in GW9. You did not, so your gameweek score is being compared…" | L2 | cut (Chip column) |
| [cards_league.py:746](../../cards_league.py:746) | "XI xGI spans just … Read it again once the season has a few more weeks in it." (conditional) | L2 | cut |
| [cards_league.py:220](../../cards_league.py:220)–221 | "Only 6 of 11 are held by more than half the league. This is always a full eleven…" | L4 | figure: "6 of 11 majority" |
| [cards_league.py:104](../../cards_league.py:104)–109 | "Share of the 8 managers in this league… Owned by only one manager: 18 more, not shown." | L4c | cut *(card goes)* |
| [cards_league.py:358](../../cards_league.py:358)–360 | "Nobody else in your league owns them. The percentage is all of FPL — the two answer different questions…" | L6 | cut (column label "Owned, all FPL" says it) |
| [cards_league.py:303](../../cards_league.py:303) | "Nobody in your league owns these." | L9 | cut (the title says differential) |
| [cards_league.py:528](../../cards_league.py:528) | "Players you did not own who returned for your rivals." | L7 | cut |
| [cards_league.py:330](../../cards_league.py:330), [:600](../../cards_league.py:600) | empty states ("You are running the template…", "…is a knot, not a trend…") | L6, L3 | figure: "0 differentials" / "from GW…" |
| [cards_scout.py:159](../../cards_scout.py:159) | "9 matches in, at most. A shortlist to look into, not a ranking." | C1 | cut |
| [scout.py:796](../../scout.py:796)–862 | 7 board notes ("Hit rate, with the per-90 behind it.", "Expected goals per 90, goals scored beside it." …) | C1 | figure: a 2–3 word unit label per board ("xG/90 · goals") |
| [cards_scout.py:165](../../cards_scout.py:165) | "Click a name for his match log, or tick up to six to compare." | C2 | cut |
| [playerview.js:148](../../playerview.js:148)–152, [:138](../../playerview.js:138) | "0.42 expected goals and … from a side priced at … Clean-sheet odds … priced by the betting market." | D1 | **i** |
| [playerview.js:183](../../playerview.js:183) | "Tiles marked Opta come from the Premier League API; the rest from FPL." | D1 | cut |
| [playerview.js:212](../../playerview.js:212)–214 | "Shaded by the team's expected goals." | D1 | cut |
| [playerview.js:239](../../playerview.js:239) | "53 points from 1,000 minutes. 9 goals and assists from 8.2 expected." | D1 | figure: "53 pts · 9 G+A · 8.2 xGI · 1,000 min" |

Keys and legends that stay (not prose): Breakdown legend [components.py:97](../../components.py:97), Scout scatter legend [cards_scout.py:184](../../cards_scout.py:184), match-strip key [scout.js:392](../../scout.js:392), "predicted to start" ring caption [cards_squad.py:489](../../cards_squad.py:489).

### Already behind an "i" or a collapsed card (33)

| file:line | Text (start) | Item | Verdict |
|---|---|---|---|
| [dashboard.py:451](../../dashboard.py:451)–456 | About & methods | X4 | keep collapsed (first-visit and CV context) |
| [dashboard.py:472](../../dashboard.py:472) | Starting XI: view definitions, scorer note, faded crest | S7 | **i**: only "Pitch xP uses match histories; the plan uses its season scorer" until scorers merge |
| [dashboard.py:511](../../dashboard.py:511) | Squad detail: sort hint, xP and Next 3 definitions | S8 | cut |
| [cards_squad.py:510](../../cards_squad.py:510) | "Fantasy Football Scout's predicted elevens…" | S10 | **i** (data source) |
| [cards_squad.py:639](../../cards_squad.py:639) | Fixture swings note | S13 | cut *(card goes)* |
| [cards_squad.py:712](../../cards_squad.py:712) | "The line is the gap. A solid green line means…" | S14 | cut *(card goes)* |
| [components.py:217](../../components.py:217) | "Two points a match at the threshold…" | S15 | cut *(card goes)* |
| [components.py:282](../../components.py:282) | "Who takes them, in the order the club lists them." | S16 | cut *(card goes)* |
| [components.py:339](../../components.py:339) | "Over the last 7 days. The season-long change…" | S17 | cut *(card goes)* |
| [analysis.py:786](../../analysis.py:786) | "Clear openings not taken. Read it as volume…" | S20 | cut *(card goes)* |
| [cards_plan.py:331](../../cards_plan.py:331) (note at [:313](../../cards_plan.py:313)) | plan scoring, roll, start-chance drift, "later weeks are a default" | P1 | **i**: becomes the one method home; add the margin/hit/enabler rules from P16 |
| [dashboard.py:542](../../dashboard.py:542)–543 | How the suggested action is chosen (2 paragraphs) | P16 | cut *(merged into P1 "i")* |
| [cards_planning.py:953](../../cards_planning.py:953) | radar axes scaling, ties, "Click a name…" | P4 | **i**: "Axes use each metric's full range" |
| [cards_planning.py:911](../../cards_planning.py:911) | "Four different questions…" | P5 | cut *(card goes)* |
| [cards_planning.py:674](../../cards_planning.py:674) | "Best gameweek for each chip in the current half…" | P6 | cut |
| [cards_planning.py:444](../../cards_planning.py:444) | Wildcard rebuild: "The full squad this would become… IN tag…" | P6b | cut |
| [cards_planning.py:496](../../cards_planning.py:496), [:556](../../cards_planning.py:556) | Bench Boost rebuild / bench notes | P6 | cut |
| [ticker.py:405](../../ticker.py:405) | Fixture outlook: rating recipe, dot = market, Games, Target, paging | P8 | **i**, one line (merged with P7) |
| [ticker.py:646](../../ticker.py:646) | "Pinnacle, margin removed…" | P9 | cut *(card goes)* |
| [cards_planning.py:767](../../cards_planning.py:767) | Best XI definition | P10 | cut *(card goes)* |
| [cards_planning.py:81](../../cards_planning.py:81) | "Prices update once a day…" | P13 | cut |
| [cards_planning.py:135](../../cards_planning.py:135) | "Pick any two measures." | P14 | cut *(card goes)* |
| [cards_planning.py:218](../../cards_planning.py:218) | elite source, managers, ±MOE | P15 | **i** (sample size matters) |
| [components.py:490](../../components.py:490) | leaders sub: P12 "Who is topping each measure…" / C1 "Ranked over 180 minutes…" | P12, C1 | P12 cut; C1 **i** |
| [dashboard.py:551](../../dashboard.py:551) | XI xGI definition | L2 | **i**, one line |
| [cards_league.py:617](../../cards_league.py:617) | "Every manager's rank in this league…" | L3 | cut |
| [cards_league.py:223](../../cards_league.py:223) | "The most-started legal eleven… the rest is where your rank moves." | L4 | cut |
| [cards_league.py:362](../../cards_league.py:362), [:329](../../cards_league.py:329) | "Every point they score is a point on the whole league." | L6 | cut |
| [cards_league.py:304](../../cards_league.py:304) | "Scored the same way as every transfer suggestion… two per club" | L9 | **i**: "Max two per club" |
| [dashboard.py:570](../../dashboard.py:570) | "Two of each per season…" | L8 | cut |
| [cards_scout.py:86](../../cards_scout.py:86) | "Capitals are home games. Difficulty is 1 to 5…" | C3 | cut *(card moves to P7)* |
| [cards_scout.py:177](../../cards_scout.py:177) | "Everyone is also one row of the table below…" | C2 | cut |
| [cards_scout.py:198](../../cards_scout.py:198) | "Each bar is distance from the filtered pool's own average… Right is always better" | C4 | **i** |

---

## 5. Reading order and headings

One display heading per tab. Everything else is a 12px section label (`.lab`, design.md) on its card, not an h2 at card-title size. Chapter bars go: they were navigation for long tabs, and every tab here gets short enough not to need them. The sticky chapter rail then has nothing to list. Hide it, or point it at the cards.

### Squad: what to do this week
1. **Score strip**: GW points, Season (rank), Up next (xP, bank, names to check). *S3 league tile leaves (G10).*
2. **Display heading = the action** ("MAKE 2 TRANSFERS") with the move cards, beside the captain card. Captain gains an expand for the radar (G2).
3. **Pitch.** Next gameweek is the default view; Season and Last gameweek are tabs. Card title shrinks to a label; "Published squad" strips go.
4. **Team news**: S10 ring and exceptions (S18, S19 folded in).
5. **Your 15, season** (collapsed S8 table). Drop "What the numbers say" and its cards S11–S17, S20, S21 (to S8 and the profile).

### Planning: the next weeks
1. **Display heading = "8 WEEKS, MAPPED."** (plan card) with the summary figure. Week tiles, then the stage.
2. **Deck** (alternatives only, the plan's moves removed; the knee-jerk becomes a tagged card).
3. **Chips**: coins row (P6); rebuild pitches stay collapsed.
4. **Fixture runs**: night band with tabs for model, FPL difficulty and position lens (CS / DefCon / goals); the 20-club ticker opens from it.
5. **Price watch.**
6. Method lives in the plan's "i". *Out: P4 → Squad, P5, P9, P11, P10 → cut or folded, P12, P14, P15 → Scout or cut, P16 → merged.*

### League: rivals
1. **Display heading = place** ("5TH") with the two gap tiles.
2. **Standings table** (lede cut).
3. **Position over time.**
4. **Template pitch** with your starters marked | **Your differentials** beside it.
5. **Scoring against you.**
6. **Differential watchlist.**
7. **Chips used.** *Out: L4b, L4c; chapter bars "What the league owns", "How they are playing it".*

### Scout: finding players
1. **Position switch** (it is the tab's heading; no display heading needed).
2. **Leaders** 2×2, unit labels instead of notes.
3. **Explorer**: filters, scatter, heatmap (open).
4. **Shortlist** compare when two or more are ticked. *Out: chapters "Worth a look", "Fixture runs", "Explore the pool"; C3 to Planning.*

### Player profile
Header (face, name, club, position, price ± season, owned %, transfers, status icon, set-piece icons, archetype) → next match (big xP, opponent crest, CS%, team xG) → season figures with percentile bars → next 6 fixtures → match strip (log table behind an expand) → last season, one line.

---

## 6. Decisions for Jonno (recommendation first)

1. **Move Planning's "This week" and "The wider market" content off Planning.** Recommend: captaincy radar under the Squad captain card; cut odds, Highest XI, Buy/Sell/Keep/Avoid; fold the knee-jerk into the deck; Season leaders and Value scatter go (Scout covers both). Alternative: keep the Value scatter's price, points-per-£m and ownership axes by adding them to Scout's scatter.
2. **Cut the Squad findings column down to team news.** Recommend: keep Predicted line-ups (with availability and rotation folded in); move the rest to the squad table and the profile. Alternative: keep Set pieces as a small card. It is the one findings card with no column in the table.
3. **One fixture home: Planning's night band**, with the Scout position lens as a tab and the 20-club ticker as its expand. Recommend over keeping Scout's own fixture card. Alternative: Scout keeps its card and Planning drops the ticker.
4. **One fixture scale page-wide.** Recommend the 0–10 rating (higher is better) everywhere, with FPL's 1–5 only as the band's second tab. This removes four "which way round" explainers.
5. **One horizon for gain figures on Planning.** Recommend the plan's window (GW10–17) for the deck too, so Isak doesn't read 45.8 in one card and 33.9 in the next. It touches the transfer scorer, so needs your OK.
6. **Squad's league tile.** Recommend cut (League tab has the place card). Alternative: keep it as a link with no change chip.
7. **Remove the plan's own moves from the deck.** Recommend yes. The deck is "other options"; two of its nine cards are the plan's own moves.
8. **Fix before deduping, not after:** the 62.7 / 48.2 / 70.9 "your XI" figures, Wildcard +70.1 v plan +45.5, and season 600 v 598 (section 3). Recommend: show only the plan scorer's figures on Planning and the match-history scorer's on Squad until the scorers merge.
