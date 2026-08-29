#!/usr/bin/env python3
"""
Renders the squad and mini-league reports as a single self-contained HTML page.

Styling is not a pastiche of Fantasy Premier League - the tokens are lifted
from the live stylesheet at fantasy.premierleague.com (brand purple #37003c,
the mono-p neutral ramp, the radius and spacing scales, and the five-step
fixture-difficulty colours with their prescribed text colours). Both themes use
FPL's own light and dark mappings rather than an invented inversion.

Two deliberate departures:

* FPL sets type in PremierSans (PremierLeagueW01), a licensed Monotype face.
  Embedding it would mean redistributing it, so the page uses Barlow - the
  closest free analogue to that tight humanist grotesque - over FPL's own
  declared fallback stack of Arial / Helvetica Neue.
* Difficulty pills always carry a visible opponent and number. The bright green
  (#01fc7a) and grey (#e7e7e7) steps sit at 1.35:1 and 1.2:1 against a white
  surface, so colour alone would not be readable; the label is what carries it.
"""

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import analysis
import chips
import fplapi
import pulse
import elite
import ffs
import components
import odds
import ticker
import transfers
from analysis import f

# FPL's own fixture-difficulty scale, background and text, straight from their
# stylesheet. Difficulty is ordinal and diverging - kind through neutral to
# brutal - so the grey midpoint is correct rather than a gap in the palette.
FDR = {
    1: ("#375523", "#ffffff"),
    2: ("#01fc7a", "#37003c"),
    3: ("#e7e7e7", "#37003c"),
    4: ("#ff1751", "#000000"),
    5: ("#80072d", "#ffffff"),
}

TONE_COLOR = {
    "good": "var(--success)",
    "bad": "var(--error)",
    "warn": "#ff9800",
    "info": "var(--lilac)",
    "neutral": "var(--p60)",
}


def e(x):
    return html.escape(str(x), quote=True)


def fdr_pill(opp, home, diff):
    bg, fg = FDR.get(diff, ("#e7e7e7", "#37003c"))
    label = opp.upper() if home else opp.lower()
    venue = "home" if home else "away"
    return (
        f'<span class="fdr" style="background:{bg};color:{fg}" '
        f'title="{e(opp)} ({venue}), difficulty {diff} of 5">'
        f"{e(label)}<b>{diff}</b></span>"
    )


# Same five-step purple ramp and the same split used in the player-detail
# dialog's own fixture strip (playerview.js: csTone/xgTone) - a goalkeeper's
# or defender's points hinge on keeping the ball out, a midfielder's or
# forward's on their side scoring, so each is shaded by the stat that
# actually decides it. Kept as one scale in two places rather than derived,
# so a fixture reads the same color wherever a player appears on the page.
CS_TONE = [(45, "#1e0021", "#fff"), (36, "#41054b", "#fff"),
          (28, "#7d5980", "#fff"), (20, "#af99b1", "#37003c")]
XG_TONE = [(1.9, "#1e0021", "#fff"), (1.6, "#41054b", "#fff"),
          (1.3, "#7d5980", "#fff"), (1.0, "#af99b1", "#37003c")]
TONE_FALLBACK = ("#ebe5eb", "#37003c")


def _step_tone(value, steps):
    for edge, bg, fg in steps:
        if value >= edge:
            return bg, fg
    return TONE_FALLBACK


def pos_fixture_pill(pos, opp, home, cs, xg):
    by_attack = pos not in ("GKP", "DEF")
    bg, fg = _step_tone(xg, XG_TONE) if by_attack else _step_tone(cs, CS_TONE)
    label = opp.upper() if home else opp.lower()
    value = f"{xg:.2f}" if by_attack else f"{cs:.0f}%"
    venue = "home" if home else "away"
    return (
        f'<span class="fxpill" style="background:{bg};color:{fg}" '
        f'title="{e(opp)} ({venue}), {xg:.2f} expected goals, '
        f'{cs:.0f}% clean sheet">{e(label)}<b>{value}</b></span>'
    )


SPARK_ICON = (
    '<svg viewBox="0 0 24 24" class="pk-spark" aria-hidden="true">'
    '<path d="M4 17l5-6 4 3 6-8" fill="none" stroke="currentColor" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def meter(value, vmax, label):
    """A single-series magnitude bar. One hue, sequential - no legend needed,
    and the number is always printed beside it so the bar is never the only
    way to read the value."""
    pct = max(0.0, min(100.0, (value / vmax * 100) if vmax else 0))
    return (
        f'<span class="meter" title="{e(label)}">'
        f'<span class="meter-fill" style="width:{pct:.1f}%"></span></span>'
    )


CSS = """
:root{
  /* Brand + neutral ramp, verbatim from FPL's stylesheet */
  --purple:#37003c; --lilac:#953bff; --white:#ffffff;
  --p2:#faf9fa; --p5:#f5f2f5; --p10:#ebe5eb; --p20:#d7ccd8; --p30:#c3b2c4;
  --p40:#af99b1; --p50:#9b809d; --p60:#87668a; --p70:#7d5980; --p80:#541e5d;
  --p90:#41054b; --p100:#37003c; --p110:#28002b; --p120:#1e0021;
  --error:#e60023; --success:#34a853; --error-container:#fff2f4;
  /* FPL's light theme mapping */
  --surface:var(--white); --surface-variant:var(--p5);
  --on-surface:var(--purple); --on-surface-variant:var(--p70);
  --outline:var(--p30); --outline-variant:var(--p10);
  --ground:var(--p5); --bar:var(--purple); --on-bar:var(--white);
  --pitch-a:#0e7a3c; --pitch-b:#0a6733;
  --radius-xs:4px; --radius-s:8px; --radius-m:12px; --radius-l:16px;
  --shadow:0 1px 2px rgb(55 0 60 / 10%), 0 1px 8px rgb(55 0 60 / 6%);
}
/* FPL's dark theme mapping, not an inversion of the light one */
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --surface:var(--p110); --surface-variant:var(--p100);
    --on-surface:var(--white); --on-surface-variant:var(--p40);
    --outline:var(--p60); --outline-variant:var(--p80);
    --ground:var(--p120); --bar:var(--p110); --on-bar:var(--white);
    --pitch-a:#0b5c2e; --pitch-b:#084a25;
    --error-container:#40121c;
    --shadow:0 1px 2px rgb(0 0 0 / 40%), 0 1px 8px rgb(0 0 0 / 30%);
  }
}
:root[data-theme="dark"]{
  --surface:var(--p110); --surface-variant:var(--p100);
  --on-surface:var(--white); --on-surface-variant:var(--p40);
  --outline:var(--p60); --outline-variant:var(--p80);
  --ground:var(--p120); --bar:var(--p110); --on-bar:var(--white);
  --pitch-a:#0b5c2e; --pitch-b:#084a25;
  --error-container:#40121c;
  --shadow:0 1px 2px rgb(0 0 0 / 40%), 0 1px 8px rgb(0 0 0 / 30%);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--on-surface);
  font-family:'Barlow',Arial,'Helvetica Neue',sans-serif;
  font-size:15px; line-height:1.45;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3{margin:0; font-weight:700; text-wrap:balance; letter-spacing:-0.01em}
a{color:inherit}
.tnum{font-variant-numeric:tabular-nums}

/* --- app chrome --- */
.topbar{
  background:var(--bar); color:var(--on-bar);
  border-bottom:1px solid rgb(255 255 255 / 12%);
  position:sticky; top:0; z-index:20;
}
.topbar-in{
  max-width:1120px; margin:0 auto; padding:12px 16px;
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
}
.wordmark{
  font-weight:700; font-size:18px; letter-spacing:0.02em; text-transform:uppercase;
  display:flex; align-items:center; gap:8px;
}
.wordmark .dot{width:10px;height:10px;border-radius:50%;background:#01fc7a;flex:none}
.gw-chip{
  margin-left:auto; background:rgb(255 255 255 / 15%); color:var(--on-bar);
  border-radius:9999px; padding:4px 12px; font-size:13px; font-weight:600;
}
.stamp{font-size:12px;color:rgb(255 255 255 / 65%)}

.wrap{max-width:1120px;margin:0 auto;padding:16px}
section{margin-bottom:20px}
.card{
  background:var(--surface); border-radius:var(--radius-m);
  box-shadow:var(--shadow); overflow:hidden;
}
.card-head{
  padding:14px 16px; border-bottom:1px solid var(--outline-variant);
  display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
}
.card-head h2{font-size:16px; text-transform:uppercase; letter-spacing:0.04em}
.card-head .sub{font-size:13px;color:var(--on-surface-variant)}
.card-body{padding:16px}

/* --- hero --- */
.hero{
  background:linear-gradient(135deg,var(--purple) 0%, #4d0a55 60%, var(--lilac) 190%);
  color:#fff; border-radius:var(--radius-m); padding:20px 18px; box-shadow:var(--shadow);
}
.hero h1{font-size:clamp(22px,4vw,32px)}
.hero .mgr{color:rgb(255 255 255 / 72%); font-size:14px; margin-top:2px}

.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr)); gap:10px; margin-top:16px}
.tile{background:rgb(255 255 255 / 12%); border-radius:var(--radius-s); padding:10px 12px}
.tile .k{font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:rgb(255 255 255 / 70%)}
.tile .v{font-size:26px; font-weight:700; line-height:1.1; margin-top:2px}
.tile .n{font-size:12px; color:rgb(255 255 255 / 65%)}

/* --- tabs --- */
.tabs{display:flex; gap:4px; margin:16px 0 12px; flex-wrap:wrap}
.tab{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface); font:inherit; font-weight:600; font-size:14px;
  padding:8px 16px; border-radius:9999px; cursor:pointer;
}
.tab[aria-selected="true"]{background:var(--purple); color:#fff; border-color:var(--purple)}
:root[data-theme="dark"] .tab[aria-selected="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .tab[aria-selected="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
}
.tab:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.panel[hidden]{display:none}

/* --- pick-team pitch toggle: a nested, quieter version of .tab/.tabs,
   scoped inside one card rather than switching the whole page --- */
.pkview{display:flex; gap:6px; padding:10px 16px; border-bottom:1px solid var(--outline-variant)}
.pkbtn{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface-variant); font:inherit; font-weight:600; font-size:12px;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.pkbtn[aria-selected="true"]{background:var(--purple); color:#fff; border-color:var(--purple)}
:root[data-theme="dark"] .pkbtn[aria-selected="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .pkbtn[aria-selected="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
}
.pkbtn:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.pkpanel[hidden]{display:none}

/* --- pitch --- */
.pitch{
  background:
    repeating-linear-gradient(180deg,var(--pitch-a) 0 60px,var(--pitch-b) 60px 120px);
  padding:18px 10px; position:relative;
}
.pitch::before{
  content:""; position:absolute; inset:10px; border:2px solid rgb(255 255 255 / 22%);
  border-radius:var(--radius-xs); pointer-events:none;
}
.row{display:flex; justify-content:center; gap:8px; flex-wrap:wrap; margin-bottom:14px; position:relative}
.row:last-child{margin-bottom:0}
.pl{position:relative; width:92px; background:var(--surface); border-radius:var(--radius-s); overflow:hidden; box-shadow:0 2px 6px rgb(0 0 0 / 25%)}
.pl .crest{display:flex; align-items:center; justify-content:center; height:44px; background:var(--surface-variant)}
.pl .crest img{width:32px;height:32px;object-fit:contain}
.pl .crest .letters{font-weight:700;font-size:13px;color:var(--on-surface-variant)}
.pl .nm{
  background:var(--purple); color:#fff; font-size:12px; font-weight:600;
  padding:3px 4px; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.pl .sc{display:flex; font-size:12px; text-align:center}
.pl .sc div{flex:1; padding:3px 2px}
.pl .sc .p{font-weight:700}
.pl .sc .x{color:var(--on-surface-variant); border-left:1px solid var(--outline-variant)}
.pl .arm{
  /* The card clips to its rounded corners, so the armband sits inside it
     rather than hanging off the edge where overflow:hidden would slice it. */
  position:absolute; top:3px; left:3px; z-index:2; width:19px;height:19px;border-radius:50%;
  background:#01fc7a; color:#37003c; font-size:11px; font-weight:700;
  display:grid; place-items:center; box-shadow:0 1px 3px rgb(0 0 0 / 35%);
}
.pl.out .crest{opacity:.45}

/* --- pick-team card: the .pl shirt card, widened for a fixture chip and a
   one-line form read --- */
.pk{width:108px}
.pk-fx{padding:3px 4px 0; display:flex; justify-content:center}
.fxpill{
  display:inline-flex; align-items:center; gap:3px; border-radius:var(--radius-xs);
  padding:2px 6px; font-size:10px; font-weight:700;
}
.fxpill b{font-weight:800; opacity:.85}
.pk-form{
  font-size:10px; line-height:1.3; text-align:center; padding:2px 5px 5px;
  color:var(--on-surface-variant);
}
.pk-form.hot{color:var(--purple); font-weight:700}
:root[data-theme="dark"] .pk-form.hot{color:var(--lilac)}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .pk-form.hot{color:var(--lilac)}
}
.pk-spark{width:11px; height:11px; vertical-align:-1px; margin-right:2px}
.benchstrip{background:var(--surface-variant); padding:12px 10px}
.benchstrip .lbl{
  font-size:11px; text-transform:uppercase; letter-spacing:0.06em;
  color:var(--on-surface-variant); text-align:center; margin-bottom:8px; font-weight:600;
}

/* --- collapsible cards --- */
/* A card that is also a <details>. The generic `details summary` rules below
   supply the chevron; these restore the card-head look the plain <div> had,
   and drop the row divider a card should not have. */
details.card{border-bottom:none}
details.collapsible > summary.card-head{cursor:pointer; list-style:none}
details.collapsible > summary.card-head::-webkit-details-marker{display:none}
details.collapsible > summary.card-head:hover{background:var(--surface-variant)}
details.collapsible > summary.card-head:focus-visible{outline:3px solid var(--lilac); outline-offset:-3px}
details.collapsible:not([open]) > summary.card-head{border-bottom:none}

/* --- predicted line-ups (Fantasy Football Scout) --- */
.pl .pip{
  position:absolute; top:3px; right:3px; z-index:2;
  width:9px; height:9px; border-radius:50%;
  box-shadow:0 0 0 2px var(--surface);
}
.pip-in{background:#01fc7a}
.pip-out{background:var(--error)}
.lu{
  display:inline-block; padding:2px 8px; border-radius:9999px;
  font-size:11px; font-weight:700; white-space:nowrap;
}
.lu-in{background:#01fc7a; color:#37003c}
.lu-out{background:var(--error); color:#fff}
.lu-unk{color:var(--on-surface-variant); font-weight:400}

/* --- tables --- */
.scroll{overflow-x:auto}
table{border-collapse:collapse; width:100%; font-size:14px}
th,td{padding:8px 10px; text-align:left; white-space:nowrap}
thead th{
  font-size:11px; text-transform:uppercase; letter-spacing:0.05em;
  color:var(--on-surface-variant); border-bottom:1px solid var(--outline);
  background:var(--surface); position:sticky; top:0;
}
th.sortable{cursor:pointer; user-select:none}
th.sortable:hover{color:var(--on-surface)}
th.sortable::after{content:"\\2195"; opacity:.35; margin-left:4px}
th.sortable[aria-sort="ascending"]::after{content:"\\2191"; opacity:1}
th.sortable[aria-sort="descending"]::after{content:"\\2193"; opacity:1}
tbody tr{border-bottom:1px solid var(--outline-variant)}
tbody tr:hover{background:var(--surface-variant)}
tbody tr.me{background:color-mix(in srgb, var(--lilac) 12%, transparent)}
td.num,th.num{text-align:right; font-variant-numeric:tabular-nums}
.pos{
  display:inline-block; min-width:34px; text-align:center; font-size:11px; font-weight:700;
  border-radius:var(--radius-xs); padding:2px 5px;
  background:var(--surface-variant); color:var(--on-surface-variant);
}
.fdr{
  display:inline-flex; align-items:center; gap:3px; border-radius:var(--radius-xs);
  padding:2px 6px; font-size:11px; font-weight:600; margin-right:3px;
}
.fdr b{font-weight:700; opacity:.75}
.meter{
  display:inline-block; width:56px; height:6px; border-radius:9999px;
  background:var(--outline-variant); vertical-align:middle; overflow:hidden;
}
.meter-fill{display:block; height:100%; background:var(--lilac); border-radius:9999px}
.flag{font-size:11px; font-weight:700; color:var(--error)}

/* --- price watch --- */
.pw-cols{display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:20px}
.pw-h{font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--on-surface-variant); margin-bottom:8px}
.pw-list{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:12px}
.pw-top{display:flex; align-items:baseline; gap:8px}
.pw-name{font-weight:600; font-size:14px; display:flex; flex-direction:column}
.pw-meta{font-weight:400; font-size:12px; color:var(--on-surface-variant)}
.pw-pct{margin-left:auto; font-weight:700; font-size:14px; white-space:nowrap}
.pw-bar{display:block; height:6px; border-radius:9999px; background:var(--outline-variant); margin:5px 0 3px; overflow:hidden}
.pw-fill{display:block; height:100%; border-radius:9999px}
.pw-foot{font-size:12px; color:var(--on-surface-variant); font-variant-numeric:tabular-nums}
.tag{display:inline-block; margin-left:6px; padding:1px 7px; border-radius:9999px; font-size:11px; font-weight:700}
.tag-now{background:var(--error); color:#fff}
.tag-mine{background:var(--lilac); color:#fff}
.pw-alert{
  background:var(--surface-variant); border-left:4px solid var(--lilac);
  border-radius:var(--radius-s); padding:10px 14px; margin-bottom:16px; font-size:14px;
}

/* --- scatter --- */
:root{--mark-mkt:#87668a; --mark-mine:#953bff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--mark-mkt:#87668a; --mark-mine:#b57bff}}
:root[data-theme="dark"]{--mark-mkt:#87668a; --mark-mine:#b57bff}
.chartfilter{display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px}
.chip{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface); font:inherit; font-size:13px; font-weight:600;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.chip[aria-pressed="true"]{background:var(--purple); color:#fff; border-color:var(--purple)}
:root[data-theme="dark"] .chip[aria-pressed="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .chip[aria-pressed="true"]{background:var(--white); color:var(--purple); border-color:var(--white)}
}
.chip:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.scatter{width:100%; min-width:560px; height:auto; display:block}
.scatter .grid line{stroke:var(--outline-variant); stroke-width:1}
.scatter .axlab text{fill:var(--on-surface-variant); font-size:11px; font-variant-numeric:tabular-nums}
.scatter .axtitle{fill:var(--on-surface-variant); font-size:12px; font-weight:600}
.scatter .mkt circle{fill:var(--mark-mkt); opacity:.55}
.scatter .mine circle{fill:var(--mark-mine); stroke:var(--surface); stroke-width:2}
.scatter .pt{cursor:pointer}
.scatter .pt:hover circle{opacity:1; stroke:var(--on-surface); stroke-width:2}
.scatter .ptlabel{
  fill:var(--on-surface); font-size:11px; font-weight:600; pointer-events:none;
  paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round;
}
.scatter .hide{display:none}

/* The enlarged hit target must out-specify the mark fill rules above,
   or it paints as a second, much fatter dot. */
.scatter .mkt circle.hit, .scatter .mine circle.hit{
  fill:transparent; opacity:0; stroke:none;
}
.scatter .pt:focus{outline:none}
.scatter .pt:focus-visible circle:first-child{stroke:var(--lilac); stroke-width:3}
.scatter .selring{fill:none; stroke:var(--on-surface); stroke-width:2}
.scatter .selname{
  fill:var(--on-surface); font-size:12px; font-weight:700;
  paint-order:stroke; stroke:var(--surface); stroke-width:3.5px; stroke-linejoin:round;
}
.readout{
  margin:12px 0 0; font-size:14px; min-height:1.4em;
  color:var(--on-surface-variant); font-variant-numeric:tabular-nums;
}
.readout b{color:var(--on-surface)}
.legend{display:flex; align-items:center; gap:6px; flex-wrap:wrap; font-size:12px; color:var(--on-surface-variant); margin:10px 0 0}
.key{width:10px; height:10px; border-radius:50%; display:inline-block; margin-left:10px}
.key.mkt{background:var(--mark-mkt)}
.key.mine{background:var(--mark-mine)}

/* --- ownership doughnuts + carousel --- */
.carnav{margin-left:auto; display:flex; gap:6px}
.arrow{
  appearance:none; width:32px; height:32px; border-radius:50%;
  border:1px solid var(--outline); background:var(--surface); color:var(--on-surface);
  font-size:18px; line-height:1; cursor:pointer; font-family:inherit;
}
.arrow:hover{background:var(--surface-variant)}
.arrow:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.carousel{
  list-style:none; margin:0; padding:4px; display:flex; gap:12px;
  overflow-x:auto; scroll-snap-type:x mandatory; scroll-behavior:smooth;
}
.carousel:focus-visible{outline:3px solid var(--lilac); outline-offset:2px; border-radius:var(--radius-s)}
.ocard{
  flex:0 0 148px; scroll-snap-align:start; text-align:center;
  background:var(--surface-variant); border-radius:var(--radius-m);
  padding:12px 8px; border:2px solid transparent;
}
.ocard.mine{border-color:var(--lilac); background:var(--surface)}
.donut{width:90px; height:90px; display:block; margin:0 auto}
.dtrack{fill:none; stroke:var(--outline-variant); stroke-width:9}
.dval{fill:none; stroke-width:9; stroke-linecap:round}
.dnum{fill:var(--on-surface); font-size:19px; font-weight:700}
.dsub{fill:var(--on-surface-variant); font-size:11px}
.oname{margin:8px 0 0; font-weight:700; font-size:14px}
.oteam,.onote{margin:1px 0 0; font-size:11px; color:var(--on-surface-variant)}
.oyou{margin:4px 0 0; font-size:11px; font-weight:700; color:var(--lilac)}
.tnote{
  margin:18px 0 8px; font-size:13px; font-weight:600;
  color:var(--on-surface-variant);
}
.tnote:first-child{margin-top:0}
@media (prefers-reduced-motion:reduce){.carousel{scroll-behavior:auto}}

/* Only the handful near 100% matter - the rest are there if you want them.
   Roughly four rows deep, then scroll. */
.pw-scroll{max-height:296px; overflow-y:auto; padding-right:8px}
.pw-scroll::-webkit-scrollbar{width:8px}
.pw-scroll::-webkit-scrollbar-thumb{background:var(--outline); border-radius:9999px}

/* --- findings: lead line, then detail --- */
.find li{margin-bottom:8px; line-height:1.35}
.find .lead{font-weight:700; display:block}
.find .det{color:var(--on-surface-variant); font-size:13px}

.axpick{display:flex; align-items:center; gap:6px; font-size:13px; font-weight:600}
.axpick select{
  font:inherit; font-size:13px; padding:5px 8px; border-radius:var(--radius-s);
  border:1px solid var(--outline); background:var(--surface); color:var(--on-surface);
}
.axpick select:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.chartfilter .spacer{flex:1 1 12px}

/* --- fixture ticker --- */
.tk-controls{padding-bottom:0}
.tk-hint{margin:6px 0 12px; font-size:12px; color:var(--on-surface-variant)}
.tktable td.tick{min-width:56px}
.tktable thead th{white-space:nowrap}
.tick{
  text-align:center; padding:5px 7px; border-radius:var(--radius-xs);
  font-size:11px; font-weight:600; line-height:1.25; min-width:52px;
}
.tk-opp{display:block; font-weight:700}
.tk-val{display:block; opacity:.88; font-variant-numeric:tabular-nums}
.tkclub{white-space:nowrap}
table td.tick{border:2px solid var(--surface)}

/* --- kits, portraits, set pieces --- */
.pl .crest img.kit{width:40px; height:40px; object-fit:contain}
.pl .crest img.crestimg{width:32px; height:32px; object-fit:contain}
.pl .crest{height:48px}
.pv-photo{
  width:66px; height:84px; border-radius:var(--radius-s); object-fit:cover;
  background:var(--surface-variant); flex:none;
}
.spwrap{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px;
  padding:0 14px}
.spgroup h4{
  margin:0 0 6px; font-size:12px; text-transform:uppercase; letter-spacing:.05em;
  color:var(--on-surface-variant); display:flex; align-items:center; gap:7px;
}
.spicon{width:17px; height:17px; flex:none; color:var(--lilac)}
.splist{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:5px}
.splist li{display:flex; align-items:baseline; gap:8px; font-size:13px}
.sprank{
  flex:none; width:19px; height:19px; border-radius:50%; font-size:11px;
  font-weight:700; display:grid; place-items:center;
  background:var(--surface-variant); color:var(--on-surface-variant);
}
.splist li.first .sprank{background:var(--lilac); color:#fff}
.spname{font-weight:600}
.spteam{margin-left:auto; color:var(--on-surface-variant); font-size:11px}
.mkt-cs,.mkt-xg{color:var(--lilac); font-weight:700}

/* --- expected points: the bars slide out sideways --- */
.epwrap{display:flex; gap:14px; align-items:stretch}
/* Collapsed, the list is only as wide as a name and a total need - it must
   not flex-grow, or it stretches across the whole card and leaves every row
   pushed to the left with dead space trailing it before the toggle. Open,
   the bars need the room, so growth turns back on. */
.eplist{flex:0 1 auto; min-width:0}
.epcard.open .eplist{flex:1 1 auto}
/* No length is transitioned here, deliberately. Chrome would not interpolate
   the grid track between 0fr and 1fr, and a max-width transition got stuck at
   its start value - in both cases the bars simply never appeared. So the
   layout snaps (flex-grow 0 to 1, instant) and every bit of the motion comes
   from a transform, which is reliable and cheap to composite. */
.epcard .epr{display:flex; align-items:center; gap:12px}
.epcard .epname{flex:0 0 150px}
.epcard .eptot{flex:0 0 52px; text-align:right}
.epcard .epbar{flex:0 0 0px; min-width:0; overflow:hidden}
.epcard.open .epbar{flex:1 1 auto}

/* The space collapsing frees up, filled with the one thing worth surfacing
   at a glance: who to captain. Gone once the bars themselves need the room. */
.epcap{
  flex:1 1 auto; display:flex; flex-direction:column; justify-content:center;
  gap:1px; padding-left:14px; border-left:1px solid var(--outline-variant);
  min-width:0;
}
.epcard.open .epcap{display:none}
.epcap-k{font-size:10px; text-transform:uppercase; letter-spacing:.06em;
  font-weight:700; color:var(--on-surface-variant)}
.epcap-name{font-size:16px; font-weight:700}
.epcap-fx{font-size:12px; color:var(--on-surface-variant)}
.epcap-v{font-size:13px; margin-top:3px}
.epcap-v b{font-size:18px}
.epcap-arm{color:var(--on-surface-variant); font-size:12px; margin-left:2px}
@media (max-width:560px){.epcap{display:none}}
/* The reveal is driven from JavaScript rather than a keyframe. A delayed CSS
   animation with fill-mode both holds its opening frame, and that kept the
   bars pinned at scaleX(0); the Web Animations API with fill "none" cannot
   leave anything stuck, because the element returns to its own styles the
   moment the animation ends. */
.epcard .epbar{transform-origin:left center}
.epmore{
  appearance:none; flex:0 0 62px; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:6px;
  background:var(--surface-variant); border:1px solid var(--outline-variant);
  color:var(--on-surface-variant); font:inherit; font-size:11px; font-weight:700;
  text-transform:uppercase; letter-spacing:.04em; line-height:1.25;
  border-radius:var(--radius-s); cursor:pointer;
  transition:background .2s ease, color .2s ease;
}
.epmore:hover{background:var(--outline-variant); color:var(--on-surface)}
.epmore:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.epchev{width:15px; height:15px; transition:transform .3s ease}
.epcard.open .epchev{transform:rotate(180deg)}

@media (prefers-reduced-motion:reduce){

  .epchev{transition:none}
}

.rpill{
  display:inline-flex; align-items:center; gap:4px; border-radius:var(--radius-xs);
  padding:2px 7px; font-size:11px; font-weight:700; margin-right:4px;
}
.rpill b{font-weight:800; font-variant-numeric:tabular-nums; opacity:.85}

/* --- odds tiles --- */
.oilist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); gap:12px}
.oi{
  position:relative; padding:14px 14px 12px; border-radius:var(--radius-m);
  background:var(--surface-variant); border-top:3px solid var(--oi-tone);
}
.oi-icon{width:20px; height:20px; color:var(--oi-tone)}
.oi-good{--oi-tone:var(--success)}
.oi-bad{--oi-tone:var(--error)}
.oi-info{--oi-tone:var(--lilac)}
.oi-label{margin:6px 0 0; font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.oi-value{margin:3px 0 0; font-size:27px; font-weight:700; line-height:1;
  font-variant-numeric:tabular-nums; display:flex; align-items:baseline; gap:6px}
.oi-value small{font-size:10px; font-weight:600; text-transform:uppercase;
  letter-spacing:.04em; color:var(--on-surface-variant)}
.oi-who{margin:8px 0 0; font-size:13px; font-weight:700}
.oi-detail{margin:1px 0 0; font-size:11px; color:var(--on-surface-variant)}

/* --- chip planner --- */
.cplist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px;
  align-items:start}
.cp{
  position:relative; padding:14px 14px 12px; border-radius:var(--radius-m);
  background:var(--surface-variant); border-top:3px solid var(--lilac);
}
.cp.used{opacity:.55}
.cp-label{margin:0; font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.cp-gw{margin:4px 0 0; font-size:22px; font-weight:700; font-variant-numeric:tabular-nums}
.cp-reason{margin:4px 0 0; font-size:13px; color:var(--on-surface-variant)}
.cp-conf{
  display:inline-block; margin-top:8px; padding:2px 8px; border-radius:9999px;
  font-size:11px; font-weight:700;
}
.cp-conf-strong{background:var(--success); color:#fff}
.cp-conf-watch{background:var(--p40); color:var(--purple)}
.cp-conf-flexible{background:var(--outline-variant); color:var(--on-surface-variant)}
.cp-used-tag{font-size:11px; color:var(--on-surface-variant); margin-top:8px}

/* If the count does not fill the last row, the final card stretches across
   what is left rather than sitting beside a hole. */
.slwrap > :last-child:nth-child(3n+2){grid-column:span 2}
.prlist > :last-child:nth-child(2n+1){grid-column:span 2}
@media (max-width:900px){
  .slwrap > :last-child:nth-child(3n+2){grid-column:auto}
  .prlist > :last-child:nth-child(2n+1){grid-column:auto}
  .slwrap{grid-template-columns:repeat(2,minmax(0,1fr))}
  .prlist{grid-template-columns:minmax(0,1fr)}
}
@media (max-width:560px){.slwrap{grid-template-columns:minmax(0,1fr)}}

/* --- fixture difficulty --- */
.fxtable td.fxc{
  text-align:center; padding:6px 8px; border:2px solid var(--surface);
  border-radius:var(--radius-xs); min-width:58px; line-height:1.2;
}
.fxc-opp{display:block; font-size:11px; font-weight:700}
.fxc-score{display:block; font-size:13px; font-weight:700;
  font-variant-numeric:tabular-nums}
.fx-mkt{
  display:inline-block; width:4px; height:4px; border-radius:50%;
  background:currentColor; margin-left:4px; vertical-align:middle; opacity:.75;
}
.fxclub{white-space:nowrap}
.fxavg{
  display:inline-block; padding:4px 9px; border-radius:9999px;
  font-weight:700; font-variant-numeric:tabular-nums;
}
.fxtable thead th{white-space:nowrap}

/* --- priced round --- */
.mlist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px}
.mcard{background:var(--surface-variant); border-radius:var(--radius-m); padding:13px}
.mteams{display:flex; align-items:baseline; gap:7px; margin-bottom:9px}
.mt{font-weight:700; font-size:15px}
.mt.mine{color:var(--lilac)}
.mvs{font-size:11px; color:var(--on-surface-variant)}
.mtotal{margin-left:auto; font-size:17px; font-weight:700;
  display:flex; flex-direction:column; align-items:flex-end; line-height:1}
.mtotal small{font-size:9px; font-weight:600; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.mbar{display:flex; height:9px; border-radius:9999px; overflow:hidden;
  background:var(--outline-variant)}
.mbar .mb-seg{display:block; height:100%; box-shadow:inset -2px 0 0 var(--surface-variant)}
.mbar .mb-seg:last-child{box-shadow:none}
.mkeys{display:flex; justify-content:space-between; margin-top:4px;
  font-size:10px; color:var(--on-surface-variant);
  font-variant-numeric:tabular-nums}
.mstats{margin:11px 0 0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(78px,1fr)); gap:7px}
.mstat{display:flex; flex-direction:column}
.mstat dt{font-size:9px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--on-surface-variant)}
.mstat dd{margin:0; font-size:15px; font-weight:700;
  font-variant-numeric:tabular-nums}
.mfoot{margin:10px 0 0; font-size:10px; color:var(--on-surface-variant)}

/* --- transfer pairings --- */
.prlist{list-style:none; margin:0; padding:0; display:grid;
  /* Four pairings divide as 2x2 for the same reason. */
  grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px}
.pr-card{background:var(--surface-variant); border-radius:var(--radius-m); padding:14px}
.pr-head{display:flex; gap:14px; align-items:flex-end; margin-bottom:12px}
.pr-total,.pr-hit,.pr-bank{display:flex; flex-direction:column;
  font-variant-numeric:tabular-nums; line-height:1.05}
.pr-total{font-size:24px; font-weight:700; color:var(--success)}
.pr-hit{font-size:15px; font-weight:700; color:var(--on-surface-variant)}
.pr-bank{font-size:15px; font-weight:700; margin-left:auto; color:var(--on-surface-variant)}
.pr-head small{font-size:9px; font-weight:600; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant); margin-top:2px}
.pr-legs{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:10px}
.pr-leg{display:flex; align-items:center; gap:8px}
.pr-face{display:flex; align-items:center; gap:7px; flex:1 1 0; min-width:0}
.pr-frame{position:relative; flex:none}
.pr-photo{width:44px; height:56px; border-radius:var(--radius-xs);
  object-fit:cover; background:var(--surface); display:block}
.pr-blank{display:grid; place-items:center; font-size:19px; font-weight:700;
  color:var(--on-surface-variant)}
.pr-kit{position:absolute; right:-5px; bottom:-4px; width:18px; height:18px;
  border-radius:50%; background:var(--surface); padding:1px}
.pr-out .pr-photo{filter:grayscale(.75) opacity(.7)}
.pr-name{font-size:12px; font-weight:600; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap}
.pr-arrow{flex:none; width:28px; color:var(--on-surface-variant)}
.pr-arrow svg{width:28px; height:12px; display:block}
.pr-gain{flex:none; font-size:12px; font-weight:700; color:var(--success);
  font-variant-numeric:tabular-nums}
.pr-foot{margin:12px 0 0; font-size:11px}
.pr-yes{color:var(--success); font-weight:700}
.pr-no{color:var(--on-surface-variant)}

/* --- league template pitch + differentials --- */
.tplpitch .pl{width:86px}
.tplpitch .pl .sc .p{font-size:11px}
.pl.tpl-mine{outline:2px solid var(--lilac); outline-offset:1px}
.dflist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px}
.df-card{display:flex; gap:14px; align-items:center;
  background:var(--surface-variant); border-radius:var(--radius-m); padding:12px}
.df-photo{width:84px; height:106px; border-radius:var(--radius-s);
  object-fit:cover; background:var(--surface); flex:none}
.df-blank{display:grid; place-items:center; font-size:34px; font-weight:700;
  color:var(--on-surface-variant)}
.df-body{min-width:0}
.df-name{margin:0; font-size:18px; font-weight:700}
.df-meta{margin:2px 0 10px; font-size:12px; color:var(--on-surface-variant)}
.df-stats{margin:0; display:flex; gap:16px}
.df-stats div{display:flex; flex-direction:column}
.df-stats dt{font-size:10px; text-transform:uppercase; letter-spacing:.05em;
  color:var(--on-surface-variant)}
.df-stats dd{margin:0; font-size:17px; font-weight:700;
  font-variant-numeric:tabular-nums}
.dfempty{margin:0; font-size:14px; color:var(--on-surface-variant); max-width:56ch}

/* --- league leaders --- */
.slwrap{
  list-style:none; margin:0; padding:0; display:grid;
  /* Six leaders divide as 3x2. Left to auto-fit they wrapped 5 + 1, which put
     a lone card beside a long empty gap. */
  grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px;
}
.slcard{
  background:var(--surface-variant); border-radius:var(--radius-m);
  padding:12px 12px 10px; border-top:3px solid var(--accent);
}
.slcard h4{
  margin:0; font-size:12px; text-transform:uppercase; letter-spacing:.04em;
  display:flex; align-items:center; gap:7px; color:var(--accent);
}
.slicon{width:17px; height:17px; flex:none}
.slnote{margin:2px 0 8px; font-size:11px; color:var(--on-surface-variant)}
.sllist{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:4px}
.sllist li{display:flex; align-items:baseline; gap:6px; font-size:13px}
.slrank{
  flex:none; width:16px; height:16px; border-radius:50%; font-size:10px;
  font-weight:700; display:grid; place-items:center;
  background:var(--outline-variant); color:var(--on-surface-variant);
}
.sllist li.mine .slrank{background:var(--accent); color:#fff}
.sllist li.mine .slname{font-weight:700}
.slname{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.slteam{font-size:10px; color:var(--on-surface-variant)}
.slval{margin-left:auto; font-weight:700; font-variant-numeric:tabular-nums}
.findnote{
  margin:0 0 12px; padding:9px 13px; font-size:13px;
  color:var(--on-surface-variant); background:var(--surface);
  border-left:3px solid var(--outline); border-radius:var(--radius-s);
}

/* --- suggested transfers --- */
.tflist{
  list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px;
}
.tf-card{
  background:var(--surface-variant); border-radius:var(--radius-m);
  padding:16px 14px 12px; position:relative; overflow:hidden;
}
/* A quiet bar along the top, scaled to how big this swap is against the
   biggest on offer - rank without another number to read. */
.tf-card::before{
  content:""; position:absolute; top:0; left:0; height:3px; width:var(--gain);
  background:linear-gradient(90deg,var(--lilac),#01fc7a);
}
.tf-swap{display:flex; align-items:flex-start; gap:8px}
.tf-face{flex:1 1 0; text-align:center; min-width:0}
.tf-frame{position:relative; width:72px; margin:0 auto}
.tf-photo{
  width:72px; height:92px; border-radius:var(--radius-s); object-fit:cover;
  background:var(--surface); display:block;
}
.tf-blank{
  display:grid; place-items:center; font-size:30px; font-weight:700;
  color:var(--on-surface-variant);
}
.tf-kit{
  position:absolute; right:-8px; bottom:-6px; width:26px; height:26px;
  border-radius:50%; background:var(--surface); padding:2px;
  box-shadow:0 1px 4px rgb(0 0 0 / 25%);
}
.tf-out .tf-photo{filter:grayscale(.75) opacity(.72)}
.tf-name{margin:10px 0 0; font-weight:700; font-size:14px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.tf-meta{margin:1px 0 0; font-size:11px; color:var(--on-surface-variant)}
.tf-mid{
  flex:0 0 76px; display:flex; flex-direction:column; align-items:center;
  gap:6px; padding-top:32px;
}
.tf-arrow{display:block; width:40px; color:var(--on-surface-variant)}
.tf-arrow svg{width:40px; height:16px; display:block}
.tf-money{font-size:12px; font-weight:700; padding:2px 8px; border-radius:9999px}
.tf-free{background:var(--outline-variant); color:var(--on-surface-variant)}
.tf-cost{background:#fde2e7; color:#a3001b}
.tf-save{background:#d9f7e7; color:#00663a}
.tf-numbers{
  display:grid; grid-template-columns:1fr auto 1fr; align-items:center;
  gap:10px; margin-top:14px;
}
.tf-ep{display:flex; flex-direction:column; gap:4px; font-size:12px;
  color:var(--on-surface-variant); font-variant-numeric:tabular-nums}
.tf-ep-in{text-align:right}
.tf-track{display:block; height:5px; border-radius:9999px;
  background:var(--outline-variant); overflow:hidden}
.tf-track i{display:block; height:100%; background:var(--p40); border-radius:9999px}
.tf-ep-in .tf-track{transform:scaleX(-1)}
.tf-ep-in .tf-track i{background:var(--lilac)}
.tf-gain{
  font-size:19px; font-weight:700; color:var(--success); text-align:center;
  line-height:1.05; font-variant-numeric:tabular-nums;
}
.tf-gain small{display:block; font-size:10px; font-weight:600;
  text-transform:uppercase; letter-spacing:.04em; color:var(--on-surface-variant)}
.tf-foot{margin:12px 0 0; font-size:11px; color:var(--on-surface-variant);
  text-align:center}
.tf-elite{font-weight:600; color:var(--lilac)}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .tf-cost{background:#4a1120; color:#ff9db0}
  :root:not([data-theme="light"]) .tf-save{background:#0d3d28; color:#6fe3ad}
}
:root[data-theme="dark"] .tf-cost{background:#4a1120; color:#ff9db0}
:root[data-theme="dark"] .tf-save{background:#0d3d28; color:#6fe3ad}

/* --- expected points, stacked --- */
.eplist{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:10px}
.epr{display:grid; align-items:center; gap:12px}
.epname{font-weight:700; font-size:14px; line-height:1.2}
.epfx{display:block; font-weight:400; font-size:11px; color:var(--on-surface-variant)}
.epbar{
  display:flex; height:16px; border-radius:9999px; overflow:hidden;
  background:var(--outline-variant);
}
.epbar.wide{height:20px; margin-top:6px}
.epbar .seg{display:block; height:100%; box-shadow:inset -2px 0 0 var(--surface)}
.epbar .seg:last-child{box-shadow:none}
.eptot{text-align:right; font-weight:700; font-size:15px}
.eplegend{
  display:flex; flex-wrap:wrap; gap:14px; margin:14px 0 0;
  font-size:12px; color:var(--on-surface-variant);
}
.epkey{display:flex; align-items:center; gap:6px}
.epkey i{width:10px; height:10px; border-radius:3px; display:inline-block}
.epkey i.k-a{background:var(--on-surface)}
.epkey i.k-x{background:var(--outline); border:2px solid var(--on-surface-variant)}
.eprows{list-style:none; margin:10px 0 0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(132px,1fr)); gap:4px 14px}
.eprows li{display:flex; align-items:center; gap:7px; font-size:13px}
.eprows i{width:10px; height:10px; border-radius:3px; flex:none}
.eprows b{margin-left:auto; font-variant-numeric:tabular-nums}

/* --- dumbbell + threshold bars --- */
.gapcard{padding-bottom:14px}
.gaplist,.dclist{list-style:none; margin:0; padding:0 14px; display:flex;
  flex-direction:column; gap:9px}
.gap,.dcr{display:grid; align-items:center; gap:10px}
.gap{grid-template-columns:96px 1fr 84px}
.dcr{grid-template-columns:96px 1fr 62px 54px}
.gapname,.dcname{font-size:13px; font-weight:600; overflow:hidden; text-overflow:ellipsis}
.gaptrack,.dctrack{position:relative; height:16px}
.gaptrack::before,.dctrack::before{
  content:""; position:absolute; left:0; right:0; top:7px; height:2px;
  background:var(--outline-variant);
}
.gapline{position:absolute; top:6.5px; height:3px; border-radius:2px}
.gapdot{
  position:absolute; top:4px; width:9px; height:9px; border-radius:50%;
  margin-left:-4.5px; box-shadow:0 0 0 2px var(--surface);
}
.gapdot.d-a{background:var(--on-surface)}
.gapdot.d-x{background:var(--surface); border:2px solid var(--on-surface-variant)}
.gapnum,.dcnum{font-size:12px; text-align:right; color:var(--on-surface-variant)}
.dchits{font-size:11px; color:var(--on-surface-variant); text-align:right}
.dcfill{position:absolute; top:5px; height:6px; border-radius:9999px}
.dcmark{
  position:absolute; top:1px; width:2px; height:14px;
  background:var(--on-surface); opacity:.55;
}
.spark{vertical-align:middle}

/* --- expanded player view --- */
.rowlink{
  appearance:none; background:none; border:0; padding:0; font:inherit;
  color:inherit; cursor:pointer; text-align:left; text-decoration:underline;
  text-decoration-color:var(--outline); text-underline-offset:3px;
}
.rowlink:hover{text-decoration-color:var(--lilac)}
.rowlink:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.pl[role="button"]{cursor:pointer}
.pl[role="button"]:hover{transform:translateY(-2px)}
.pl[role="button"]:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.pl{transition:transform .12s ease}
dialog.pv{
  width:min(720px,94vw); max-height:88vh; padding:0; border:0;
  border-radius:var(--radius-l); background:var(--surface);
  color:var(--on-surface); box-shadow:0 18px 60px rgb(0 0 0 / 35%);
}
dialog.pv::backdrop{background:rgb(30 0 33 / 62%)}
.pv-close{
  position:absolute; top:10px; right:12px; z-index:2;
  appearance:none; border:0; background:var(--surface-variant);
  color:var(--on-surface); width:32px; height:32px; border-radius:50%;
  font-size:20px; line-height:1; cursor:pointer; font-family:inherit;
}
.pv-close:hover{background:var(--outline-variant)}
.pv-close:focus-visible{outline:3px solid var(--lilac); outline-offset:2px}
.pv-body{padding:20px 20px 24px; overflow-y:auto; max-height:88vh}
.pv-head{display:flex; align-items:flex-start; gap:12px; padding-right:38px}
.pv-head h2{font-size:22px}
.pv-sub{margin:2px 0 0; font-size:13px; color:var(--on-surface-variant)}
.pv-alert{
  margin:12px 0 0; padding:9px 12px; border-radius:var(--radius-s);
  background:var(--error-container); color:var(--error); font-size:13px;
}
.pv-block{margin-top:20px}
.pv-block h3{
  font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--on-surface-variant); margin-bottom:8px;
  display:flex; align-items:center; gap:10px;
}
.pv-spark{margin-left:auto}
.pv-big{margin:0; font-size:30px; font-weight:700; line-height:1.1}
.pv-big-n{font-size:13px; font-weight:400; color:var(--on-surface-variant)}
.pv-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px}
.pvs{background:var(--surface-variant); border-radius:var(--radius-s); padding:9px 11px}
.pvs-k{display:block; font-size:11px; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.pvs-v{display:block; font-size:19px; font-weight:700; font-variant-numeric:tabular-nums}
.pvs-n{display:block; font-size:11px; color:var(--on-surface-variant)}
.pv-fx{display:flex; gap:6px; flex-wrap:wrap}
.fxcell{
  display:flex; flex-direction:column; align-items:center; gap:1px;
  padding:6px 9px; border-radius:var(--radius-xs); font-size:11px; min-width:52px;
}
.fxcell i{font-style:normal; opacity:.85; font-variant-numeric:tabular-nums}
.pv-note{margin:8px 0 0; font-size:12px; color:var(--on-surface-variant)}
.pv-chips{margin:0; display:flex; gap:6px; flex-wrap:wrap}
.chiptag{
  background:var(--surface-variant); border-radius:9999px;
  padding:3px 10px; font-size:12px; font-weight:600;
}
@media (prefers-reduced-motion:reduce){.pl{transition:none}}

/* --- findings --- */
.finds{display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px}
.find{background:var(--surface); border-radius:var(--radius-m); box-shadow:var(--shadow); overflow:hidden}
.find h3{
  font-size:12px; text-transform:uppercase; letter-spacing:0.05em;
  padding:10px 14px; border-left:4px solid var(--tone,var(--p60));
}
.find .note{padding:0 14px 8px; font-size:13px; color:var(--on-surface-variant); margin-top:-4px}
.find ul{margin:0; padding:0 14px 14px 30px; font-size:14px}
.find li{margin-bottom:4px}

/* --- match logs --- */
details{border-bottom:1px solid var(--outline-variant)}
details summary{
  padding:10px 14px; cursor:pointer; font-weight:600; font-size:14px;
  display:flex; align-items:center; gap:10px;
}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"\\25B8"; color:var(--on-surface-variant); transition:transform .15s}
details[open] summary::before{transform:rotate(90deg)}
details summary:focus-visible{outline:3px solid var(--lilac); outline-offset:-3px}
details summary .mini{margin-left:auto; font-weight:400; color:var(--on-surface-variant); font-size:13px}
details .scroll{padding:0 14px 14px}

.foot{padding:16px; font-size:12px; color:var(--on-surface-variant); text-align:center}
@media (prefers-reduced-motion:reduce){*{transition:none!important; animation:none!important}}
@media (max-width:560px){
  .pl{width:76px}
  .pk{width:92px}
  .hero h1{font-size:20px}
  body{font-size:14px}
}
"""

SCATTER_JS = (Path(__file__).with_name("scatter.js")).read_text(encoding="utf-8")
PLAYERVIEW_JS = (Path(__file__).with_name("playerview.js")).read_text(encoding="utf-8")

JS = """
(function(){
  var tabs=document.querySelectorAll('.tab');
  tabs.forEach(function(t){
    t.addEventListener('click',function(){
      tabs.forEach(function(o){
        o.setAttribute('aria-selected', String(o===t));
        var p=document.getElementById(o.dataset.panel);
        if(p) p.hidden = (o!==t);
      });
      // Panels differ in height. Without this, switching from a long panel to
      // a short one leaves you scrolled past the end of the new one, staring
      // at empty background.
      var bar=t.parentNode;
      if(bar.getBoundingClientRect().top < 0) bar.scrollIntoView({block:'start'});
    });
  });

  // Starting XI: overview vs pick-team pitch. Same swap as the tabs above,
  // scoped to whichever card the clicked button lives in, since the page
  // only has one of these but a second squad card could add one later.
  document.querySelectorAll('.pkview').forEach(function(group){
    var btns = group.querySelectorAll('.pkbtn');
    var card = group.closest('.card');
    btns.forEach(function(b){
      b.addEventListener('click', function(){
        btns.forEach(function(o){ o.setAttribute('aria-selected', String(o===b)); });
        card.querySelectorAll('.pkpanel,[data-pkview]').forEach(function(p){
          p.hidden = (p.dataset.view || p.dataset.pkview) !== b.dataset.view;
        });
      });
    });
  });



  // Expected points: the bars slide out when opened.
  document.querySelectorAll('.epcard').forEach(function (card) {
    var btn = card.querySelector('.epmore');
    var txt = btn && btn.querySelector('.epmore-txt');
    var reduce = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function reveal() {
      if (reduce || !card.classList.contains('open')) { return; }
      card.querySelectorAll('.epr .epbar').forEach(function (bar, i) {
        if (!bar.animate) { return; }
        bar.animate(
          [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
          { duration: 450, delay: i * 42, fill: 'none',
            easing: 'cubic-bezier(.22,.7,.3,1)' }
        );
      });
    }
    if (btn) {
      btn.addEventListener('click', function () {
        var open = card.classList.toggle('open');
        btn.setAttribute('aria-expanded', String(open));
        if (txt) { txt.innerHTML = open ? 'Hide<br>bars' : 'See<br>more'; }
        reveal();
      });
    }
  });
  document.querySelectorAll('table[data-sortable]').forEach(function(tbl){
    tbl.querySelectorAll('th.sortable').forEach(function(th,i){
      var idx=Array.prototype.indexOf.call(th.parentNode.children,th);
      th.setAttribute('tabindex','0');
      function go(){
        var dir = th.getAttribute('aria-sort')==='descending' ? 1 : -1;
        tbl.querySelectorAll('th').forEach(function(o){o.removeAttribute('aria-sort')});
        th.setAttribute('aria-sort', dir<0 ? 'descending' : 'ascending');
        var body=tbl.tBodies[0];
        var rows=Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){
          var x=a.cells[idx], y=b.cells[idx];
          var xv=x?(x.dataset.v!==undefined?x.dataset.v:x.textContent):'';
          var yv=y?(y.dataset.v!==undefined?y.dataset.v:y.textContent):'';
          var xn=parseFloat(xv), yn=parseFloat(yv);
          if(!isNaN(xn)&&!isNaN(yn)) return (xn-yn)*dir;
          return String(xv).localeCompare(String(yv))*dir;
        });
        rows.forEach(function(r){body.appendChild(r)});
      }
      th.addEventListener('click',go);
      th.addEventListener('keydown',function(ev){
        if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();go();}
      });
    });
  });
})();
"""


# --- fragments ------------------------------------------------------------

def player_card(r, ctx, badges, shirts, captain_id, vice_id, played=True):
    el = r.element
    # FPL put a club shirt on their pitch, so this does too; the badge is the
    # fallback when a shirt image cannot be had.
    shirt = shirts.get((el["team"], r.pos == "GKP"))
    uri = shirt or badges.get(el["team"])
    crest = (
        f'<img class="{"kit" if shirt else "crestimg"}" src="{uri}" alt="{e(r.team)}">'
        if uri
        else f'<span class="letters">{e(r.team)}</span>'
    )
    arm = ""
    if el["id"] == captain_id:
        arm = '<span class="arm" title="Captain">C</span>'
    elif el["id"] == vice_id:
        arm = '<span class="arm" title="Vice-captain" style="background:var(--p20)">V</span>'
    flag, news = r.availability
    title = f"{r.name} - {r.pos}, {r.team}, {r.price:.1f}m"
    if flag:
        title += f" - {flag}. {news}"
    pred = ctx.is_predicted(el)
    pip = ""
    if pred is True:
        pip = '<span class="pip pip-in" title="Predicted to start"></span>'
        title += " - predicted to start"
    elif pred is False:
        pip = '<span class="pip pip-out" title="Not in the predicted eleven"></span>'
        title += " - NOT in the predicted eleven"
    cls = "pl" if played else "pl out"
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}{pip}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="sc tnum"><div class="p">{r.points}</div>'
        f'<div class="x">{r.xgi:.2f}</div></div></div>'
    )


def pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id):
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    out = ['<div class="pitch">']
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            player_card(r, ctx, badges, shirts, captain_id, vice_id, r.minutes > 0)
            for r in rows[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        player_card(r, ctx, badges, shirts, captain_id, vice_id, r.minutes > 0) for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div>'
    )
    return "".join(out)


def pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
              next_gw, played=True):
    """One card for the 'Pick team' pitch: the same shirt card as the
    overview, plus the two things worth knowing at a glance before a
    deadline - the next fixture, and a read on recent form worth the one
    line it costs."""
    el = r.element
    shirt = shirts.get((el["team"], r.pos == "GKP"))
    uri = shirt or badges.get(el["team"])
    crest = (
        f'<img class="{"kit" if shirt else "crestimg"}" src="{uri}" alt="{e(r.team)}">'
        if uri
        else f'<span class="letters">{e(r.team)}</span>'
    )
    arm = ""
    if el["id"] == captain_id:
        arm = '<span class="arm" title="Captain">C</span>'
    elif el["id"] == vice_id:
        arm = '<span class="arm" title="Vice-captain" style="background:var(--p20)">V</span>'
    flag, news = r.availability
    title = f"{r.name} - {r.pos}, {r.team}, {r.price:.1f}m"
    if flag:
        title += f" - {flag}. {news}"

    fx_rows = ticker._rows_for(r.team, proj, market, next_gw, 1)
    fx_html = (
        pos_fixture_pill(r.pos, fx_rows[0]["opp"], fx_rows[0]["home"],
                         fx_rows[0]["cs"], fx_rows[0]["xg"])
        if fx_rows else ""
    )

    form = r.recent_form()
    snippet = ""
    if form:
        icon = SPARK_ICON if form["hot"] else ""
        hot_cls = " hot" if form["hot"] else ""
        snippet = f'<div class="pk-form{hot_cls}">{icon}{e(form["text"])}</div>'

    cls = "pl pk" if played else "pl pk out"
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="pk-fx">{fx_html}</div>'
        f"{snippet}</div>"
    )


def pick_team_pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id,
                    proj, market, next_gw):
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    out = ['<div class="pitch">']
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj,
                     market, next_gw, r.minutes > 0)
            for r in rows[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
                 next_gw, r.minutes > 0)
        for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div>'
    )
    return "".join(out)


SQUAD_HEAD = [
    ("Pos", "", False), ("Player", "", True), ("Club", "", True),
    ("Price", "num", True), ("Own", "num", True), ("Min", "num", True),
    ("Pts", "num", True), ("xG", "num", True), ("xA", "num", True),
    ("xGI", "num", True), ("xGI/90", "num", True), ("DC/90", "num", True),
    ("Starting", "", True), ("Next 3", "", False),
]


def squad_table(reports, ctx, captain_id, vice_id, proj=None, market=None,
                next_gw=None):
    head = "".join(
        f'<th scope="col" class="{cls}{" sortable" if sortable else ""}">{e(label)}</th>'
        for label, cls, sortable in SQUAD_HEAD
    )
    maxx = max([r.xgi90 for r in reports] + [0.01])
    body = []
    for r in reports:
        el = r.element
        flag, news = r.availability
        fx = "".join(
            ticker.rating_pill(row["opp"], row["home"], row["score"])
            for row in ticker._rows_for(r.team, proj, market, next_gw, 3)
        ) or "".join(
            fdr_pill(ctx.team_name(o), h, d)
            for o, h, d, _ev in ctx.next_fixtures(el["team"], 3)
        )
        suffix = " (C)" if el["id"] == captain_id else (" (V)" if el["id"] == vice_id else "")
        flag_html = f' <span class="flag" title="{e(news)}">{e(flag)}</span>' if flag else ""
        # Goalkeepers have no defensive-contribution threshold, and a player
        # with no minutes has no rate worth printing.
        dc_cell = (
            f'<td class="num" data-v="{r.defcon90}">{r.defcon90:.1f}</td>'
            if r.minutes and r.pos != "GKP"
            else '<td class="num">-</td>'
        )
        pred = ctx.is_predicted(el)
        pred_txt = "yes" if pred is True else ("no" if pred is False else "unknown")
        sort_key = "" if pred_txt == "unknown" else pred_txt
        pred_cell = {
            "yes": '<span class="lu lu-in">Predicted XI</span>',
            "no": '<span class="lu lu-out">Not predicted</span>',
            "unknown": '<span class="lu lu-unk">-</span>',
        }[pred_txt]
        body.append(
            "<tr>"
            f'<td><span class="pos">{e(r.pos)}</span></td>'
            f'<td><button class="rowlink" data-player="{el["id"]}">'
            f"<b>{e(r.name)}</b></button>{suffix}{flag_html}</td>"
            f"<td>{e(r.team)}</td>"
            f'<td class="num" data-v="{r.price}">{r.price:.1f}</td>'
            f'<td class="num" data-v="{r.owned}">{r.owned:.0f}%</td>'
            f'<td class="num" data-v="{r.minutes}">{r.minutes}</td>'
            f'<td class="num" data-v="{r.points}"><b>{r.points}</b></td>'
            f'<td class="num" data-v="{r.xg}">{r.xg:.2f}</td>'
            f'<td class="num" data-v="{r.xa}">{r.xa:.2f}</td>'
            f'<td class="num" data-v="{r.xgi}">{r.xgi:.2f}</td>'
            f'<td class="num" data-v="{r.xgi90}">'
            f"{meter(r.xgi90, maxx, f'{r.xgi90:.2f} xGI per 90')} "
            f"{r.xgi90:.2f}</td>"
            f"{dc_cell}"
            f'<td data-v="{sort_key}">{pred_cell}</td>'
            f"<td>{fx}</td></tr>"
        )
    return (
        '<div class="scroll"><table data-sortable><thead><tr>'
        f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def match_logs(reports, ctx):
    out = []
    for r in reports:
        rows = sorted(r.history, key=lambda x: x["round"])
        if not rows:
            continue
        trs = []
        for h in reversed(rows):
            trs.append(
                "<tr>"
                f"<td>GW{h['round']}</td>"
                f"<td>{e(ctx.team_name(h['opponent_team']))} "
                f"{'(H)' if h['was_home'] else '(A)'}</td>"
                f'<td class="num">{h["minutes"]}</td>'
                f'<td class="num">{h["goals_scored"]}</td>'
                f'<td class="num">{h["assists"]}</td>'
                f'<td class="num">{f(h["expected_goals"]):.2f}</td>'
                f'<td class="num">{f(h["expected_assists"]):.2f}</td>'
                f'<td class="num">{f(h["expected_goal_involvements"]):.2f}</td>'
                f'<td class="num">{h.get("defensive_contribution", 0)}</td>'
                f'<td class="num">{h["bps"]}</td>'
                f'<td class="num"><b>{h["total_points"]}</b></td>'
                "</tr>"
            )
        out.append(
            f"<details><summary>{e(r.name)}"
            f'<span class="mini">{r.minutes} min &middot; {r.xgi:.2f} xGI '
            f"&middot; {r.points} pts</span></summary>"
            '<div class="scroll"><table><thead><tr>'
            "<th>GW</th><th>Opponent</th>"
            '<th class="num">Min</th><th class="num">G</th><th class="num">A</th>'
            '<th class="num">xG</th><th class="num">xA</th><th class="num">xGI</th>'
            '<th class="num">DefCon</th><th class="num">BPS</th><th class="num">Pts</th>'
            f"</tr></thead><tbody>{''.join(trs)}</tbody></table></div></details>"
        )
    return "".join(out)


def findings_cards(finds):
    cards = []
    for fnd in finds:
        tone = TONE_COLOR.get(fnd["tone"], "var(--p60)")
        items = []
        for raw in fnd["items"]:
            # Findings read "Player - what happened". Splitting on that first
            # dash lets the name lead in bold and the evidence sit under it,
            # which is the difference between a wall of prose and a list you
            # can actually scan.
            lead, sep, detail = raw.partition(" - ")
            if sep and len(lead) < 40:
                items.append(
                    f'<li><span class="lead">{e(lead)}</span>'
                    f'<span class="det">{e(detail)}</span></li>'
                )
            else:
                items.append(f'<li><span class="det">{e(raw)}</span></li>')
        items = "".join(items)
        note = f'<p class="note">{e(fnd["note"])}</p>' if fnd["note"] else ""
        cards.append(
            f'<div class="find" style="--tone:{tone}">'
            f"<h3>{e(fnd['title'])}</h3>{note}<ul>{items}</ul></div>"
        )
    return f'<div class="finds">{"".join(cards)}</div>'


def price_row(r):
    """One player's progress toward a price change.

    The bar is |percent| capped at 100, so a full bar means the change is due
    at the next recalculation. Direction is carried by an explicit arrow and
    the sign, not by the bar colour alone."""
    rising = r["pct"] > 0
    arrow = "&#9650;" if rising else "&#9660;"
    tone = "var(--success)" if rising else "var(--error)"
    width = min(100.0, abs(r["pct"]))
    tags = []
    if r["imminent"]:
        tags.append('<span class="tag tag-now">due now</span>')
    if r["owned_by_you"]:
        tags.append('<span class="tag tag-mine">yours</span>')
    net = r["net_transfers"]
    return (
        f'<li class="pw">'
        f'<span class="pw-top">'
        f'<span class="pw-name">{e(r["name"])}'
        f'<span class="pw-meta">{e(r["pos"])} &middot; {e(r["team"])} &middot; '
        f'{r["price"]:.1f}m</span></span>'
        f'<span class="pw-pct tnum" style="color:{tone}">{arrow} {abs(r["pct"]):.0f}%</span>'
        f"</span>"
        f'<span class="pw-bar"><span class="pw-fill" '
        f'style="width:{width:.1f}%;background:{tone}"></span></span>'
        f'<span class="pw-foot">in 2 days {r["projected"]:+.0f}% &middot; '
        f'net transfers {net:+,} {"".join(tags)}</span>'
        f"</li>"
    )


def price_watch_card(pw):
    if not pw["risers"] and not pw["fallers"]:
        return ""
    risers = "".join(price_row(r) for r in pw["risers"])
    fallers = "".join(price_row(r) for r in pw["fallers"])
    urgent = []
    if pw["your_fallers"]:
        names = ", ".join(r["name"] for r in pw["your_fallers"][:4])
        urgent.append(
            f"<b>{e(names)}</b> in your squad {'are' if len(pw['your_fallers']) > 1 else 'is'} "
            f"losing value. Selling after the drop costs you the difference."
        )
    if pw["rising_not_owned"]:
        soon = [r for r in pw["rising_not_owned"] if r["imminent"]][:4]
        if soon:
            names = ", ".join(r["name"] for r in soon)
            urgent.append(
                f"<b>{e(names)}</b> {'are' if len(soon) > 1 else 'is'} due to rise and "
                f"you do not own {'them' if len(soon) > 1 else 'him'}. Buying now saves the rise."
            )
    banner = (
        f'<div class="pw-alert">{"<br>".join(urgent)}</div>' if urgent else ""
    )
    return (
        '<section class="card">'
        '<div class="card-head"><h2>Price watch</h2>'
        '<span class="sub">A change fires at 100%. Prices update once a day, so this '
        "is only worth anything before it happens.</span></div>"
        f'<div class="card-body">{banner}'
        '<div class="pw-cols">'
        f'<div><h3 class="pw-h">Rising</h3><ul class="pw-list pw-scroll">{risers}</ul></div>'
        f'<div><h3 class="pw-h">Falling</h3><ul class="pw-list pw-scroll">{fallers}</ul></div>'
        "</div></div></section>"
    )


def scatter(points):
    """Value scatter with switchable axes.

    Drawn in the browser rather than baked into the SVG here: the point of
    swapping axes is to re-scale to whatever pair you choose, and that means
    the ticks, the domain and every position have to be recomputed. Emitting
    the data once and letting a few lines of JavaScript lay it out is far less
    code than generating every combination server-side.

    Your squad is separated from the market by size, a surface-coloured ring
    and a label, not by hue alone - the two mark colours clear CVD separation
    for protanopia but sit in the 6-8 band for tritanopia, where colour needs
    a second channel behind it."""
    if not points:
        return ""
    data = [
        {
            "n": p["name"], "t": p["team"], "p": p["pos"], "mine": p["mine"],
            "price": round(p["price"], 1),
            "xgi90": round(p["xgi90"], 3),
            "points": p["points"],
            "owned": round(p["owned"], 1),
            "minutes": p["minutes"],
            "ppm": round(p["points"] / p["price"], 2) if p["price"] else 0,
        }
        for p in points
    ]
    axes = (
        ("xgi90", "xGI per 90"),
        ("points", "Total points"),
        ("price", "Price (£m)"),
        ("owned", "Ownership %"),
        ("ppm", "Points per £m"),
        ("minutes", "Minutes"),
    )
    opts = lambda sel: "".join(
        f'<option value="{k}"{" selected" if k == sel else ""}>{e(label)}</option>'
        for k, label in axes
    )
    return (
        '<section class="card">'
        '<div class="card-head"><h2>Value scatter</h2>'
        '<span class="sub">Pick any two measures. Click a dot to identify the '
        "player. Your squad is labelled.</span></div>"
        '<div class="card-body">'
        '<div class="chartfilter" role="group" aria-label="Chart controls">'
        '<label class="axpick">Y <select class="axis" data-axis="y">'
        f"{opts('xgi90')}</select></label>"
        '<label class="axpick">X <select class="axis" data-axis="x">'
        f"{opts('price')}</select></label>"
        '<span class="spacer"></span>'
        '<button class="chip" data-pos="ALL" aria-pressed="true">All</button>'
        '<button class="chip" data-pos="DEF" aria-pressed="false">Defenders</button>'
        '<button class="chip" data-pos="MID" aria-pressed="false">Midfielders</button>'
        '<button class="chip" data-pos="FWD" aria-pressed="false">Forwards</button>'
        "</div>"
        '<div class="scroll"><svg class="scatter" viewBox="0 0 760 400" '
        'role="img" aria-label="Scatter plot of player metrics"></svg></div>'
        '<p class="readout" aria-live="polite">Click any dot to identify the player.</p>'
        '<p class="legend"><span class="key mkt"></span>Every player with 60+ minutes'
        '<span class="key mine"></span>Your squad</p>'
        f'<script type="application/json" class="scatter-data">{json.dumps(data)}</script>'
        "</div></section>"
    )


def opta_table(reports):
    """The Opta stats the Premier League publishes and FPL does not.

    Kept as its own card rather than more columns on the squad table: these
    measure a different thing (what a player actually did on the ball) and
    come from a different source, and mixing them in would imply FPL supplies
    them."""
    rows = [r for r in reports if r.element.get("_pulse")]
    if not rows:
        return ""
    keys = [k for k in pulse.STATS if any(r.element["_pulse"].get(k) for r in rows)]
    if not keys:
        return ""
    head = '<th scope="col">Player</th><th scope="col">Club</th>' + "".join(
        f'<th scope="col" class="num sortable" title="{e(pulse.STATS[k][1])}">'
        f"{e(pulse.STATS[k][0])}</th>"
        for k in keys
    )
    body = []
    for r in sorted(rows, key=lambda r: -(r.element["_pulse"].get("touches") or 0)):
        ps = r.element["_pulse"]
        cells = "".join(
            f'<td class="num" data-v="{ps.get(k) or 0:g}">'
            f'{("%g" % ps[k]) if ps.get(k) else "-"}</td>'
            for k in keys
        )
        body.append(
            f'<tr><td><b>{e(r.name)}</b></td><td>{e(r.team)}</td>{cells}</tr>'
        )
    return (
        '<section class="card">'
        '<div class="card-head"><h2>Beyond FPL</h2>'
        "<span class=\"sub\">Opta stats from the Premier League's own API. None of "
        "these appear anywhere in the FPL site or app.</span></div>"
        '<div class="scroll"><table data-sortable><thead><tr>'
        f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div></section>"
    )


def donut(pct, label, center, sub, tone="var(--lilac)"):
    """A single part-of-whole figure.

    Doughnuts are poor at comparing magnitudes, which is why nothing else in
    this page uses one. They are fine for exactly this: one share, read on its
    own, with the number printed in the middle so the angle is never the only
    way to read it."""
    r = 34
    circ = 2 * math.pi * r
    dash = max(0.0, min(1.0, pct / 100.0)) * circ
    return (
        f'<svg class="donut" viewBox="0 0 90 90" role="img" '
        f'aria-label="{e(label)}">'
        f'<circle class="dtrack" cx="45" cy="45" r="{r}"/>'
        f'<circle class="dval" cx="45" cy="45" r="{r}" stroke="{tone}" '
        f'stroke-dasharray="{dash:.1f} {circ - dash:.1f}" '
        f'transform="rotate(-90 45 45)"/>'
        f'<text class="dnum" x="45" y="43" text-anchor="middle">{e(center)}</text>'
        f'<text class="dsub" x="45" y="57" text-anchor="middle">{e(sub)}</text>'
        "</svg>"
    )


def ownership_carousel(own, by_name, ctx, my_name):
    """Mini-league ownership, one doughnut per player, arrows to move.

    Deliberately not auto-advancing: a slideshow that moves on its own hides
    most of the data behind waiting and takes the reading pace out of your
    hands. The track scrolls, snaps, and answers to the arrow keys."""
    n = len(by_name)
    if not own or not n:
        return ""
    rows = sorted(own.items(), key=lambda kv: -len(kv[1]["owners"]))
    cards = []
    for pid, rec in rows:
        el = ctx.players.get(pid)
        if not el:
            continue
        owners = len(rec["owners"])
        pct = 100.0 * owners / n
        mine = my_name in rec["owners"]
        tone = "var(--lilac)" if mine else "var(--p60)"
        caps = len(rec["captains"])
        note = f"{caps} captained him" if caps else "&nbsp;"
        aria = f"{el['web_name']} owned by {owners} of {n} managers"
        own_flag = '<p class="oyou">You own him</p>' if mine else ""
        cards.append(
            f'<li class="ocard{" mine" if mine else ""}">'
            f"{donut(pct, aria, f'{owners}/{n}', f'{pct:.0f}%', tone)}"
            f'<p class="oname">{e(el["web_name"])}</p>'
            f'<p class="oteam">{e(ctx.team_name(el["team"]))} &middot; {el["total_points"]} pts</p>'
            f'<p class="onote">{note}</p>'
            f"{own_flag}"
            "</li>"
        )
    return (
        '<section class="card">'
        '<div class="card-head"><h2>Who owns whom</h2>'
        f'<span class="sub">Share of the {n} managers in this league holding each '
        "player, most-owned first.</span>"
        '<span class="carnav">'
        '<button class="arrow" data-dir="-1" aria-label="Scroll left">&#8249;</button>'
        '<button class="arrow" data-dir="1" aria-label="Scroll right">&#8250;</button>'
        "</span></div>"
        f'<div class="card-body"><ul class="carousel" tabindex="0" '
        f'aria-label="Ownership by player">{"".join(cards)}</ul></div>'
        "</section>"
    )


def elite_card(res, ctx):
    """What the best managers in the world own, against what everyone owns."""
    if not res:
        return ""
    est = res["mode"] == "sampled"
    caveat = (
        f" Estimated from a {res['managers']}-manager sample, so each figure "
        f"carries about &plusmn;{res['moe']:.1f} points at 95% confidence."
        if est else ""
    )

    def table(rows, cols_note):
        body = []
        for r in rows:
            cls = ' class="me"' if r["mine"] else ""
            edge_tone = "var(--success)" if r["edge"] > 0 else "var(--error)"
            body.append(
                f"<tr{cls}><td><b>{e(r['name'])}</b></td>"
                f"<td>{e(r['pos'])}</td><td>{e(r['team'])}</td>"
                f'<td class="num">{r["price"]:.1f}</td>'
                f'<td class="num" data-v="{r["elite"]}">{r["elite"]:.1f}%</td>'
                f'<td class="num" data-v="{r["overall"]}">{r["overall"]:.1f}%</td>'
                f'<td class="num" data-v="{r["edge"]}" style="color:{edge_tone}">'
                f'<b>{r["edge"]:+.1f}</b></td></tr>'
            )
        return (
            f'<p class="tnote">{cols_note}</p>'
            '<div class="scroll"><table data-sortable><thead><tr>'
            '<th scope="col" class="sortable">Player</th>'
            '<th scope="col">Pos</th><th scope="col">Club</th>'
            '<th scope="col" class="num sortable">Price</th>'
            '<th scope="col" class="num sortable">Elite</th>'
            '<th scope="col" class="num sortable">Everyone</th>'
            '<th scope="col" class="num sortable">Edge</th>'
            f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        )

    parts = [table(res["most_owned"], "Most owned by the elite.")]
    if res["elite_edge"]:
        parts.append(table(
            res["elite_edge"],
            "Owned far more by the elite than by the crowd - and you do not own them.",
        ))
    if res["against"]:
        parts.append(table(
            res["against"],
            "You own these; the elite largely do not.",
        ))
    return (
        '<section class="card">'
        '<div class="card-head"><h2>What the best managers own</h2>'
        f'<span class="sub">{e(res["label"])}, read from the global FPL league at '
        f"gameweek {res['event']}.{caveat}</span></div>"
        f'<div class="card-body">{"".join(parts)}</div></section>'
    )


def ep_card(eps, gw):
    """Our own expected points, with the arithmetic on show."""
    if not eps:
        return ""
    rows = []
    for r, ep in sorted(eps, key=lambda x: -x[1]["total"]):
        fx = f"{ep['opponent']} ({'H' if ep['home'] else 'A'})"
        rows.append(
            f'<tr><td><b>{e(r.name)}</b></td><td>{e(r.pos)}</td>'
            f'<td>{e(fx)}</td>'
            f'<td class="num"><b>{ep["total"]:.2f}</b></td>'
            f'<td class="num">{ep["attack"]:.2f}</td>'
            f'<td class="num">{ep["defence"]:.2f}</td>'
            f'<td class="num">{ep["appearance"]:.2f}</td>'
            f'<td class="num">{ep["defcon"]:.2f}</td>'
            f'<td class="num">{ep["cs"]:.0f}%</td></tr>'
        )
    return (
        '<details class="card collapsible" open>'
        '<summary class="card-head"><h2>Expected points</h2>'
        f'<span class="sub">Our model for gameweek {gw}, broken into its parts. '
        "FPL's own projection tops out at 4.0 for every premium player, so this "
        "is built from Scout's fixture odds and each player's own rates."
        "</span></summary>"
        '<div class="scroll"><table data-sortable><thead><tr>'
        '<th scope="col" class="sortable">Player</th><th scope="col">Pos</th>'
        '<th scope="col">Fixture</th>'
        '<th scope="col" class="num sortable">Expected</th>'
        '<th scope="col" class="num sortable">Attack</th>'
        '<th scope="col" class="num sortable">Clean sheet</th>'
        '<th scope="col" class="num sortable">Appearance</th>'
        '<th scope="col" class="num sortable">DefCon</th>'
        '<th scope="col" class="num sortable">CS odds</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>"
    )


def findings_section(finds, reports, ctx):
    """Findings, with the ones that have a shape drawn rather than listed.

    Three of these are genuinely numeric comparisons and were being written
    out as sentences: goals against expected goals is a gap, defensive
    contribution is a distance to a threshold, and both read better as marks
    than as prose. The rest stay as lists, because a set-piece order or an
    injury note is text and dressing it up as a chart would be decoration."""
    drawn = {"cold", "hot", "defcon", "bcm", "setpieces", "sample"}

    gaps = [
        (r.name, r.goals, r.xg)
        for r in sorted(reports, key=lambda r: r.finishing)
        if abs(r.finishing) > 0.4 or r.xg >= 0.5
    ]
    dc_rows = []
    for r in reports:
        threshold = analysis.DEFCON_THRESHOLD.get(r.pos)
        if not threshold or not r.minutes:
            continue
        if r.defcon90 >= threshold * 0.55:
            dc_rows.append(
                (r.name, r.defcon90, threshold, r.defcon_hits, r.appearances)
            )
    dc_rows.sort(key=lambda x: -x[1] / x[2])

    # Grouped by duty, because the question is "who takes our penalties".
    duties = (
        ("pens", "On pens", "penalties_order"),
        ("fk", "On free kicks", "direct_freekicks_order"),
        ("corners", "On corners", "corners_and_indirect_freekicks_order"),
    )
    groups = []
    for key, title, field in duties:
        rows = sorted(
            ((r.element.get(field), r.name, r.team)
             for r in reports if r.element.get(field)),
            key=lambda x: x[0],
        )
        groups.append((key, title, rows))

    cards = []
    if gaps:
        cards.append(components.gap_chart(
            gaps,
            "Goals against expected goals",
            "The line is the gap. Green means the chances are arriving and the "
            "finishing has not caught up yet.",
            "Scored", "Expected",
        ))
    if dc_rows:
        cards.append(components.defcon_bars(dc_rows))
    sp = components.set_piece_card(groups)
    if sp:
        cards.append(sp)
    for fnd in finds:
        if fnd["key"] in drawn:
            continue
        cards.append(finding_card(fnd))
    return f'<div class="finds">{"".join(cards)}</div>'


def finding_card(fnd):
    tone = TONE_COLOR.get(fnd["tone"], "var(--p60)")
    items = []
    for raw in fnd["items"]:
        lead, sep, detail = raw.partition(" - ")
        if sep and len(lead) < 40:
            items.append(
                f'<li><span class="lead">{e(lead)}</span>'
                f'<span class="det">{e(detail)}</span></li>'
            )
        else:
            items.append(f'<li><span class="det">{e(raw)}</span></li>')
    note = f'<p class="note">{e(fnd["note"])}</p>' if fnd["note"] else ""
    return (
        f'<div class="find" style="--tone:{tone}">'
        f"<h3>{e(fnd['title'])}</h3>{note}<ul>{''.join(items)}</ul></div>"
    )


def template_xi(own, by_name, ctx):
    """The most-owned legal eleven in the mini-league.

    Not simply the eleven most-owned players: that could be six defenders and
    no keeper. Every legal shape is tried - one keeper, three to five
    defenders, two to five midfielders, one to three forwards, eleven in all -
    and the one with the most total ownership wins, which is what "the
    template" actually means."""
    n = len(by_name)
    if not own or not n:
        return None
    pools = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pid, rec in own.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        pools[ctx.pos(el)].append((len(rec["owners"]), el, rec))
    for key in pools:
        pools[key].sort(key=lambda x: (-x[0], -x[1]["total_points"]))

    best, best_total = None, -1
    for d in range(3, 6):
        for m in range(2, 6):
            f_ = 11 - 1 - d - m
            if not 1 <= f_ <= 3:
                continue
            picks = {"GKP": pools["GKP"][:1], "DEF": pools["DEF"][:d],
                     "MID": pools["MID"][:m], "FWD": pools["FWD"][:f_]}
            if any(len(v) < need for v, need in
                   ((picks["GKP"], 1), (picks["DEF"], d),
                    (picks["MID"], m), (picks["FWD"], f_))):
                continue
            total = sum(x[0] for group in picks.values() for x in group)
            if total > best_total:
                best_total, best = total, (picks, f"{d}-{m}-{f_}")
    if not best:
        return None
    picks, shape = best
    return {"picks": picks, "shape": shape, "managers": n}


def template_pitch(tpl, ctx, shirts, my_name):
    """The template eleven, laid out on a pitch."""
    if not tpl:
        return ""
    n = tpl["managers"]
    rows = []
    for key in ("GKP", "DEF", "MID", "FWD"):
        cards = []
        for count, el, rec in tpl["picks"][key]:
            shirt = shirts.get((el["team"], key == "GKP"))
            crest = (
                f'<img class="kit" src="{shirt}" alt="{e(ctx.team_name(el["team"]))}">'
                if shirt else f'<span class="letters">{e(ctx.team_name(el["team"]))}</span>'
            )
            mine = my_name in rec["owners"]
            pct = 100.0 * count / n
            cards.append(
                f'<div class="pl{" tpl-mine" if mine else ""}" '
                f'data-player="{el["id"]}" role="button" tabindex="0" '
                f'title="{e(el["web_name"])} - owned by {count} of {n}'
                f'{" including you" if mine else ", not by you"}">'
                f'<div class="crest">{crest}</div>'
                f'<div class="nm">{e(el["web_name"])}</div>'
                f'<div class="sc tnum"><div class="p">{count}/{n}</div>'
                f'<div class="x">{pct:.0f}%</div></div></div>'
            )
        if cards:
            rows.append(f'<div class="row">{"".join(cards)}</div>')
    owned_by_you = sum(
        1 for group in tpl["picks"].values() for _c, _el, rec in group
        if my_name in rec["owners"]
    )
    return (
        '<section class="card"><div class="card-head"><h2>League template</h2>'
        f'<span class="sub">The most-owned legal eleven across {n} managers, '
        f'in a {tpl["shape"]}. You have {owned_by_you} of them &mdash; the rest '
        "is where your rank moves.</span></div>"
        f'<div class="pitch tplpitch">{"".join(rows)}</div></section>'
    )


def differential_card(own, by_name, ctx, my_name, photos):
    """Players only you own, given room and a face.

    A one-line list in a grid cell left most of the card empty and made the
    single most interesting fact on the page look like an afterthought. With
    few enough of them, each gets a portrait and its numbers."""
    n = len(by_name)
    if not own or not my_name:
        return ""
    mine = [
        (pid, rec) for pid, rec in own.items()
        if my_name in rec["owners"] and len(rec["owners"]) == 1
    ]
    if not mine:
        return (
            '<section class="card"><div class="card-head"><h2>Your differentials</h2>'
            '<span class="sub">Players nobody else in the league owns.</span></div>'
            '<div class="card-body"><p class="dfempty">Every player you own is '
            "owned by somebody else in this league. You are running the template "
            "&mdash; safe from falling behind, and with nothing that can pull you "
            "clear.</p></div></section>"
        )
    mine.sort(key=lambda x: -f(ctx.players[x[0]]["expected_goal_involvements"]))
    cards = []
    for pid, _rec in mine:
        el = ctx.players[pid]
        photo = photos.get(pid)
        face = (
            f'<img class="df-photo" src="{photo}" alt="" width="84" height="106">'
            if photo else f'<div class="df-photo df-blank">{e(el["web_name"][:1])}</div>'
        )
        cards.append(
            f'<li class="df-card">{face}'
            f'<div class="df-body"><p class="df-name">{e(el["web_name"])}</p>'
            f'<p class="df-meta">{e(ctx.pos(el))} &middot; '
            f'{e(ctx.team_name(el["team"]))} &middot; {el["now_cost"] / 10:.1f}m</p>'
            f'<dl class="df-stats">'
            f'<div><dt>Points</dt><dd>{el["total_points"]}</dd></div>'
            f'<div><dt>xGI</dt><dd>{f(el["expected_goal_involvements"]):.2f}</dd></div>'
            f'<div><dt>Owned</dt><dd>{f(el["selected_by_percent"]):.0f}%</dd></div>'
            f"</dl></div></li>"
        )
    return (
        '<section class="card"><div class="card-head"><h2>Your differentials</h2>'
        f'<span class="sub">Nobody else in this league owns '
        f'{"them" if len(mine) > 1 else "him"}. Every point '
        f'{"they score" if len(mine) > 1 else "he scores"} is a point on the '
        "whole league.</span></div>"
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
    )


def leader_groups(ctx, squad_ids, depth=4, min_minutes=45):
    """Top few players on each measure, mixing FPL's numbers with Opta's.

    Expected goals conceded is the odd one out and is ranked ascending: for a
    defence, less is the achievement."""
    pool = [
        el for el in ctx.players.values()
        if el.get("minutes", 0) >= min_minutes
    ]
    mine = set(squad_ids)

    def build(title, note, icon, tone, key, fmt="{:.2f}", ascending=False,
              opta=False, positions=None):
        rows = []
        for el in pool:
            if positions and ctx.pos(el) not in positions:
                continue
            raw = (el.get("_pulse") or {}).get(key) if opta else el.get(key)
            value = f(raw)
            if raw is None or (not opta and value == 0 and not ascending):
                continue
            if opta and not raw:
                continue
            rows.append((value, el))
        rows.sort(key=lambda x: (x[0] if ascending else -x[0]))
        return {
            "title": title, "note": note, "icon": icon, "tone": tone,
            "rows": [
                (el["web_name"], ctx.team_name(el["team"]), fmt.format(v),
                 el["id"] in mine)
                for v, el in rows[:depth]
            ],
        }

    groups = [
        build("Expected goals", "xG this season", "ball", "#953bff",
              "expected_goals"),
        build("Expected assists", "xA this season", "key", "#00b3d6",
              "expected_assists"),
        build("Goal involvement", "xG plus xA", "spark", "#d81b8c",
              "expected_goal_involvements"),
        build("Chances created", "Passes leading to a shot", "boot", "#e07b00",
              "total_att_assist", fmt="{:.0f}", opta=True),
        build("Big chances created", "Passes setting up a clear opening",
              "run", "#00a35c", "big_chance_created", fmt="{:.0f}", opta=True),
        build("Fewest goals expected against", "xGC, defenders and keepers",
              "shield", "#7d5980", "expected_goals_conceded", ascending=True,
              positions=("GKP", "DEF")),
    ]
    return [g for g in groups if g["rows"]]


def player_payload(r, ctx, proj, ep, next_gw, photos):
    """Everything the expanded view shows for one player, as plain data.

    Emitted once as JSON and rendered in the browser. Fifteen copies of the
    same markup would be a lot of page weight for a panel you look at one
    player at a time."""
    el = r.element
    flag, news = r.availability
    fixtures = [
        {"gw": row["gw"], "opp": row["opp"], "home": row["home"],
         "cs": round(row["cs"]), "xg": round(row["xg"], 2)}
        for row in ffs.ticker(proj, r.team, next_gw, 6)
    ]
    log = [
        {"gw": h["round"], "opp": ctx.team_name(h["opponent_team"]),
         "home": h["was_home"], "min": h["minutes"],
         "g": h["goals_scored"], "a": h["assists"],
         "xg": round(f(h["expected_goals"]), 2),
         "xa": round(f(h["expected_assists"]), 2),
         "dc": h.get("defensive_contribution", 0),
         "bps": h["bps"], "pts": h["total_points"]}
        for h in sorted(r.history, key=lambda x: x["round"])
    ]
    return {
        "id": el["id"], "name": r.name, "team": r.team, "pos": r.pos,
        "photo": photos.get(el["id"]),
        "price": r.price, "owned": r.owned,
        "flag": flag or "", "news": news,
        "predicted": ctx.is_predicted(el),
        "minutes": r.minutes, "starts": r.starts, "apps": r.appearances,
        "goals": r.goals, "assists": r.assists, "points": r.points,
        "bonus": r.bonus,
        "xg": round(r.xg, 2), "xa": round(r.xa, 2), "xgi": round(r.xgi, 2),
        "xgi90": round(r.xgi90, 2), "defcon90": round(r.defcon90, 1),
        "defconHits": r.defcon_hits,
        "threshold": analysis.DEFCON_THRESHOLD.get(r.pos, 0),
        "setpieces": r.set_pieces(),
        "opta": el.get("_pulse") or {},
        "ep": ep,
        "fixtures": fixtures,
        "log": log,
        "last": r.last_season(),
    }


CONFIDENCE_LABEL = {"strong": "Strong", "watch": "Worth watching",
                    "flexible": "Timing flexible"}


def _cp_card(label, used_gw, body_html):
    if used_gw:
        return (
            f'<div class="cp used"><p class="cp-label">{e(label)}</p>'
            f'<p class="cp-used-tag">Already used, GW{used_gw}</p></div>'
        )
    return f'<div class="cp"><p class="cp-label">{e(label)}</p>{body_html}</div>'


def chip_planner_card(fh, tc, bb, wc, used):
    """The four chip recommendations, one card each - target gameweek,
    the number behind it, and a plain-language confidence read."""
    if not (fh or tc or bb or wc):
        return ""

    def conf_pill(level):
        return (f'<span class="cp-conf cp-conf-{level}">'
               f'{e(CONFIDENCE_LABEL.get(level, level))}</span>')

    cards = []

    if fh:
        pt = fh["points_team"]
        body = (
            f'<p class="cp-gw">GW{fh["gw"]}</p>'
            f'<p class="cp-reason">Best possible XI projects {pt["ideal_value"]:.1f} pts '
            f'against your {pt["ours_value"]:.1f} - a gap of {fh["gap"]:.1f}.</p>'
            f'{conf_pill(fh["confidence"])}'
        )
        cards.append(_cp_card("Free Hit", used.get("freehit"), body))

    if tc:
        body = (
            f'<p class="cp-gw">GW{tc["gw"]}</p>'
            f'<p class="cp-reason">Captain {e(tc["player"].name)} for '
            f'{tc["ep"]:.1f} pts ({tc["ep"] * 2:.1f} with the armband).</p>'
            f'{conf_pill(tc["confidence"])}'
        )
        cards.append(_cp_card("Triple Captain", used.get("3xc"), body))

    if bb:
        body = (
            f'<p class="cp-gw">GW{bb["gw"]}</p>'
            f'<p class="cp-reason">Bench projects {bb["ep"]:.1f} pts that week'
            f'{" - if your bench stays as it is." if not bb["transfers"] else "."}</p>'
            f'{conf_pill(bb["confidence"])}'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body))

    if wc:
        start, weeks = wc["gw_window"]
        body = (
            f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
            f'<p class="cp-reason">{wc["gap"]:.1f} pts of upside available '
            f'over the window.</p>'
            f'{conf_pill(wc["confidence"])}'
        )
        cards.append(_cp_card("Wildcard", used.get("wildcard"), body))

    # The grid above is for the compact per-chip summary only.
    # components.transfer_cards renders its own full-width "Suggested
    # transfers"-shaped section (portrait, arrow, portrait) - it does not
    # fit a ~250px grid column, so Bench Boost's and Wildcard's move lists
    # render as their own full-width sections below the grid instead of
    # nested inside it. Found by actually looking at the rendered page,
    # not assumed safe from the code alone.
    extra = []
    if bb and bb["transfers"]:
        rows = [{**t, "out_photo": None, "in_photo": None,
                "out_shirt": None, "in_shirt": None}
               for t in bb["transfers"]]
        extra.append(components.transfer_cards(
            rows, f"Bench Boost, GW{bb['gw']} - would improve that specific week."))
    if wc and wc["moves"]:
        rows = [{**mv, "out_photo": None, "in_photo": None,
                "out_shirt": None, "in_shirt": None}
               for mv in wc["moves"]]
        extra.append(components.transfer_cards(
            rows, "Wildcard - suggested rebuild, most expensive first."))

    return (
        '<section class="card"><div class="card-head"><h2>Chip planner</h2>'
        '<span class="sub">Best gameweek for each chip in the current half, '
        'scored from the same projections as the rest of the page.</span></div>'
        f'<div class="card-body"><ul class="cplist">{"".join(cards)}</ul></div></section>'
        f'{"".join(extra)}'
    )


def player_dialog(payloads):
    """One dialog for every player, filled on demand from the JSON below it."""
    labels = {k: v[0] for k, v in pulse.STATS.items()}
    return (
        '<dialog class="pv" aria-label="Player detail">'
        '<button class="pv-close" aria-label="Close player detail">&times;</button>'
        '<div class="pv-body"></div></dialog>'
        f'<script type="application/json" id="player-data">'
        f"{json.dumps({'players': payloads, 'optaLabels': labels})}</script>"
    )


def league_table(rows, squads, ctx, me):
    maxx = max(
        [analysis.squad_underlying(p, ctx)["xgi"] for p in squads.values()] + [0.01]
    )
    body = []
    for r in rows:
        picks = squads.get(r["entry"])
        chip = bench = hits = "-"
        xgi = 0.0
        cap = "-"
        if picks:
            chip = picks.get("active_chip") or "-"
            eh = picks.get("entry_history", {})
            bench = eh.get("points_on_bench", 0)
            hits = eh.get("event_transfers_cost", 0)
            xgi = analysis.squad_underlying(picks, ctx)["xgi"]
            cid = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
            if cid and cid in ctx.players:
                cap = ctx.players[cid]["web_name"]
        cls = ' class="me"' if me and r["entry"] == me else ""
        body.append(
            f"<tr{cls}>"
            f'<td class="num">{r["rank"]}</td>'
            f'<td><b>{e(r["entry_name"])}</b></td>'
            f'<td>{e(r["player_name"])}</td>'
            f'<td class="num">{r["event_total"]}</td>'
            f'<td class="num"><b>{r["total"]}</b></td>'
            f"<td>{e(cap)}</td>"
            f"<td>{e(chip)}</td>"
            f'<td class="num">{bench}</td>'
            f'<td class="num">{hits}</td>'
            f'<td class="num" data-v="{xgi}">'
            f"{meter(xgi, maxx, f'{xgi:.1f} xGI')} {xgi:.1f}</td>"
            "</tr>"
        )
    return (
        '<div class="scroll"><table data-sortable><thead><tr>'
        '<th class="num sortable">#</th><th class="sortable">Team</th>'
        '<th class="sortable">Manager</th><th class="num sortable">GW</th>'
        '<th class="num sortable">Total</th><th class="sortable">Captain</th>'
        '<th class="sortable">Chip</th><th class="num sortable">Bench</th>'
        '<th class="num sortable">Hits</th><th class="num sortable">XI xGI</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def ownership_cards(own, by_name, ctx, my_name):
    n = len(by_name)

    def nm(pid):
        el = ctx.players.get(pid)
        return f"{el['web_name']} ({ctx.team_name(el['team'])})" if el else str(pid)

    mine = {p for p, r in own.items() if my_name in r["owners"]}
    blocks = []

    template = sorted(
        (p for p, r in own.items() if len(r["owners"]) >= max(2, n * 0.5)),
        key=lambda p: -len(own[p]["owners"]),
    )
    if False and template:
        items = [
            f"{nm(p)} - {len(own[p]['owners'])}/{n} managers"
            f"{'' if p in mine else '  (you do not own)'}"
            for p in template
        ]
        blocks.append(analysis._finding("t", "League template", "neutral", items,
                                        f"Owned by at least half of {n} managers."))

    diffs = sorted(
        (p for p in mine if len(own[p]["owners"]) == 1),
        key=lambda p: -f(ctx.players[p]["expected_goal_involvements"]),
    )
    if False and diffs:
        items = [
            f"{nm(p)} - {ctx.players[p]['total_points']} pts, "
            f"xGI {f(ctx.players[p]['expected_goal_involvements']):.2f}, "
            f"{f(ctx.players[p]['selected_by_percent']):.0f}% owned overall"
            for p in diffs
        ]
        blocks.append(analysis._finding("d", "Your differentials", "good", items,
                                        "Nobody else in the league owns them."))

    gaps = sorted(
        (p for p, r in own.items() if p not in mine and len(r["owners"]) >= max(2, n * 0.4)),
        key=lambda p: -ctx.players[p]["total_points"],
    )
    if gaps:
        items = [
            f"{nm(p)} - {len(own[p]['owners'])}/{n} own, "
            f"{ctx.players[p]['total_points']} pts, "
            f"xGI {f(ctx.players[p]['expected_goal_involvements']):.2f}"
            for p in gaps
        ]
        blocks.append(analysis._finding("g", "The league has these, you do not", "warn", items))

    caps = {}
    for pid, r in own.items():
        for c in r["captains"]:
            caps.setdefault(pid, []).append(c)
    if caps:
        items = [
            f"{nm(pid)} - {len(who)}/{n}: {', '.join(who)} "
            f"({ctx.players[pid]['event_points']} pts this gameweek)"
            for pid, who in sorted(caps.items(), key=lambda kv: -len(kv[1]))
        ]
        blocks.append(analysis._finding("c", "Captain picks", "info", items))

    return findings_cards(blocks)


def chips_table(histories):
    names = ["wildcard", "freehit", "bboost", "3xc"]
    label = {"wildcard": "Wildcard", "freehit": "Free Hit",
             "bboost": "Bench Boost", "3xc": "Triple Captain"}
    body = []
    for mgr, h in histories.items():
        used = {}
        for c in h.get("chips", []):
            used.setdefault(c["name"], []).append(str(c["event"]))
        cells = "".join(
            f"<td>{'GW' + ', '.join(used[c]) if c in used else '-'}</td>" for c in names
        )
        body.append(f"<tr><td><b>{e(mgr)}</b></td>{cells}</tr>")
    head = "".join(f"<th>{label[c]}</th>" for c in names)
    return (
        '<div class="scroll"><table><thead><tr><th>Manager</th>'
        f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


# --- page -----------------------------------------------------------------

def render(d, standalone=True):
    ctx = d["ctx"]
    title = d["team_name"]
    eh = d["entry_history"]

    # What belongs here is what you would act on, not what happened. Squad
    # value and points-on-bench were retrospective, and XI xGI was the weakest
    # number on the page - a season total over one match, never adjusted for
    # minutes. Replaced by the two forward-looking things: what the squad is
    # projected to score, and who is not going to play.
    projected = d.get("projected_xi")
    attention = d.get("attention") or []
    tiles = [
        ("Gameweek", eh.get("points", "-"), f"GW{d['gw']}"),
        ("Total", eh.get("total_points", "-"),
         f"{d['overall_rank']:,} overall" if d.get("overall_rank") else "points"),
        ("League", f"{d['my_rank']}/{d['league_size']}" if d["my_rank"] else "-",
         e(d["league_name"])),
        ("Projected", f"{projected:.1f}" if projected else "-",
         f"your XI, GW{d['next_gw']}"),
        ("Needs a look", len(attention),
         ", ".join(attention[:2]) + ("&hellip;" if len(attention) > 2 else "")
         if attention else "nobody flagged"),
        ("In the bank", f"{eh.get('bank', 0) / 10:.1f}m",
         f"squad {eh.get('value', 0) / 10:.1f}m"),
    ]
    tile_html = "".join(
        f'<div class="tile"><div class="k">{e(k)}</div>'
        f'<div class="v tnum">{e(v)}</div><div class="n">{n}</div></div>'
        for k, v, n in tiles
    )

    body = f"""
<header class="topbar"><div class="topbar-in">
  <span class="wordmark"><span class="dot"></span>FPL Insights</span>
  <span class="gw-chip">Gameweek {d['gw']}</span>
  <span class="stamp">{e(d['generated'])}</span>
</div></header>

<div class="wrap">
  <section class="hero">
    <h1>{e(title)}</h1>
    <div class="mgr">{e(d['manager'])} &middot; {e(d['league_name'])}</div>
    <div class="tiles">{tile_html}</div>
  </section>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" aria-selected="true" data-panel="p-squad">Squad</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-market">Planning</button>
    <button class="tab" role="tab" aria-selected="false" data-panel="p-league">Mini-league</button>
  </div>

  <div class="panel" id="p-squad" role="tabpanel">
    <section class="card">
      <div class="card-head"><h2>Starting XI</h2>
        <span class="sub" data-pkview="ov">Points and season xGI on each card. Faded crest = did not play. Green dot = predicted to start, red = not in the predicted eleven.</span>
        <span class="sub" data-pkview="pk" hidden>Next fixture and a read on recent form on each card, shaded by clean-sheet odds for keepers and defenders and by expected goals for everyone else.</span>
      </div>
      <div class="pkview" role="tablist" aria-label="Pitch view">
        <button class="pkbtn" role="tab" aria-selected="true" data-view="ov">Overview</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="pk">Pick team</button>
      </div>
      <div class="pkpanel" data-view="ov">{d['pitch']}</div>
      <div class="pkpanel" data-view="pk" hidden>{d['pick_pitch']}</div>
    </section>
    {d['ep']}
    <details class="card collapsible">
      <summary class="card-head"><h2>Squad detail</h2>
        <span class="sub">Click a column heading to sort. Next 3 fixtures coloured by difficulty.</span>
      </summary>
      {d['squad_table']}
    </details>
    <section>
      <div class="card-head"><h2>What the numbers say</h2></div>
      {d['findings']}
    </section>
  </div>

  <div class="panel" id="p-market" role="tabpanel" hidden>
    {d['chip_planner']}
    {d['ticker']}
    {d['market']}
    {d['transfers']}
    {d['pairings']}
    {d['leaders']}
    {d['price_watch']}
    {d['scatter']}
    {d['elite']}
  </div>

  <div class="panel" id="p-league" role="tabpanel" hidden>
    <section class="card">
      <div class="card-head"><h2>{e(d['league_name'])}</h2>
        <span class="sub">XI xGI is the season expected involvement of the eleven that started.
        A big score beside a small xGI came from somewhere that will not repeat.</span>
      </div>
      {d['league_table']}
    </section>
    {d['template']}
    {d['carousel']}
    {d['differentials']}
    <section>{d['ownership']}</section>
    <section class="card">
      <div class="card-head"><h2>Chips used</h2>
        <span class="sub">Two of each per season - one before GW20, one after.</span>
      </div>
      {d['chips']}
    </section>
  </div>



  {d['dialog']}
  <p class="foot">Built from the public Fantasy Premier League API &middot;
  expected goals are Opta's, as used by FPL &middot; {e(d['generated'])}</p>
</div>
"""
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Barlow:wght@400;500;600;700&display=swap">'
    )
    head = f"<title>{e(title)}</title>{fonts}<style>{CSS}</style>"
    page = f"{head}{body}<script>{JS}</script><script>{SCATTER_JS}</script><script>{PLAYERVIEW_JS}</script>"
    if not standalone:
        return page
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{head}</head><body>{body}<script>{JS}</script>"
        f"<script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script></body></html>"
    )


def build(entry_id, league_id, ttl=fplapi.DEFAULT_TTL, gw=None, limit=25,
          elite_depth=100, elite_sample=None):
    """Gather everything the page needs."""
    ctx = analysis.Ctx.load(ttl=ttl)
    gw = gw or ctx.last_event_with_picks()

    picks = analysis.squad_for(entry_id, gw, ctx)
    meta = fplapi.entry(entry_id, ttl=ttl)
    cap = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
    vice = next((p["element"] for p in picks["picks"] if p["is_vice_captain"]), None)

    xi_ids = [p["element"] for p in picks["picks"] if p["position"] <= 11]
    bench_ids = [p["element"] for p in picks["picks"] if p["position"] > 11]
    reports = {pid: analysis.build_player(ctx, pid, ttl=ttl)
               for pid in xi_ids + bench_ids}
    xi = [reports[i] for i in xi_ids]
    bench = [reports[i] for i in bench_ids]

    matched = pulse.attach(ctx, ttl=ttl)
    if matched:
        print(f"[pulse] {matched} players matched to Premier League Opta stats")

    shirts = {}
    for tid, t in ctx.teams.items():
        for keeper in (False, True):
            uri = fplapi.shirt_data_uri(t["code"], keeper=keeper)
            if uri:
                shirts[(tid, keeper)] = uri

    photos = {}
    for r in xi + bench:
        uri = fplapi.photo_data_uri(r.element["photo"])
        if uri:
            photos[r.element["id"]] = uri

    badges = {}
    for tid, t in ctx.teams.items():
        uri = fplapi.badge_data_uri(t["code"])
        if uri:
            badges[tid] = uri

    rows, squads, by_name, histories = [], {}, {}, {}
    league_name = "Mini-league"
    if league_id:
        data = fplapi.league_standings(league_id, ttl=ttl)
        league_name = data["league"]["name"]
        rows = data["standings"]["results"][:limit]
        for r in rows:
            try:
                p = analysis.squad_for(r["entry"], gw, ctx)
            except fplapi.FplError:
                continue
            squads[r["entry"]] = p
            by_name[r["entry_name"]] = p
            try:
                histories[r["entry_name"]] = fplapi.entry_history(r["entry"], ttl=ttl)
            except fplapi.FplError:
                pass

    squad_ids = xi_ids + bench_ids
    pw = analysis.price_watch(ctx, squad_ids)
    scatter_pts = analysis.market_scatter_points(ctx, squad_ids)

    proj = ffs.projections(ttl=ttl)
    try:
        odds.build_club_lookup(ctx)
        market_fixtures = odds.league_fixtures(ttl=ttl)
        market = odds.by_club(ctx, ttl=ttl)
    except fplapi.FplError as ex:
        print(f"[odds] skipped: {ex}")
        market, market_fixtures = {}, []
    next_gw = min(38, (ctx.current_event() or 1) + 1)
    baselines = analysis.team_attack_baselines(ctx)
    eps = []
    for r in xi + bench:
        ep = analysis.expected_points(r, ctx, proj, next_gw,
                                      market=market, baselines=baselines)
        if ep:
            eps.append((r, ep))

    elite_res = None
    if elite_depth:
        try:
            elite_res = elite.compare(ctx, squad_ids, depth=elite_depth,
                                      sample=elite_sample, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[elite] skipped: {ex}")

    bank = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
    swaps = transfers.suggest(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=6, elite=elite_res,
    )
    for sw in swaps:
        el = sw["in"]
        sw["in_club"] = ctx.team_name(el["team"])
        sw["out_photo"] = photos.get(sw["out"].element["id"])
        sw["in_photo"] = fplapi.photo_data_uri(el["photo"])
        sw["out_shirt"] = shirts.get(
            (sw["out"].element["team"], sw["out"].pos == "GKP"))
        sw["in_shirt"] = shirts.get((el["team"], ctx.pos(el) == "GKP"))

    pairings = transfers.pair_suggestions(
        ctx, xi + bench, proj, next_gw, market, baselines,
        bank=bank, limit=4, elite=elite_res,
    )
    for pr in pairings:
        for leg in pr["legs"]:
            el = leg["in"]
            leg["out_photo"] = photos.get(leg["out"].element["id"])
            leg["in_photo"] = fplapi.photo_data_uri(el["photo"])
            leg["out_shirt"] = shirts.get(
                (leg["out"].element["team"], leg["out"].pos == "GKP"))
            leg["in_shirt"] = shirts.get((el["team"], ctx.pos(el) == "GKP"))

    my_row = next((r for r in rows if r["entry"] == entry_id), None)
    my_name = my_row["entry_name"] if my_row else None
    my_xgi = analysis.squad_underlying(picks, ctx)["xgi"]
    ranked = sorted(
        ((analysis.squad_underlying(p, ctx)["xgi"], n) for n, p in by_name.items()),
        reverse=True,
    )
    xgi_note = "expected involvement of your XI"
    if ranked and my_name:
        place = next((i for i, (_v, n) in enumerate(ranked, 1) if n == my_name), None)
        if place:
            xgi_note = f"{place} of {len(ranked)} in the league"

    own = analysis.league_ownership(by_name) if by_name else {}
    tpl = template_xi(own, by_name, ctx) if own else None
    league_photos = dict(photos)
    if own and my_name:
        for pid, rec in own.items():
            if my_name in rec["owners"] and len(rec["owners"]) == 1:
                league_photos.setdefault(pid, fplapi.photo_data_uri(
                    ctx.players[pid]["photo"]))

    # Same graceful-degradation shape ticker.fixture_ticker already uses
    # for the same reason: if proj never arrived this build, there is
    # nothing honest to recommend, so the whole card skips rather than
    # showing a set of zeroed or misleading cards.
    fh = tc = bb = wc = None
    used = {}
    if proj:
        bank_m = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
        try:
            total_sell, _per_player = analysis.squad_sell_value(
                entry_id, ctx, xi + bench, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] sell value unavailable, falling back to "
                  f"current price: {ex}")
            total_sell = sum(r.price for r in xi + bench)
        fh = chips.free_hit(ctx, xi, proj, market, baselines, next_gw)
        tc = chips.triple_captain(ctx, xi, proj, market, baselines, next_gw)
        bb = chips.bench_boost(ctx, bench, proj, market, baselines, next_gw,
                               bank=bank_m)
        wc = chips.wildcard(ctx, xi + bench, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        try:
            used = chips.used_chips_this_half(entry_id, next_gw, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] chip history unavailable: {ex}")

    return {
        "ctx": ctx,
        "gw": gw,
        "team_name": meta.get("name", "My team"),
        "manager": f"{meta.get('player_first_name', '')} "
                   f"{meta.get('player_last_name', '')}".strip(),
        "entry_history": picks.get("entry_history", {}),
        "league_name": league_name,
        "league_size": len(rows),
        "my_rank": my_row["rank"] if my_row else None,
        "my_xgi": my_xgi,
        "xgi_note": xgi_note,
        "pitch": pitch(xi, bench, ctx, badges, shirts, cap, vice),
        "pick_pitch": pick_team_pitch(xi, bench, ctx, badges, shirts, cap,
                                      vice, proj, market, next_gw),
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used),
        "squad_table": squad_table(xi + bench, ctx, cap, vice,
                                   proj, market, next_gw),
        "opta": opta_table(xi + bench),
        "ticker": ticker.fixture_ticker(xi + bench, ctx, proj, next_gw,
                                        weeks=6, market=market),
        "market": ticker.odds_insights(market_fixtures, xi, ctx, proj, next_gw),
        "pairings": components.pairing_cards(
            pairings,
            "Two out, two in - moves a single transfer cannot reach, because "
            "one sale funds the other and two sales from a club free a slot. "
            "Same shape, within budget, three per club respected."),
        "leaders": components.stat_leaders(leader_groups(ctx, squad_ids)),
        "transfers": components.transfer_cards(
            swaps,
            f"Same position, affordable on {bank:.1f}m in the bank, ranked by "
            f"projected gain for gameweek {next_gw}. Selling price is taken as "
            f"current price. One gameweek of data underneath - read these as "
            f"prompts, not instructions."),
        "ep": components.ep_bars(eps),
        "dialog": player_dialog([
            player_payload(r, ctx, proj, ep, next_gw, photos) for r, ep in eps
        ] + [
            player_payload(r, ctx, proj, None, next_gw, photos)
            for r in xi + bench if not any(r is q for q, _ in eps)
        ]),
        "findings": findings_section(
            analysis.build_findings(list(reports.values()), ctx),
            list(reports.values()), ctx),
        "logs": match_logs(xi + bench, ctx),
        "price_watch": price_watch_card(pw),
        "scatter": scatter(scatter_pts),
        "league_table": league_table(rows, squads, ctx, entry_id) if rows else "",
        "ownership": ownership_cards(own, by_name, ctx, my_name) if own else "",
        "carousel": ownership_carousel(own, by_name, ctx, my_name) if own else "",
        "template": template_pitch(tpl, ctx, shirts, my_name),
        "differentials": differential_card(own, by_name, ctx, my_name, league_photos),
        "elite": elite_card(elite_res, ctx),
        "chips": chips_table(histories) if histories else "",
        "next_gw": next_gw,
        "overall_rank": meta.get("summary_overall_rank"),
        "projected_xi": sum(
            ep["total"] for r, ep in eps
            if r.element["id"] in set(xi_ids)
        ) or None,
        # Anyone you would want to know about before the deadline.
        "attention": [
            r.name for r in xi
            if r.availability[0] or ctx.is_predicted(r.element) is False
        ],
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
    }
