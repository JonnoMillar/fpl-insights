# FPL Insights

Start here: read docs/HANDOFF.md. At each stage gate: update HANDOFF.md, commit, check in, suggest /clear.

## Project and working rules

- A Python-generated static FPL squad and mini-league dashboard, with vanilla JavaScript interactions. README.md and current code are authoritative; older docs/superpowers plans are historical context.
- Preserve the existing architecture: Python standard library, no frontend framework or bundler. Pillow is optional image compression. Do not add dependencies, paid services, features or unrelated refactors without a concrete need and appropriate authorization.
- Inspect existing work before editing. Preserve user changes. Investigate thoroughly, report briefly, and verify actual browser/data boundaries as well as tests.
- League members have consented to display their data and pictures for this personal project. Do not reopen that settled question without new evidence.
- Keep stable instructions here and current status, verification counts, decisions and next steps in docs/HANDOFF.md.

## Commands

```powershell
python -m unittest discover -s tests -t .  # dependency-free regression suite; CI uses this
python -m pytest -q                      # alternative when pytest is installed
python cli.py dashboard --artifact      # complete hosted HTML plus projections.json
python cli.py dashboard --open          # build and open the standalone page
node --check dashboard.js               # repeat for edited feature scripts
git diff --check
python -m http.server 8766 --bind 127.0.0.1  # local browser verification; stop afterwards
```

config.json selects the manager and league. API responses and image assets are cached in .cache/. A fresh build fetches public data and also updates price_history.json; use a temporary --out path for checks when appropriate. Do not publish an incomplete or unverified generated artifact.

## File map

- fplapi.py: API fetching, retries, caching, images and source health.
- analysis.py: context, reports, fixture-bound scoring and recovered selling values.
- odds.py, ffs.py, pulse.py, elite.py: external sources.
- transfers.py, chips.py, captaincy.py, squadbuilder.py: recommendation logic.
- dashboard.py: data assembly and document rendering; cli.py: entry points and output files.
- cards_squad.py, cards_planning.py, cards_league.py, cards_scout.py: tab content.
- cards_common.py: HTML escaping and script-safe JSON encoding.
- dashboard.css, dashboard.js and feature .js files: styles and interactions.
- tests/: offline regressions, including the CV-readiness cases.
- .github/workflows/build.yml: tests, scheduled/source-change builds and generated commits.
- vercel.json: root URL serves dashboard-artifact.html.
- docs/audits/: evidence and fixes; docs/og.png: published social preview.

## Hard-won constraints

- Hosted dashboard-artifact.html must be a complete standards-mode HTML document with language, encoding and viewport metadata. A body fragment is not a website; render(..., standalone=False) is not the hosted output.
- Use cards_common.script_json for every JSON payload inside an HTML script element. json.dumps alone does not protect the closing-script boundary. Use normal HTML escaping for visible text and attributes.
- Keep projections.json's public gw/generated/xp interface compatible with the separate phone-alert project. Unavailable predictions must not look valid for the requested week.
- Public picks, bank and transfer allowances describe the last published squad, not authenticated pre-deadline changes. Affordability uses recovered selling prices; withhold advice if those cannot be recovered.
- Choose an owned squad's starting XI with squadbuilder.owned_xi, not the cheap-bench-first budget builder. Evaluate paired transfers together, with one budget and the full squad's ownership/club constraints.
- Fixture estimates must agree with FPL's gameweek, opponent and venue. Bind market data to the priced date. Distinguish a confirmed blank from unavailable projections. Do not repeat one market fixture across later weeks.
- Double-gameweek prediction support is deliberately absent. Withhold affected planning advice and label historical multi-fixture aggregates rather than pretending they describe one match.
- Optional-source failures must preserve core squad/league rendering and be visible on the page. Fatal failures and regression failures must prevent generated publication. Keep the last valid artifact.
- HTTP 403/404 portrait failures use existing fallbacks; retries cannot repair these answers. Use urllib for FPL; curl has historically failed its TLS handshake on this machine.
- GitHub scheduling is best-effort. Do not promise guaranteed three-hour freshness; the browser flags overdue snapshots.
- Scheduled builds commit generated HTML, projections and price history to main. Fetch before publishing and integrate concurrent bot commits without force-pushing or overwriting source changes. Generated conflicts can be resolved with verified regenerated output.
- Browser screenshots can capture a tab-indicator animation mid-transition. Check actual selected state and settled geometry before reporting an indicator bug.
