# Managed account — current handoff

Last updated 29 October 2026. Keep this work separate from dashboard development
and the other research chat. Start here for this account; root `docs/HANDOFF.md`
describes the dashboard product, not this experiment's current team.

## State

- **Live account created:** entry **11195024**, Jonno's Team, starts GW9.
  Saved XV £99.6m, £0.4m bank. Signed-in UI and persistence after reload verified.
- XI **3-5-2**: Trafford; Gabriel, Van Hecke, Muharemović; Belloumi, Rogers,
  Palmer, Neto, Tavernier; Haaland, Barry. C Haaland; VC Van Hecke.
- Bench GK Kinsky; outfield order Konsa, Vuskovic, Cherif. All four chips unused
  this half; WC/FH unavailable in first scoring week, confirmed in account UI.
- Upcoming deadline **31 October 2026 11:00 Europe/London (UTC)**. Unlimited
  initial changes until then, explicitly verified on the live Transfers page.
  Read live allowance afterwards; do not invent FTs.
- `state.json` is the last **confirmed** account record, not an instruction to
  overwrite newer user changes. Read the real signed-in team first.
- Read `strategy.md` for authority, evidence order, decisions, chips and recovery;
  `rules.md` for current rules/date discrepancies; `decisions/2026-10-29-gw9.md`
  and matching JSON for the frozen initial rationale, squad and forecasts.

## Isolation

- All operational files and scripts are in `account-management/`.
- `config.json`, product code, generated site, projections and price history were
  not changed by this work. Existing modified `price_history.json`, 91 staged
  research paths, untracked research/app-control files belong to other work.
- Never repoint dashboard entry **3385667** or the existing `fpl-lineup-alert`
  project to this team. Its README/apply code were inspected only; its saved
  tokens, encryption files and secrets were not read, tested or changed.
- Raw input/cache files and screenshots remain in this directory's ignored
  `.cache/`. No credential/session export. Do not commit secrets.
- Root HANDOFF has only a pointer to this separate track. No push/publication
  authorised. Commit only explicit account paths and the small root pointer.

## Scheduled operation

- Heartbeat ID **manage-fpl-experiment**, active in this chat. Configuration
  viewed successfully. Baseline reviews **09:00 and 18:00 Europe/London**.
- Its instructions temporarily increase this same heartbeat to hourly on the
  hour when within 12h of a deadline, then return to the baseline afterwards.
  No duplicate schedules. Main review after team news, final check near an hour
  before the actual FPL deadline. This adaptive behaviour remains untested.
- The schedule uses the local computer/app and available logged-in browser.
  It cannot promise action if those are asleep, closed, locked/inaccessible,
  disconnected or require reauthentication. The initial manual account write
  and reload worked; a later unattended run has not yet been observed.
- No point hits or chip activation under the current starting policy. Those
  limits were announced by the assistant; Jonno has not expressly expanded them.
  Routine free transfers and team/armband changes are delegated.
- Notifications: meaningful confirmed changes, failures or required user action;
  quiet when unchanged. End/disable after GW38 and report experiment results.

## Verified checks

- `python -X utf8 account-management/prepare.py --self-check`: legal scoring,
  beneficial upgrade, six invalid-squad and five invalid-fixture cases passed.
- `python -m unittest discover -s tests -t .`: **112 tests, OK**. Expected image
  404-fallback fixture messages only. No hosted build needed: no production edit.
- Live input run: 669 players, 380 fixtures, 219 predicted starters, 760 fixture
  rows, 8 historical weeks, 173 eligible candidates, 25 distinct initial squads.
  Full candidate data in `.cache/preparation.json`; 23 individual histories in
  `.cache/history-review.json`; stress comparisons in `.cache/sensitivity.json`.
- FPL saved team was checked after reload, including correct entry history link,
  XI, ordered bench, Haaland C/Van Hecke VC, no active chip and finance.
- Initial squad selection/entry and reversible team changes are proved for this
  session. Ordinary later buy/sell, chip writes, login longevity, background
  browser availability and adaptive scheduling are **unverified**.

## Browser mechanics learned

Use `cua_repl` and the current tab inventory. Current managed team is in the
in-app browser on `/en/my-team`; rebind an existing FPL tab by returned ID.
Do not assume persisted JS handles survive a new runtime. `var` creates a new
handle when an earlier bare assignment reports an undefined variable.

Player search opens a selection dialog with a labelled searchbox and exact
`Add player NAME` buttons. Match the **actual result row's** name/club/price.
The position dialog stays open after adding a player; close before switching.
`Enter Squad` submitted directly, then showed badge/new-feature popups. No new
legal checkbox was presented. Those optional popups were dismissed.

For substitutions: click outgoing player's profile → Substitute; click target
player → its Substitute. Clicking the target alone just opens its profile.
The same flow reorders two reserve outfield players. Save Your Team is required.
Vice/captain checkboxes close the profile on action. A Playwright `check()`
reported a timeout after the actual toggle succeeded: inspect the visible role
before retrying. UI animations can briefly leave stale nodes or disabled cards;
fresh observation is safer than a fast multi-step click chain. Never blindly
repeat a financial/transfer-like write after an ambiguous response.

The old native Chrome fallback stopped when it could not establish its URL.
Do not bypass that guard. In-app browser access has worked since Jonno logged in.

## Next work

1. Confirm the heartbeat's first real run and browser availability. Record actual
   results, not just ACTIVE configuration. If it fails, preserve the legal saved
   team and report the concrete access problem once.
2. Refresh Friday's news/press conferences, cup minutes and current live prices.
   Reassess Chelsea concentration and Manzambi's sustained role. No automatic
   change simply because a fractionally different model seed appears.
3. Finalise GW9 before 31 October 11:00 and recheck saved team/chips after reload.
4. After GW9 score against the frozen initial baselines and plan GW10 with the
   actual authenticated FT/selling prices. Review first-half chips by GW12/GW15;
   get a single clear expansion of chip authority if Jonno wants hands-off chips.

## Resume prompt

```text
Read account-management/HANDOFF.md, strategy.md and state.json in C:/Users/jonno/code/fpl-insights. Continue managing entry 11195024 only. The GW9 squad is saved and verified, first deadline 31 October 2026 at 11:00 UK. Check the real signed-in team before changes. Verify the first run of heartbeat manage-fpl-experiment; refresh deadline-relevant primary team news and reassess the recorded risks. No hits/chips without expanded authority. Keep all work in account-management, preserve other staged research and dashboard changes, do not publish or repoint config.json or fpl-lineup-alert. Save, reload, verify and log any actual change.
```
