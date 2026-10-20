# FPL Insights: CV showcase design assessment

Reviewed 20 October 2026 using apple-design. Proposal only; no application or generated-output changes.

## Summary

**Overall: Needs work as a showcase; the existing identity is worth keeping.** The product's job is to turn public Fantasy Premier League data into understandable squad decisions. Its strongest visual asset is the actual team sheet, supported by a personal weekly review and explorable evidence. Those should define the first impression.

The present hierarchy makes a visitor work to understand the product and discover its interactive depth. More animation would have less impact than improving arrival, composition and discovery. This is design judgment informed by the evidence below, not a claim about recruiter behaviour measured in user testing.

## Scope and version boundary

- Inspected the public site at `https://fpl-insights-jm.vercel.app/` and the existing local `revised.html` build at 1440px desktop and 390px phone width. Checked all four local tabs at 320px, plus a 720px resized layout.
- Live arrival displayed the **20 October, 08:12 UTC** snapshot. It still used the older pitch controls and lacked the latest hero actions. Treat publication of verified source as a separate delivery prerequisite, not a new design finding.
- The local build contains the **14 October, 13:17 UTC** data snapshot. Its CSS and embedded dashboard.js, scout.js, playerview.js and ticker.js exactly match the current source. It is useful for reviewing committed presentation and interactions; its advice is historical. Its overdue warning is expected and is not evidence that the live feed is stale.
- Read dashboard.py, dashboard.css, dashboard.js, cards_squad.py, cards_scout.py and relevant player/Scout interaction code, plus the earlier design brief and handoff. Preserve Jonno's explicit decision to keep the review hero on desktop and mobile, the stable pitch and existing functionality.
- Applied Apple's foundations to a website: hierarchy, legibility, restraint, feedback and adaptable layout. Native navigation placement, native point sizes, Liquid Glass and App Store rules are not web requirements.

## Five changes with the greatest presentation impact

### 1. High — Explain the product before asking visitors to interpret the team

**Evidence.** Arrival says FPL Insights, then leads with the team name as the only h1. There is no visible purpose statement. The source link appears in the footer as “source and phone alerts”. A visitor unfamiliar with FPL must infer both the task and the personal scope. See [dashboard.py](../../dashboard.py), header/hero rendering around lines 332–350 and footer.

**Change.** Add a compact product introduction: **“The numbers behind your FPL decisions.”** Follow with **“Jonno Millar's public squad and mini-league, analysed from player statistics, fixtures and market odds.”** Make **Source code** and **About & methods** accessible near the top. Keep technical detail in the latter, where a hiring manager can inspect the project after trying it. Use “Fantasy Premier League” at first mention and explain expected goal involvement at first use.

**Why.** `writing.md › Getting started`: “Be clear.” `branding.md › Best practices`: “Ensure branding always defers to content.” The proposed wording and placement are editorial judgments, not prescribed Apple copy.

**Success check.** A visitor can identify the purpose, author and whose squad is shown without opening README. A source-code link is visible without reaching the footer.

### 2. High — Compose the weekly review and pitch as one first impression

**Evidence.** In the local 390×844 context, the hero is about **718px** tall; main tabs start at document y≈**906px**, and the pitch starts at y≈**1,208px**. At 320px these become **871px**, **1,059px** and **1,380px**. On desktop the hero is about **403px** tall, with the pitch starting at y≈753px. The desktop field spans about 1,368px while the formation occupies only its centre. See [dashboard.py](../../dashboard.py), hero and squad-pitch markup; [dashboard.css](../../dashboard.css), `.hero`, `.tiles`, `.pitch-panels` and final mobile rules.

**Change.** Put the main tabs above the substantial review. On desktop, place the review in roughly four of twelve columns and the team sheet in the other eight. Keep the review, all six facts, captain and transfer links. On phones, retain the hero but promote two headline figures and present the other four as compact label/value rows; shorten repeated action copy while keeping validity limits visible. Preserve shared pitch geometry across periods.

**Why.** `layout.md › Visual hierarchy`: “Order content by relative importance.” Side-by-side composition and the compact fact treatment are design judgments. They preserve the requested hero rather than repeat the rejected removal proposal.

**Success check.** At 390px, all four main destinations are visible near arrival and the team-sheet heading appears within the first viewport in a normal healthy-snapshot state. Test 320px and overdue/unavailable states separately; never meet the target by clipping text, shrinking essential labels or hiding warnings.

### 3. High — Give the interactive features a short, obvious path

**Evidence.** Planning opens with methodology, market context, an unconstrained XI and the knee-jerk card. In the desktop local snapshot, Suggested transfers begins around y≈1,963px and Captaincy around y≈3,223px. Scout filtering and comparison work, but the selected-count bar and comparison are after the table. With the unfiltered defender pool at 390px, the first selection is around y≈3,867px and the comparison begins around y≈7,229px: roughly **3,362px farther down**. See [dashboard.py](../../dashboard.py), Planning assembly around line 394; [cards_scout.py](../../cards_scout.py), explorer and shortlist ordering around lines 181–230.

**Change.** Lead Planning with captaincy and affordable moves, followed by their evidence and supporting market context. Keep the unconstrained XI, explicitly named as a benchmark. Put a visible **Explore & compare** entry beside Scout's shortlists. Move the existing selected-count controls above the table and provide **Compare 2 players** there, leading to the existing comparison. Keep selections under user control; do not auto-scroll on every tick.

**Why.** `layout.md › Visual hierarchy` supports progressive disclosure. `charts.md › Descriptive content` calls for a clear main message before detailed exploration. The exact ordering is a product judgment: demonstrate a useful decision, then let visitors inspect why.

**Success check.** A new visitor can reach a captain explanation or complete filter → select two → compare without searching below the full table. Existing filters, comparisons, benchmark and model limits remain available.

### 4. Medium — Give typography and cards a clearer hierarchy

**Evidence.** Product chrome is 18px, the desktop team title up to 34px, card titles 16px uppercase, finding titles 12px uppercase and hero labels 10px uppercase. Scout repeats “Worth a look” immediately above “Defenders worth a look”, and similarly repeats “Fixture runs”. Multiple borders, inset panels and uppercase labels make supporting content compete with primary content. Sampled text contrast is already sound: muted purple on white measured **5.81:1**, and a Scout caution measured **5.20:1**. This finding is about hierarchy and reading comfort, not an invented blanket contrast failure. See [dashboard.css](../../dashboard.css), card headers, tiles, findings and Scout styles.

**Change.** Retain Archivo and IBM Plex Mono. Use sentence case for card titles, reserving expanded display type for product/chapter hierarchy. Standardise explanatory text at 15–16px, secondary copy at 13px and card titles at 16px. Use 12px as a proposed floor for essential labels, rather than treating native point sizes as CSS rules. Remove duplicate section titles and unnecessary nested borders. Give each card one dominant answer before its evidence. Keep metric-specific precision and scope explicit.

**Why.** `typography.md › Conveying hierarchy` recommends distinguishing importance through weight, size and colour. `color.md › Best practices` supports consistent semantic colour roles. The proposed scale is a web design decision.

**Success check.** First answers read more strongly than labels and caveats, while caveats remain readable. Enlarge text and test narrow layouts; the type scale must not create cropped names or broken tables.

### 5. Medium — Finish navigation, control targets and feedback consistently

**Evidence.** Main tabs scroll away while a separate chapter rail remains sticky. Information buttons have **16×16px** hit boxes, the player-dialog close button is **32×32px**, and some Scout form controls are 28–30px tall. Existing positive behaviour matters: a hero captain link selected Planning, focused `#captaincy` and landed below the sticky header; a player dialog closed on Escape and restored focus; reduced-motion emulation changed sampled tab/card transition durations to 0s. See [dashboard.js](../../dashboard.js), tab/rail/jump handlers; [dashboard.css](../../dashboard.css), `.infobtn`, `.pv-close`, Scout controls and motion rules.

**Change.** Keep one predictable navigation area: main sections remain reachable while chapter links are subordinate. Expand frequent touch controls towards **44×44 CSS pixels**, allowing the visible icon to remain small. Make hover, pressed, selected and keyboard-focus treatments consistent. Use brief colour/opacity feedback around 140–180ms where it clarifies an action, keeping the existing short tab indicator and reduced-motion override. Preserve immediate response and stable layout. Do not add delays, entrance cascades or decorative movement to frequent actions.

**Why.** `accessibility.md › Mobility`: “Offer sufficiently sized controls.” `motion.md › Providing feedback`: “Aim for brevity and precision in feedback animations.” The 44px target is a proposed comfort target for this website, not a claim that every smaller control violates WCAG. This was not a complete accessibility audit.

**Success check.** Keyboard and touch users can change section, open details and return without losing their place. Small icons have comfortable hit areas without overlapping adjacent targets. Reduced motion still works. Verify settled tab geometry before diagnosing an indicator defect.

## What already works

- **A recognisable football identity.** Purple ink, bright green, warm paper, kits and pitch markings belong to this subject. The team sheet is a stronger signature than an abstract decorative hero.
- **A coherent foundation.** Two type families, tabular figures, reusable cards, semantic colour tokens and restrained shadows already exist. Keep them and tighten their application.
- **Real interaction depth.** Player breakdowns, Scout's filters/scatter/comparison, standings sorting and linked advice make this more demonstrable than a static report.
- **Credible limits.** Snapshot status, public-picks caveats, sample-size notes and model explanations make the project more convincing when legible and well placed.
- **Useful responsive repairs.** All four current-source tabs fit the sampled 320px and 390px contexts without document overflow. The pitch card retained the same measured height across all three periods, and only one season metric was visible per player.

## Concrete visual direction

**A matchday analysis desk:** a compact weekly briefing beside a recognisable team sheet, with evidence available directly from each decision. The pitch and the review supply the identity. Avoid adding a separate portfolio landing page or replacing the palette with a generic analytics theme.

Keep the existing light page and dark review surface. The following are roles on those surfaces, not a proposal for a new appearance toggle:

| Role | Light page | Dark review surface | Contrast |
|---|---|---|---|
| Ground | `#F4F1EA` | `#1E0021` for chrome | Purple text on paper: 15.16:1 |
| Card/surface | `#FFFFFF` | `#37003C` | White on purple: 17.11:1 |
| Main text | `#37003C` | `#FFFFFF` | Purple on white: 17.11:1 |
| Supporting text | `#7D5980` | `#C3B2C4` | 5.81:1 on white; 8.54:1 on purple |
| Action/selection | `#01FC7A` fill with purple text | `#01FC7A` text on purple | 12.39:1 for purple/green |
| Positive outcome | `#046B39` text | `#01FC7A` with a label/arrow | Dark green on white: 6.63:1 |

Bright green on white is only **1.38:1**: keep using the dark green ink for positive text on light surfaces. Existing warning, error, ownership, rival and market roles remain; do not replace meaningful chart categories with this six-role summary.

Type proposal: Archivo 32px desktop/26px mobile for the product statement, 22px chapters, 16px card titles, 15–16px body and 13px supporting copy; Plex Mono for headline data and aligned numeric columns. Preserve existing 8/12/16px radii, use an 8px spacing rhythm and align card edges. The exact layout should be checked with real changing data before implementation is final.

```text
Desktop
┌ Product purpose · Jonno Millar       Source · About/methods ┐
├ Squad | Planning | Mini-league | Scout                     ┤
├ Snapshot and public-squad status                           ┤
├ Weekly review (4 columns) ┬ Starting XI (8 columns)         ┤
│ Result + six facts        │ Period / figure controls       │
│ Captain + transfer links  │ Pitch + bench                  │
│ Visible validity limits   │ Open any player                │
├ Supporting evidence, grouped by the question it answers    ┤
└───────────────────────────────────────────────────────────┘

Phone
┌ Purpose / author / source ┐
├ Four main tabs            ┤
├ Snapshot status           ┤
├ Compact weekly review    ┤
│ Two headline figures     │
│ Four compact facts       │
│ Captain / transfer links │
│ Visible validity limits  │
├ Starting XI / controls    ┤
│ Pitch / bench             │
├ Evidence and details     ┤
└──────────────────────────┘
```

**Restraint check.** Remove repeated headings and competing inset treatments. Keep the requested hero and the useful data. This direction is specific to a personal football decision tool; its central team sheet and weekly result-to-action narrative would not transfer unchanged to an unrelated dashboard.

## Verification and next delivery gate

Sampled browser checks: all four tabs at 1440/390/320; three Scout positions; Arsenal team filtering (four results in the historical snapshot); two-player comparison and selection feedback; pitch periods; one-player metric visibility; hero captain destination/focus; main-tab keyboard activation; player dialog/Escape/focus restoration; standings Total sorting; reduced-motion styles. No errors were recorded in the checked local browser console. These are functional samples, not a frame-rate or performance benchmark.

Not verified: physical phones, Safari/Firefox, full screen-reader or accessibility coverage, enlarged-text/zoom behaviour, slow devices/networks, prediction accuracy or a fresh source build. Regression tests were not rerun for this documentation-only assessment. No app code, generated artifact, projections or price history changed.

Evidence screenshots are local review files under `.playwright-mcp/`, including `cv-apple-desktop.png`, `cv-apple-mobile.png`, `cv-current-arrival-{1440,390,320}.png`, per-tab desktop/phone captures, `cv-current-next-pitch-390.png`, `cv-current-player-390.png` and `cv-current-compare-1440.png`. They are not published application assets. The audit's temporary server is stopped after inspection.

Read bundled apple-design references: accessibility, layout, typography, color, motion, branding, charts, writing, cross-platform and code-audit. Guideline quotations above identify their file and heading; other recommendations are design judgment. No native-platform compliance claim is made.

Recommended implementation order: arrival/composition, decision discovery, then typography and control polish. Before publishing, use a fresh complete source build, regressions and browser checks of healthy and affected failure states, then integrate concurrent generated commits through the existing Git deployment. The direction here is proposed for Jonno's review; no implementation or publication approval is implied.
