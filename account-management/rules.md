# Rules reference — 2026/27

Checked against the **rendered, signed-in rules page** on 28 October 2026.
Recheck on a rules change, January chip reset, and before a special-week action.
Sources: [live rules](https://fantasy.premierleague.com/en/help/rules),
[live FAQ](https://fantasy.premierleague.com/en/help/faqs),
[official chip explainer](https://www.premierleague.com/en/news/4679879/whats-happening-with-fpl-chips-in-202627).

## Legal team and deadlines

- £100m initial budget; fifteen players: 2 GK, 5 DEF, 5 MID, 3 FWD;
  no more than three per club. XI: one GK, at least three DEF and one FWD.
- Captain doubles points; vice takes over only if the captain does not play.
  A cameo can block both a vice-captain switch and an automatic substitution.
- Bench priority applies subject to a legal formation. Reserve GK only replaces
  GK. A card can count as participation even without recorded playing minutes.
- No manual intervention changes the current scoring week after its deadline.
  Read the event's current deadline, not an assumed Saturday kickoff or timezone.
- New entrants have unlimited free changes until their **first** deadline.
  Thereafter one FT per week; carry up to five. Each excess transfer costs four.
  Normal-week transfer cap is twenty. Confirmed ordinary transfers are final.
- Selling price is not current market price: keep half a price rise in £0.1m
  steps; falls can reduce proceeds. Use authenticated displayed sale values.

## Scoring card

| Event | FPL points |
|---|---:|
| Appearance below 60 minutes / at least 60, excluding stoppage | 1 / 2 |
| Goal: GK / DEF / MID / FWD | 10 / 6 / 5 / 4 |
| Assist | 3 |
| Clean sheet: GK or DEF / MID | 4 / 1 |
| Every three GK saves / penalty saved | 1 / 5 |
| Every two goals conceded, GK or DEF | -1 |
| Yellow / red / own goal / missed penalty | -1 / -3 / -2 / -2 |
| Match bonus | 1–3, including tied awards |
| Defensive threshold reached in a match | 2, once per match |

DEF threshold: 10 combined clearances, blocks, interceptions and tackles.
MID/FWD: 12 including recoveries. A per-90 average above a threshold does not
mean the player receives the award every match. Clean-sheet points require
60 minutes and no goal conceded while on the pitch; dismissal is an exception
because later conceded goals still count against the dismissed defender/GK.
Assists use FPL/Opta's final-touch, rebound and won-penalty rules, not necessarily
another provider's assist statistic. BPS is a separate underlying system;
3 BPS does **not** mean 3 fantasy points. Provisional scores can be revised.

## Chips and late entry

Each half has Wildcard, Free Hit, Bench Boost and Triple Captain; one chip per
week. Unused first-half chips expire at the GW19 deadline, not the end of GW19.
WC permanently resets the squad within its real budget. FH temporarily resets
it for one week, then restores the old squad/bank with relevant price changes.
BB includes bench scores; TC adds one further captain share beyond normal
doubling. WC/FH are unavailable in this account's first scoring week, when
changes are already unlimited. FH cannot be used in consecutive weeks.
Saved FTs survive WC/FH; confirm actual next-week allowance in the account.

**Date conflict:** the July chip article says GW19 is 2 January at 13:30 GMT;
the live rules page says 1 January at 18:30. Never hardcode either prose date.
Read current `events[id=19].deadline_time` and the signed-in chip availability.
The FAQ also contains a WC-pending cancellation qualification that the main
rules do not explain. Treat a confirmed chip as committed; do not depend on
being able to undo it.

## Prices

The [official predictor explainer](https://www.premierleague.com/en/news/4680462)
describes progress towards a threshold, not a calibrated probability of a rise.
Above 100% is not certainty: subsequent transfers can alter it. The explainer's
00:00 UK wording and live-page local-time display can diverge around clock
changes; read the displayed next update rather than hardcoding a nightly hour.
Use price risk only to time an independently worthwhile move. Check the current
purchase price again immediately before confirmation.

## Participation boundary

This is Jonno's personal, non-commercial account-management experiment. He has
authorised squad selection and ongoing management. The previously explained
[FPL terms](https://fantasy.premierleague.com/en/help/terms) restrictions remain;
personal use does not establish Premier League permission. No paid league,
prize claim, money movement or external account creation is part of this work.
