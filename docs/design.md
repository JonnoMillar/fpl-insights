# FPL Insights design system

Agreed direction, 1 November 2026. Source: the final draft on the brand canvas
(https://claude.ai/artifact/9paQtGhWZJ4K6NS4gmYzAn, row "Final draft"), copied into
`docs/design-reference/` as F-Kit, F-Desktop and F-Phone. Those boards are written in
Archivo; this document overrides them wherever type is concerned. Images in the boards
are canvas `/_blob/` ids and do not render locally: read them for structure, sizes and
CSS. `docs/brand-handoff/` README files still mention Archivo, #01FC7A and the rejected
vector suite; this document supersedes them.

## Colour

| Token | Value | Use |
| --- | --- | --- |
| `--purple` | #37003C | Rail, headlines, selected week, captain card, deck cards |
| `--night` | #16001A | Body text, caption strips, the dark band |
| `--green` | #00FF87 | One loud panel per screen, gains, planned chips |
| `--white` | #FFFFFF | Stage, cards, week tiles |
| `--paper` | #EEECEF | Page ground |
| `--mist` | #F4F2F5 | Photo panels behind cut-outs |
| `--line` | #E6E2E8 | Hairlines, unselected tile edge |
| `--muted` | #5B4E60 | Section labels only (never help text) |
| `--glow-1`, `--glow-2` | #963CFF, #04F5FF | Blurred light inside night areas. Never carries meaning |

- Green is #00FF87 (FPL's own green, used throughout the boards), replacing the old
  #01FC7A. The difference is invisible; one value avoids drift.
- Target laptop balance: paper 38%, white 24%, purple 14%, night 13%, green 11%. Every
  laptop view shows a white stage, a purple card, one green panel and one night band.
  Neighbouring sections never share a fill.
- Meaning never rides on hue. The current `--good`/`--bad` (green/red), `--attention`
  amber, `--mine` magenta, `--rival` blue and `--market` teal tokens go. Gains and losses
  read from sign and arrow (+8.7, price-rise icon), ownership from words ("you own 3"),
  states from fill, weight, lift and icons.
- Gone for good: the lilac `--p*` scale, tinted card-in-card, coloured card edges,
  green-edged chapter bands, large gradient washes.

## Type

Noto Sans only (Google Fonts, weights 400 to 900, `display=swap`). Tabular figures
page-wide. Never a slashed or dotted zero, never thin figures.

| Role | Setting | Sizes |
| --- | --- | --- |
| Display | 900, capitals, letter-spacing -0.01em, line-height 0.95 | 40 page, 34 stage, 26-30 card names |
| Numbers | 900, tabular | 80 hero, 56-68 card, 28 inline |
| Body | 600-700, line-height 1.4 | 15-20, never under 14 |
| Label | 12, 800, tracked capitals (0.12em) | Section names only, one per card |

Noto Sans has no expanded width, so the boards' width-125 display setting becomes normal
width at 900. Check display headings for wrapping at 375 and 320px.

## Icons

Use the generated set in `docs/brand-handoff/transparent-suite/` (40 icons, Saves B).
Do not redraw any of them in SVG. Production use goes through one packed sprite (below),
never the four source atlases.

Assessment, 1 November (measured from the atlases):

- **Fit.** One rounded-outline language, recolourable to purple, white, green or night
  through one class. Football-specific symbols (armbands C, V and 3C, chip symbols,
  cards, injury) give the instant recognition Jonno asked for alongside faces and
  crests. Yellow versus red card differs by outline versus solid; price rise versus
  fall by direction. Both work without hue.
- **Weight spread.** Stroke width at 24px runs from 0.77px (corners) to 2.7px (chevrons);
  the core set sits at 1.7-2.0px. Corners (0.77), saves (1.0), free kicks (1.0) and
  injured (1.2) look faint beside the rest. Fix: thicken those four alpha masks by a
  morphological dilation at pack time (artwork kept, only the line weight grows),
  or regenerate them heavier. Needs Jonno's pick.
- **Planning is cropped.** Its source rectangle cuts the last route node and includes
  a speck from the neighbouring shirt. This is the Planning nav icon. Fix the rectangle
  at pack time from the icon's own connected components.
- **Yellow card reads as a phone** because of the bar inside it. Recommended: drop that
  bar component at pack time so it is a plain outline card. Needs Jonno's OK.
- **Weight of files.** The atlases total 3.19MB for icons drawn at 32px or less. CSS masks
  also load in CORS mode, so external PNGs fail on the file:// standalone build.
  Packing 40 icons into 64px cells gives one 56KB PNG (measured), embedded as a data URI.
- **Small sizes.** Free kicks, saves, corners and injured are illegible at 16px. Minimum
  20px for simple controls, 24px for navigation and football scenes, always with a
  visible or accessible label.
- **High contrast.** Mask icons are painted with `background-color`, which forced-colors
  mode overrides. Add `@media (forced-colors:active){.ico{background-color:CanvasText}}`.
- **Overlaps to avoid.** Use Defence for defensive contributions and Clean sheet only for
  clean sheets; Minutes (stopwatch) and Deadline (clock) are not interchangeable.

Production pipeline: a one-off packer reads `catalog.json`, crops each source rectangle
(with the fixes above), resizes to 64px alpha cells in an 8 x 5 grid and writes
`assets/icons.png` plus a name-to-index list. Pillow is needed only to repack, not to
build. `dashboard.py` base64-embeds the PNG with the standard library into one CSS
custom property; `.ico` plus a modifier class selects a cell by `mask-position`.

## Logo

Goal frame with three ascending bars (`docs/brand-handoff/logo/goal-chart-draft.svg`).
Geometry is still a draft: use it in the rail, check at 16, 24 and 32px and show Jonno
before producing favicon, app icon or og image exports.

## Shape, depth, texture

- Corners: 28 sections and the stage, 24 cards, 18-22 tiles and photo panels, 12-14
  strips and plates. No pill shapes for tags or labels.
- Shadows: soft and purple-tinted on paper. White cards barely lift; the selected week
  and the deck lift most.
- Glass: only on night - crest tiles, the deck's opponent plate, the phone tab bar.
- Texture: faint pitch markings at 7-8% opacity on the stage, the green panel and purple
  headers. Nothing else.

## Components (from F-Kit)

- **Week tile** (96px wide): default white with hairline; selected lifts 3px, fills purple
  and casts a purple shadow; chip week shows a chip coin; roll week shows the roll icon.
- **Chip coin**: planned green, available purple, saved white with purple ring, used
  struck through (not only greyed). Chip icon inside the coin, chip name beneath.
- **Transfer card**: mist photo panel, outgoing player grey at 55% opacity on the left,
  arrow, incoming player standing on the bottom edge, name in display caps, night caption
  strip with the opponent's crest and one line of reasoning.
- **Captain card**: purple, green ring behind the cut-out (never across the body),
  opponent crest, one big xP number.
- **Glass crest tile**: night band, blurred glow behind, glass plate, crest breaking the
  top-right corner, run score in big numbers.
- **Swipe deck** (other transfer options only, never the hero or captain): purple cards
  fanned behind on the green panel, glass opponent plate, gain in green numbers. Drag,
  arrows, ranked list (desktop) or row of faces (phone). Gentle foil shimmer.

Player images: cut-outs stand on a card's bottom edge or fade; never end in a hard line
inside a card. Break out of a card only on big hero cards. List rows use round faces.
Show the opponent's crest, not the player's own club.

## Layout

- Desktop: purple side rail with logo and four icon-plus-word tabs (Squad, Planning,
  Mini-league, Scout). Selected tab differs by fill, icon weight and position marker, not
  hue alone. Stage on paper to the right.
- Phone: bottom tab bar in night glass, same four icons with words.
- Planning follows F-Desktop: week stage (GW tiles revealing one week at a time), hero
  move, captain, green panel with the swipe deck, night band with best and worst fixture
  runs as crest tiles, white last-week card.
- Squad, Mini-league and Scout have no board of their own. Build them from these
  components and show Jonno before polishing.

## Motion

- Week change: new stage content rises 14px and fades in, 500ms.
- Deck: cards travel 550ms; a drag past 70px (60px on phone) flips; the top card tilts
  with the drag.
- Hover: tiles lift 3px; glass tiles catch a light sweep, 900ms.
- One easing: `cubic-bezier(.2,.8,.2,1)`. `prefers-reduced-motion` turns all of it off.

## Copy

Titles state the finding. One headline number per card. Low-key, no boasting. No small
grey help or info lines; method notes sit behind a disclosure. Keep the
published-squad, no-double-gameweek and data-unavailable caveats visible once each.
