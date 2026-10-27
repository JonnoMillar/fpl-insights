# Reference study: Sofascore and Gradient Sports on Instagram (27 October 2026)

Jonno named @sofascore_football (first) and @gradient_sports as the feel to aim for: stat graphics that are easy to take in at a glance. I looked at about 40 recent grid posts in Claude's browser while logged in to his account, skipping the Ballon d'Or posts (single-player portraits). Below is what makes them work, and what transfers to a dense, interactive dashboard. Nothing here is copied artwork; it is method.

## Sofascore

- **One claim per graphic, set as a headline.** "Defending is an art", "Three defenders in the top five", "Loving life in England", "Ready for a three-peat?". The headline is the insight; the table underneath is the evidence. Our cards are titled by the measure ("Big chances created"), so the reader has to find the point themselves.
- **Big, tight, sentence-case headline type.** Large grotesque at two or three lines, tight leading, left aligned, top left. Sub-line in small spaced caps (competition, round, season). Two text sizes do almost all the work.
- **Dark, near-black ground with one brand colour.** Charcoal/black panels, white type, Sofascore blue-violet for the rating box and the highlighted row. Accent used once or twice per graphic, never as a border stripe.
- **The rating box is the signature.** A small filled square with the number beside it, always both. The colour (blue for 9+, teal 8s, green 7s, yellow-orange 6s) repeats what the number says; it is never the only cue. That is the pattern we should keep for colour-blind safety, not their hue scale itself.
- **Player cut-outs bleed off the edge** and overlap the panel; the player is part of the layout, not a thumbnail in a box. Club crests and flags are small icons at row ends.
- **Tables are plain.** Rank, small face, name, two or three columns, one highlighted row (the subject) filled in the brand colour. Thin rules, no zebra, no card-in-card.
- **Mono/condensed spaced caps for stat labels** ("DEFENSIVE CONTRIBUTIONS 22") with the figure right-aligned. Very close to what our IBM Plex Mono figures already do.
- **Formats repeat.** Team of the week on a dark pitch with rating chips under faces; top-N list with one hero row enlarged; head-to-head comparison with the best value per row in bold white and the rest greyed. Same few templates, so the feed reads as one brand.

## Gradient Sports

- **Warm off-white paper, photo cut-out on top, table below.** The light counterpart of Sofascore's layout: subject photo fades into the paper, title sits where the fade ends.
- **Ranked list as the default graphic.** "1." to "10." in an orange-brown rank numeral, name in bold caps, a small position tag, value right-aligned and large, crest at the end. One stat per graphic ("Passing Grade", "Tackle Resistance Grade").
- **Emphasis by circling**, a hand-drawn orange loop around the one figure that matters (the 81.5% save rate, the 7 goals). One emphasis per graphic.
- **Two inks plus one accent**: near-black text, warm grey rules and captions, orange for ranks and the circle. Charts (scatter of passing grades) are dense but stay readable because everything except the labelled points is muted.
- **Small print is honest**: source, minutes floor and season in tiny caps at the foot, out of the way.

## What transfers to this dashboard

1. Headline each card with its finding, keep the measure as the small caps sub-line. ("Calafiori misses the most", not "Big chances missed".) This is a copy change as much as a design one.
2. One hero figure per card at a large size; the rest of the card is a plain list in two sizes.
3. Drop the coloured top/side edges, lilac card heads and lilac-in-lilac. Separation by ground colour and space, not stripes.
4. One emphasis device used consistently (filled highlight row, or a circle) instead of many tints.
5. A small set of repeatable templates: ranked list, hero-row list, head-to-head, pitch. Most existing cards already map onto one.
6. Number-plus-swatch for any rated value, never swatch alone. Use a blue/orange or lightness scale, not Sofascore's green-to-orange run.
7. Player photos larger and cut out where we have them; we already cache portraits.

## Open decision

Sofascore is dark; Gradient is light paper. The standing rule since 31 August is light only, with FPL purple and green kept flat. Options: a Gradient-style light paper page with Sofascore's headline/rating-box structure (fits the rule), or dark panels in the Sofascore manner (reverses it). Jonno's call before Claude Design exploration.
