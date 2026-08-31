# fpl-insights

Underlying stats for your FPL squad and your mini-league — the xG, xA and
defensive-contribution numbers behind the points, per match.

Everything comes from FPL's own public API. No login, no scraping, no API key,
no third-party packages. Python 3.9+ and the standard library.

```
python cli.py dashboard --open     the whole thing as a web page
python cli.py team                 your 15, with per-match xG/xA
python cli.py league               how your rivals are doing, and why
python cli.py player szoboszlai    one player, in detail
```

## The dashboard

`python cli.py dashboard --open` writes a single self-contained `dashboard.html`
and opens it. Everything is baked in — club badges as data URIs, no network
calls once written — so it works offline and can be mailed, hosted or opened
from disk. Re-run it whenever you want current numbers.

Three tabs: **Squad** (pitch view - Overview by default, with a Pick Team
toggle for next-fixture and form context instead - sortable detail table,
and findings cards; click any player for their full match-by-match log and
Opta stats), **Planning** (the chip planner's Free Hit / Triple Captain /
Bench Boost / Wildcard recommendations, fixture ticker, price-change and
transfer-suggestion cards, and elite-manager ownership), and **Mini-league**
(standings with each rival's XI xGI, captain and chip, plus
template/differential analysis).

Styling is taken from FPL's live stylesheet rather than approximated: brand
purple `#37003c`, the purple-biased `mono-p` neutral ramp, their radius and
spacing scales, and their five-step fixture-difficulty colours with the text
colours they prescribe for each. Both light and dark use FPL's own theme
mappings, not an invented inversion.

Two deliberate departures. FPL sets type in **PremierSans** (PremierLeagueW01),
a licensed Monotype face — embedding it would mean redistributing it, so the
page uses Barlow over FPL's own declared Arial / Helvetica Neue fallback.
And difficulty pills always carry a visible opponent and number: the bright
green and grey steps sit at 1.35:1 and 1.2:1 against a white surface, so colour
alone would not be readable.

`--artifact` also writes a body-only copy for publishing to a hosted page.

## Access

The live dashboard: **https://fpl-insights-jm.vercel.app** - a public URL
(not indexed or linked anywhere), deployed from this repo without exposing
the source or `config.json`, since the repo itself stays private. Open it on
your phone and "Add to Home Screen" for an app-like icon - it's a static
page, so that's the whole install.

It rebuilds automatically (see [How it stays current](#how-it-stays-current)
below), so this URL is never more than a few hours behind live FPL data with
nothing to trigger manually.

`python cli.py dashboard --open` is the alternative: a local build using your
own machine's network access, for current-minute data rather than the last
scheduled build.

## Setup

Put your ids in `config.json`:

```json
{
  "entry_id": 3385667,
  "league_id": 1453141
}
```

Your `entry_id` is the number in the URL when you view your own team
(`/entry/<id>/event/1/`). The `league_id` is the number in a mini-league URL.
Both can also be passed as `--entry` / `--league`.

## What you get

### `team`

- **Squad table** — price, ownership, minutes, points, xG, xA, xGI, xGI per 90,
  defensive contribution per 90, and the next three fixtures with difficulty.
- **Per-match log** — one row per fixture per player: minutes, goals, assists,
  xG, xA, xGI, defensive contribution, BPS, points. This is the thing FPL's own
  interface will not show you.
- **Captaincy** — whether the armband went on the highest underlying option in
  your XI, judged on xGI per 90 rather than on the points it happened to score.
- **Bench** — points left on the bench and which starters they outscored.
- **Findings** — availability flags, players scoring above or below their
  expected goals, defensive-contribution threshold rates, set-piece duties,
  rotation risk, fixture swings, price movement, and last-season baselines.

`--matches N` sets the log depth, `--no-log` skips it, `--gw N` picks a
gameweek.

### `league`

- **Standings** with each manager's gameweek score, chip played, bench points,
  transfer hits, and the season xGI of their starting XI. A high score next to
  a low XI xGI means the points came from somewhere that will not repeat.
- **Who owns what** — the league template, your differentials, and the players
  most of the league has that you do not.
- **Captain picks** across the league.
- **Chips used**, so you know who has already burned a Bench Boost.

`--squads` prints every manager's full XI and bench. `--limit N` caps how many
managers get analysed.

## How it stays current

One scheduled piece, one automatic reaction to it - deliberately reduced
from two scheduled pieces (below).

**GitHub Actions builds it** (`.github/workflows/build.yml`), every three hours.
It runs the build, commits `dashboard-artifact.html` if the page changed, and
warns in the run log if any data source dropped out.

Three-hourly rather than twice a day because GitHub's scheduler is best-effort.
The very first scheduled fire here was skipped outright - no run, no error, and
the routine went on to publish an eight-hour-old page while calling it fresh.
Eight chances a day makes a dropped fire a non-event. Runs where the page has
not changed exit without committing, so the extra frequency costs nothing.

The build runs here rather than in a Claude session because Claude's sandbox
sits behind a policy-enforcing egress proxy that refuses CONNECT to
`fantasy.premierleague.com` with a 403 - it cannot fetch a single byte of this
project's data. GitHub's runners have open outbound network.

**Vercel deploys it automatically.** The Vercel project is linked directly to
this repo, so every commit to `main` - i.e. every build above that actually
changed the page - triggers a fresh deploy with no extra step. This used to
be a second scheduled piece: a Claude routine that cloned the repo twice a
day and republished a hosted artifact. It quietly stopped running at some
point with no error, and nothing surfaced that until the live page was
checked against the repo directly. Deploying straight off the git push
removes that failure mode rather than just monitoring for it better - there
is no second schedule left to silently stop.

One thing that looks wrong but is not: **the built HTML is committed.** A
1.1 MB page eight times a day sounds expensive. It is not - the embedded
photos are byte-identical between builds, so git deltas them away. Measured
across two consecutive builds: zero growth.

Timing is deliberate. Prices change around 01:30 UK, so the early builds catch
them; predicted line-ups only sharpen through the day, so later builds are the
ones that land before a typical 18:30 deadline. Nothing is ever more than
about three hours stale.

Every run ends with a source-health block, so a broken scrape shows up as a
`FAIL` line rather than a section quietly vanishing from the page.

## Sources beyond FPL

Three things here do not come from FPL, because FPL does not have them.

**Predicted line-ups** — Fantasy Football Scout's team-news page. FPL's API says
nothing about who will actually start. FFS renders each predicted starter with a
player photo whose filename is the same id FPL exposes in `element["photo"]`, so
the two join on a number, not a name. If the page fails to parse, the feature
reports nothing rather than marking everyone benched.

**Premier League Opta stats** — `footballapi.pulselive.com`, the open API behind
premierleague.com. Big chances created and missed, shots, shots on target,
successful dribbles and touches, none of which appear in FPL's own site or app.
The join is exact: Pulselive returns `altIds: {"opta": "p223094"}` and FPL carries
the identical string in `element["opta_code"]`. Two quirks — ids come back as
floats and must be cast to int for URLs, and the ranked endpoints only include
opta ids when asked with `altIds=true`.

**Elite ownership** — FPL runs a public global league of every entry, id 314.
Its standings are ranked, so the top managers' squads can be read exactly like a
mini-league rival's. Ownership among that group separates "popular" from
"popular with people who are winning", and FPL publishes nothing like it.

Two modes, because scale matters. `--elite 100` (the default) reads every
manager in the top 100 exactly, about 100 requests in 8 seconds. Exact ownership
for the top 10,000 would need roughly 10,200 requests and half an hour, which is
not a reasonable thing to do to a free API — so deeper ranges use a systematic
sample instead: `--elite 10000 --elite-sample 500` spreads 500 managers evenly
across the range in about a minute and reports a margin of error (near ±4 points
at 95% confidence). Sampled figures are always labelled as estimates.

**Price-change forecasts** — FPL's own `price_change_percent` and
`price_change_projections`, which the site does not surface. Signed: positive
rises, negative falls, and the change fires at 100.

Sources checked and rejected: FBref (403), FotMob (404), Sofascore (403), and
Fantasy Football Scout's projected points and DefCon tables, which render player
names for anonymous visitors but strip the numbers — that is their paid product.

## Notes on the data

**Per-match history is current season only.** `element-summary` gives one row
per fixture for this season, but for previous seasons the API keeps totals
only — no per-match breakdown. Those totals are used as a baseline while the
current season is short. If you ever want per-match history going back further,
`github.com/vaastav/Fantasy-Premier-League` archives it as CSV per gameweek
from 2016/17 onward, with the same column names.

**Defensive contribution.** FPL awards 2 points for hitting a threshold in a
match: 10 for defenders (clearances, blocks, interceptions, tackles), 12 for
midfielders and forwards (the same plus recoveries). The API's
`defensive_contribution` field is already composed correctly per position —
verified against the raw components rather than assumed — so only the
threshold differs by position.

**Early season.** Per-90 rates over one or two matches are noise. The report
says so explicitly when players are under 270 minutes, and falls back to
last-season baselines.

**FPL's xG is Opta's.** Understat runs a different model and will not agree —
for 2025/26 Haaland was 25.50 xG by FPL and 28.80 by Understat. Never mix the
two in one number. If you want Understat's extras (npxG with penalties stripped
out, xGChain, xGBuildup, per-shot data), note that its old embedded-JSON
scraping pattern no longer works; the data now comes from
`understat.com/getLeagueData/{league}/{season}` and
`understat.com/getPlayerData/{id}`, gzipped, needing `Referer` and
`X-Requested-With` headers.

## Two environment quirks this handles

- **`curl` cannot reach the FPL API from this machine** — the TLS handshake
  fails (curl exit 35) sandboxed or not, while Python's `urllib` succeeds
  against the same host. Everything here uses `urllib`.
- **Connection resets.** Requests on this network intermittently die with
  WinError 10054. Every fetch retries with backoff.

Responses are cached in `.cache/` for 15 minutes. `--ttl 0` forces a refresh.
