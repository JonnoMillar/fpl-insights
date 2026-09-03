#!/usr/bin/env python3
"""
Renders the squad and mini-league reports as a single self-contained HTML page.

Colour is FPL's own - the deep purple and the bright green the game is
actually recognised by - because a tool read alongside the site it draws from
should look related to it. What changed is how that colour is spent.

The page used to open on a 135-degree three-stop gradient, purple bleeding
through lilac into green. That is the default hero of every generated
dashboard, and it was the thing that made this one look generated. It is
gone. Purple is now structure and ink, green is one accent used flat, and
the character comes from type and layout instead of from a colour wash:

* Type is Archivo across its width axis - expanded for headings, normal for
  body, so the contrast comes from width rather than from a second family -
  with IBM Plex Mono on every figure, tabular, so columns of stats align on
  the digit the way a results service does.
* One delta chip carries every number that has a good or bad reading, rather
  than each card inventing its own arrow.
* Findings read as a mono subject tag beside ordinary prose, not as a bold
  black line with grey underneath it, which is the pattern that made every
  card on the page look like every other card.

Two constraints worth keeping in mind when editing:

* Green is a fill, never type. #01fc7a is 1.35:1 on white, so anything that
  lands on text uses --accent-ink / --good-ink instead.
* Difficulty pills always carry a visible opponent and number. Several steps
  on the ramp are too close in luminance to carry meaning by fill alone, so
  the label does the work and the colour only makes a run visible down a
  column.

Light only. There is no dark theme and no toggle - the page is read in
daylight before a deadline, and carrying a second full palette meant every
new colour had to be drawn twice and kept in step.
"""

import html
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import analysis
import captaincy
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

# FPL's own five-step difficulty scale, background and text, straight from
# their stylesheet. Difficulty is ordinal and diverging - kind through neutral
# to brutal - so the grey midpoint is correct rather than a gap in the
# palette. Every pill also carries the opponent and the number, which is what
# actually makes it readable: steps 2 and 3 sit at 1.35:1 and 1.2:1 against
# white, so the fill alone was never carrying the meaning.
FDR = {
    1: ("#375523", "#ffffff"),
    2: ("#01fc7a", "#37003c"),
    3: ("#e7e7e7", "#37003c"),
    4: ("#ff1751", "#000000"),
    5: ("#80072d", "#ffffff"),
}

TONE_COLOR = {
    "good": "var(--good)",
    "bad": "var(--bad)",
    "warn": "var(--attention)",
    "info": "var(--p60)",
    "neutral": "var(--p60)",
}


def e(x):
    return html.escape(str(x), quote=True)


def fdr_pill(opp, home, diff):
    bg, fg = FDR.get(diff, ("#ebe5eb", "#37003c"))
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
  /* "Floodlit". The ground is the cold blue-slate of a night stand, the one
     accent is sodium-vapour amber - the colour of the lamps outside a ground
     and on the old pylons. Good and bad run turf-to-clay rather than the
     The two colours are FPL's own and deliberately so: the deep purple and
     the bright green are the pairing the game is actually recognised by, and
     no invented scheme signals "this is about FPL" the way they do.

     What had to go was not the colours but how they were being spent. A
     135-degree three-stop gradient across the hero, purple bleeding into
     lilac into green, is the house style of every generated dashboard there
     is - the tell was the gradient, not the hue. So: purple is structure and
     ink, green is the one accent, both flat, and the page earns its
     character from typography and layout instead of from a colour wash.

     Green is a fill, never type - #01fc7a on white is 1.35:1 - so anything
     that lands on text uses the darker cut. */
  --white:#ffffff;
  --p2:#faf9fa; --p5:#f5f2f5; --p10:#ebe5eb; --p20:#d7ccd8; --p30:#c3b2c4;
  /* --p50 is 3.52:1 on white and must not carry type - it is a border
     and fill value. --p60 is 4.62:1 and is the lightest ink allowed on
     a white card. */
  --p40:#af99b1; --p50:#9b809d; --p60:#87668a; --p70:#7d5980; --p80:#541e5d;
  --p90:#41054b; --p100:#37003c; --p110:#28002b; --p120:#1e0021;
  --ink:#37003c;

  /* --accent is the brand: the green this page is recognised by, spent on
     structure - the hero's rule, a selected state, the one card in a group
     that has earned it. --good is a reading: this number went the right
     way. They are the same green today because FPL's green is both, but
     they are two jobs and were one token, so recolouring either one
     silently moved the other. Split, with the same value, deliberately. */
  --accent:#01fc7a; --accent-ink:#046b39; --accent-wash:#e2fdf0;
  --good:#01fc7a; --good-ink:#046b39; --good-wash:#e2fdf0;
  --bad:#e60023; --bad-ink:#c0001d; --bad-wash:#fff2f4;
  /* --warn is retired - its role folds into --attention below. --warn-ink
     stays, on its own, for the one thing that is genuinely "borderline"
     rather than "needs a look": the .warn-pill text. */
  --warn-ink:#9c5400;
  /* The sodium-amber the page always meant to use for "needs a look":
     knee-jerk's default rule, tile-warn, the Avoid column, a radar
     candidate. One amber, not two competing oranges. */
  --attention:#ffb000; --attention-ink:#7a4b00; --attention-wash:#fff4d6;
  /* Who this number belongs to, everywhere that isn't "the crowd" or "the
     market": scatter's mine dot, the mini-league "you" row, the template
     pitch's outline, the wildcard's incoming tag. */
  --mine:#e6007e; --mine-ink:#a3005a;
  /* Anything priced by the bookmaker rather than modelled. */
  --market:#00708a; --market-wash:#e3f4f8;
  /* Everyone who is not you, on the league chart and the rivals list -
     replaces --bad red, which made a rival's good gameweek read as an
     error. */
  --rival:#1b5ce0;
  /* The one "top reward" treatment fixture ratings earn past a threshold -
     see .fx-premium. */
  --premium:#0b5f4a;

  --error:var(--bad); --success:var(--good); --error-container:var(--bad-wash);
  --surface:var(--white); --surface-variant:#f8f5ef;
  --on-surface:var(--ink); --on-surface-variant:var(--p70);
  --outline:var(--p30); --outline-variant:var(--p10);
  /* Warm chalk, not a purple-tinted grey - programme paper under white
     cards, not the generic SaaS ground the rest of this sheet is trying
     to avoid. */
  --ground:#f4f1ea; --bar:var(--p120); --on-bar:var(--white);
  --pitch-a:#0e7a3c; --pitch-b:#0a6733;
  /* The content column. It was 1120px, which on a desktop left the page
     using barely a third of the width while every grid inside it was
     squeezed to three 322px columns of 10px type. The density problem
     was never the amount of data - it was the width it had to fit. */
  --shell:1400px;
  --radius-xs:4px; --radius-s:8px; --radius-m:12px; --radius-l:16px;
  --shadow:0 1px 2px rgb(55 0 60 / 10%), 0 1px 8px rgb(55 0 60 / 6%);
}

/* One family for words, one for numbers. Archivo carries a width axis, so
   headings can be genuinely expanded rather than merely bolder - the wide
   caps read like the lettering on a perimeter board, and the contrast against
   normal-width body text does the work a second typeface would otherwise do.
   Every figure on the page is set in Plex Mono at tabular width, so columns
   of stats line up on the digit the way a results service does. */
:root{
  --sans:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--on-surface);
  font-family:var(--sans);
  font-size:15px; line-height:1.45;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3{
  margin:0; font-weight:700; text-wrap:balance;
  font-stretch:118%; letter-spacing:-0.005em; line-height:1.15;
}
h2{font-size:17px; text-transform:uppercase; letter-spacing:0.04em}
a{color:inherit}
.tnum{font-variant-numeric:tabular-nums}
/* Figures. `num` already marks every numeric cell in the tables. */
.num,.tnum,.stat-v,.delta,.fxc-score,.fxavg,.oi-value,.pr-total,.pr-hit,
.pr-bank,.cp-num,.hero-num{
  font-family:var(--mono); font-variant-numeric:tabular-nums;
  letter-spacing:-0.02em;
}

/* --- the delta chip -------------------------------------------------------
   One component for every number that has a good or bad reading - rank
   movement, price change, a fixture swinging, points against the average.
   A wedge for direction, a mono figure, and a wash behind it. It is the same
   shape everywhere so the page only has to teach it once, and it is the
   thing the design is meant to be remembered by, so nothing else on the page
   gets to be this loud. */
.delta{
  display:inline-flex; align-items:center; gap:4px;
  padding:2px 7px 2px 5px; border-radius:var(--radius-xs);
  font-size:12px; font-weight:600; line-height:1.3; white-space:nowrap;
  background:var(--surface-variant); color:var(--on-surface-variant);
}
.delta::before{
  content:""; width:0; height:0; flex:none;
  border-left:4px solid transparent; border-right:4px solid transparent;
}
.delta-up{background:var(--good-wash); color:var(--good-ink)}
.delta-up::before{border-bottom:5px solid currentColor}
.delta-down{background:var(--bad-wash); color:var(--bad-ink)}
.delta-down::before{border-top:5px solid currentColor}
.delta-flat::before{
  border:none; width:7px; height:2px; background:currentColor; border-radius:1px;
}
/* Amber is reserved for the one number that matters most in a card. */
.delta-key{background:var(--accent-wash); color:var(--accent-ink)}
.delta-key::before{display:none}

/* A stat that clears a threshold. Same badge grammar as the set-piece order
   pills, so "this is notable" already reads as a pill on this page. */
.good-pill{
  display:inline-flex; align-items:center; gap:4px; padding:1px 7px;
  border-radius:9999px; font-family:var(--mono); font-size:12px;
  font-weight:600; background:var(--good-wash); color:var(--good-ink);
}
.bad-pill{
  display:inline-flex; align-items:center; gap:4px; padding:1px 7px;
  border-radius:9999px; font-family:var(--mono); font-size:12px;
  font-weight:600; background:var(--bad-wash); color:var(--bad-ink);
}
/* The one surviving warn-ink usage: "borderline", not "needs a look". */
.warn-pill{
  display:inline-flex; align-items:center; gap:4px; padding:1px 7px;
  border-radius:9999px; font-family:var(--mono); font-size:12px;
  font-weight:600; background:var(--attention-wash); color:var(--warn-ink);
}

/* --- app chrome --- */
.topbar{
  background:var(--bar); color:var(--on-bar);
  border-bottom:1px solid rgb(255 255 255 / 12%);
  position:sticky; top:0; z-index:20;
}
.topbar-in{
  max-width:var(--shell); margin:0 auto; padding:12px 16px;
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

/* --- the chapter rail ---
   Planning is four chapters and about fourteen sections deep, and until now
   the only way to the bottom of it was the scrollbar. The rail is built from
   whichever chapters the open tab actually has, so it is never a menu of
   things that are not on screen, and it hides itself on a tab with only one
   chapter rather than showing a nav of length one. */
.railwrap{max-width:var(--shell); margin:0 auto; padding:0 16px 8px}
.railwrap[hidden]{display:none}
.rail{display:flex; gap:2px; flex-wrap:wrap}
.railbtn{
  appearance:none; border:0; background:none; cursor:pointer;
  font:inherit; font-size:12px; font-weight:600;
  color:rgb(255 255 255 / 62%); padding:4px 8px; border-radius:var(--radius-xs);
}
.railbtn:hover{color:#fff; background:rgb(255 255 255 / 10%)}
.railbtn[aria-current="true"]{color:var(--ink); background:var(--accent)}
/* The topbar is sticky, so a chapter scrolled to must clear it. The rail
   computes its own offset rather than relying on this, but a chapter
   reached any other way - a fragment link, a find-in-page - wants it too. */
.chapter{scroll-margin-top:92px}
/* On a phone the rail wrapped to three lines and took the sticky bar to
   137px - a sixth of the screen, permanently, to hold a nav. One line that
   scrolls sideways instead: the chapter names are short and the first two
   are always in view. */
@media (max-width:560px){
  .railwrap{padding:0 12px 6px}
  .rail{
    flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none;
    -webkit-overflow-scrolling:touch;
  }
  .rail::-webkit-scrollbar{display:none}
  .railbtn{font-size:11px; white-space:nowrap; flex:none}
}

.wrap{max-width:var(--shell);margin:0 auto;padding:16px}
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

/* --- chapter ---
   A screen section, above the cards it groups.

   There were two levels of heading on this page and they were one pixel
   apart - a bare 17px `card-head` sitting on the ground meant "everything
   below me", the same markup inside a card meant "this card", and at 17 vs
   16 nothing told them apart. Worse, which one a section got was arbitrary.

   So: a card's own title stays 16px uppercase, and the level above it is
   this - larger, expanded on Archivo's width axis, sentence case rather
   than a second set of caps, and ruled underneath in ink. The width axis
   is what separates the two, not weight, because both were already bold.
   A bare `card-head` on the ground is now always a mistake. */
.chapter{
  margin:30px 0 12px; padding-bottom:6px;
  border-bottom:2px solid var(--ink);
  display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
}
.chapter h2{
  font-size:22px; font-stretch:125%; text-transform:none;
  letter-spacing:-0.01em; line-height:1.2;
}
.chapter .sub{font-size:13px; color:var(--on-surface-variant)}
/* The first chapter in a panel already has the tab strip above it. */
.panel > .chapter:first-child{margin-top:6px}
@media (max-width:560px){.chapter h2{font-size:19px}}
.card-head .sub{font-size:13px;color:var(--on-surface-variant)}
/* A card's explanation used to print in full, permanently, under every
   title on the page - a sentence of small print nobody asked to read
   before they'd even looked at the numbers. One click reveals it instead. */
.infobtn{
  align-self:center; flex:none; width:16px; height:16px; border-radius:50%;
  border:1px solid var(--outline-variant); background:none; padding:0;
  color:var(--on-surface-variant); font:italic 700 11px/14px Georgia,serif;
  cursor:pointer;
}
.infobtn:hover,.infobtn[aria-expanded="true"]{
  border-color:var(--accent); color:var(--accent);
}
h2 .infobtn,h3 .infobtn,h4 .infobtn{margin-left:6px; vertical-align:middle}
.card-body{padding:16px}

/* --- hero ---
   Flat purple with a single green rule along the top, and the one tile the
   week turns on picked out in the same green. What was here before was a
   135-degree three-stop gradient - ink, then lilac, then accent, bleeding
   across the whole panel. That gradient was the thing that made the page
   look generated: it is the default move, it appears on every AI-built
   dashboard, and it says nothing about football. Flat colour and one rule
   say the same brand louder by not straining. */
.hero{
  background:var(--ink); border-top:3px solid var(--accent);
  color:var(--white); border-radius:var(--radius-m); padding:22px 18px;
  box-shadow:var(--shadow); position:relative; overflow:hidden;
}
.hero h1{font-size:clamp(23px,4vw,34px); font-stretch:125%; font-weight:700}
.hero .mgr{color:rgb(255 255 255 / 66%); font-size:14px; margin-top:3px}
/* The one sentence that says whether the week was good. Sits between the
   name and the numbers because it is the thing you read first and the
   tiles are the evidence for it. */
.hero-line{
  margin:14px 0 0; max-width:62ch; font-size:15px; line-height:1.5;
  color:rgb(255 255 255 / 88%); border-left:2px solid var(--accent);
  padding-left:11px;
}
.hero-line b{
  font-family:var(--mono); font-weight:600; color:var(--white);
  letter-spacing:-0.02em;
}
/* Chips inside a tile qualify the number, so they must not compete with it. */
.tile .v{display:flex; align-items:baseline; gap:7px; flex-wrap:wrap}
.tile .delta{
  font-size:10px; padding:1px 5px 1px 4px; font-weight:600;
  background:rgb(255 255 255 / 12%); color:rgb(255 255 255 / 82%);
}
.tile .delta-up{background:rgb(1 252 122 / 18%); color:#8affc4}
.tile .delta-down{background:rgb(230 0 35 / 22%); color:#ff9aa8}

.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr)); gap:10px; margin-top:18px}
.tile{
  background:rgb(255 255 255 / 7%); border-radius:var(--radius-s);
  padding:10px 12px; border:1px solid rgb(255 255 255 / 9%);
}
.tile .k{font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:rgb(255 255 255 / 62%)}
.tile .v{
  font-family:var(--mono); font-variant-numeric:tabular-nums;
  font-size:25px; font-weight:600; line-height:1.1; margin-top:3px;
  letter-spacing:-0.03em;
}
.tile .n{font-size:12px; color:rgb(255 255 255 / 58%)}
/* Only two of the six tiles ever carry a tone - see render() for which and
   why. Same three-way good/warn/bad vocabulary the delta chips already
   use, just applied to the whole tile instead of a chip inside it. */
.tile.tile-good{background:rgb(1 252 122 / 9%); border-color:rgb(1 252 122 / 26%)}
.tile.tile-good .v{color:#8affc4}
.tile.tile-warn{background:rgb(255 176 0 / 14%); border-color:rgb(255 176 0 / 34%)}
.tile.tile-warn .v{color:#ffd166}
.tile.tile-bad{background:rgb(230 0 35 / 11%); border-color:rgb(230 0 35 / 28%)}
.tile.tile-bad .v{color:#ff9aa8}

/* --- tabs --- */
.tabs{display:flex; gap:4px; margin:16px 0 12px; flex-wrap:wrap}
.tab{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface); font:inherit; font-weight:600; font-size:14px;
  padding:8px 16px; border-radius:9999px; cursor:pointer;
}
.tab[aria-selected="true"]{background:var(--ink); color:#fff; border-color:var(--ink)}
.tab:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.panel[hidden]{display:none}

/* --- pick-team pitch toggle: a nested, quieter version of .tab/.tabs,
   scoped inside one card rather than switching the whole page --- */
.pkview{display:flex; gap:6px; padding:10px 16px; border-bottom:1px solid var(--outline-variant)}
.pkbtn{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface-variant); font:inherit; font-weight:600; font-size:12px;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.pkbtn[aria-selected="true"]{background:var(--ink); color:#fff; border-color:var(--ink)}
.pkbtn:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.pkpanel[hidden]{display:none}

/* --- pitch --- */
.pitch{
  background:
    repeating-linear-gradient(180deg,
      var(--pitch-a) 0 12.5%,var(--pitch-b) 12.5% 25%);
  padding:18px 10px; position:relative;
}
.pitch::before{
  content:""; position:absolute; inset:10px; border:2px solid rgb(255 255 255 / 22%);
  border-radius:var(--radius-xs); pointer-events:none;
}
.row{display:flex; justify-content:center; gap:8px; flex-wrap:wrap;
  margin-bottom:14px; position:relative; z-index:1}

/* --- pitch markings ------------------------------------------------------
   The pitch was four mown stripes and a rectangle. The lines are what make
   eleven shirts read as a team sheet rather than as cards on a green panel,
   and they are the one piece of custom drawing this page had no excuse for
   not having. Same 22% white as the touchline: furniture, never something
   competing with a shirt.

   Horizontal extents are percentages, vertical ones are pixels. A pitch
   here is exactly as tall as its rows make it, so a penalty area measured
   proportionally in both directions would deform from one squad shape to
   the next. Fixed depth and proportional width is how the box keeps its
   shape at any height.

   The stripes moved from a 60px repeat to a 12.5% one for the same reason:
   at a fixed pitch a mini pitch showed two and a half bands where the full
   one showed eight. */
.pmk{
  position:absolute; inset:10px; pointer-events:none; z-index:0;
  --mk:rgb(255 255 255 / 22%);
}
.pmk i{position:absolute; border:2px solid var(--mk)}
/* Halfway line, then the centre circle and spot on top of it. */
.pmk-half{left:0; right:0; top:50%; border-width:2px 0 0}
.pmk-circle{
  left:50%; top:50%; width:84px; height:84px; margin:-42px 0 0 -42px;
  border-radius:50%;
}
.pmk-spot{
  left:50%; top:50%; width:6px; height:6px; margin:-3px 0 0 -3px;
  border:0; border-radius:50%; background:var(--mk);
}
/* Penalty area, the six-yard box inside it, and the goal beyond the line -
   all three at both ends. The edge that would sit on the goal line is
   dropped, because the touchline is already drawing it. */
.pmk-box{left:50%; width:46%; margin-left:-23%; height:46px}
.pmk-six{left:50%; width:22%; margin-left:-11%; height:20px}
.pmk-goal{left:50%; width:11%; margin-left:-5.5%; height:7px}
.pmk-t{top:0; border-top-width:0}
.pmk-b{bottom:0; border-bottom-width:0}
.pmk-goal.pmk-t{top:-7px; border-width:2px 2px 0}
.pmk-goal.pmk-b{bottom:-7px; border-width:0 2px 2px}
/* Corner arcs: a quarter circle struck from each corner of the touchline. */
.pmk-arc{width:14px; height:14px}
.pmk-arc-tl{top:0; left:0; border-width:0 2px 2px 0; border-radius:0 0 100% 0}
.pmk-arc-tr{top:0; right:0; border-width:0 0 2px 2px; border-radius:0 0 0 100%}
.pmk-arc-bl{bottom:0; left:0; border-width:2px 2px 0 0; border-radius:0 100% 0 0}
.pmk-arc-br{bottom:0; right:0; border-width:2px 0 0 2px; border-radius:100% 0 0 0}
/* A small pitch keeps the same lines at the same relative weight - the
   point of the mini pitch is that it is recognisably the same object. */
.pitch.mini .pmk-circle{width:50px; height:50px; margin:-25px 0 0 -25px}
.pitch.mini .pmk-box{height:26px}
.pitch.mini .pmk-six{height:11px}
.pitch.mini .pmk-goal{height:5px}
.pitch.mini .pmk-goal.pmk-t{top:-5px}
.pitch.mini .pmk-goal.pmk-b{bottom:-5px}
.pitch.mini .pmk-arc{width:9px; height:9px}
.pitch.mini .pmk i{border-width:1px}
.pitch.mini .pmk-half{border-width:1px 0 0}
.pitch.mini .pmk-spot{width:4px; height:4px; margin:-2px 0 0 -2px; border:0}
.row:last-child{margin-bottom:0}
.pl{position:relative; width:92px; background:var(--surface); border-radius:var(--radius-s); overflow:hidden; box-shadow:0 2px 6px rgb(0 0 0 / 25%)}
.pl .crest{display:flex; align-items:center; justify-content:center; height:44px; background:var(--surface-variant)}
.pl .crest img{width:32px;height:32px;object-fit:contain}
.pl .crest .letters{font-weight:700;font-size:13px;color:var(--on-surface-variant)}
.pl .nm{
  background:var(--ink); color:#fff; font-size:12px; font-weight:600;
  padding:3px 4px; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.pl .sc{display:flex; text-align:center; align-items:baseline}
.pl .sc div{
  flex:1; min-width:0; padding:4px 1px;
  transition:font-size .14s, flex-grow .14s, color .14s;
}
.pl .sc .g,.pl .sc .x{border-left:1px solid var(--outline-variant)}
/* Exactly one of the three is forward at a time, and it is forward by a
   long way: the point of a card this small is that one number should be
   readable across the room and the other two only when you look for them.
   The chosen cell also takes extra width, since 15px digits do not fit a
   third of a 92px card. */
.ovwrap .sc div{color:var(--p60); font-weight:500; font-size:10px}
.ovwrap.emph-p .sc .p,
.ovwrap.emph-g .sc .g,
.ovwrap.emph-x .sc .x{
  color:var(--on-surface); font-weight:700; font-size:15px; flex-grow:1.7;
  letter-spacing:-0.04em;
}
@media (prefers-reduced-motion:reduce){.pl .sc div{transition:none}}

/* Plain text, not pills: this sits in the same row as the view tabs and two
   sets of pills side by side would have read as two sets of tabs. Selected
   is simply the bold one. */
.statsel{display:flex; align-items:center; gap:2px; margin-left:auto}
/* An author `display` beats the user-agent's [hidden] rule at equal
   specificity, so the JS setting .hidden on this group did nothing and the
   figure selector stayed on screen in the one view where it means nothing. */
.statsel[hidden]{display:none}
.stbtn{
  appearance:none; border:0; background:none; cursor:pointer;
  color:var(--on-surface-variant); font:inherit; font-family:var(--mono);
  font-size:11px; font-weight:500; padding:5px 6px; border-radius:var(--radius-xs);
}
.stbtn[aria-pressed="true"]{color:var(--on-surface); font-weight:700}
.stbtn:hover{color:var(--on-surface)}
.stbtn:focus-visible{outline:3px solid var(--accent); outline-offset:1px}
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
.pk-form.hot{color:var(--ink); font-weight:700}
.pk-spark{width:11px; height:11px; vertical-align:-1px; margin-right:2px}
.benchstrip{background:var(--surface-variant); padding:12px 10px}
.benchstrip .lbl{
  font-size:11px; text-transform:uppercase; letter-spacing:0.06em;
  color:var(--on-surface-variant); text-align:center; margin-bottom:8px; font-weight:600;
}
.bbpitch{padding:16px 10px}

/* A name only suggested, not already owned - the Bench Boost proposed bench
   and the Wildcard "Proposed" pitch both use this on top of the ordinary
   .pl/.pk shirt card, so the same visual language marks "new" everywhere a
   proposed squad appears on the page. */
.pl-incoming{
  outline:2px solid var(--mine); outline-offset:2px;
  box-shadow:0 2px 6px rgb(0 0 0 / 25%), 0 0 0 5px rgb(230 0 126 / 12%);
}
.pl-in-tag{
  position:absolute; top:3px; right:3px; z-index:2; padding:1px 5px;
  border-radius:9999px; background:var(--mine); color:#fff;
  font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:.04em;
}

/* --- Wildcard before/after mini pitches ---------------------------------
   A scaled-down .pitch, not a second bespoke component - same shirts,
   smaller and side by side, so "would I actually want this squad" is a
   five-second glance rather than a table read. */
.wcpitches{display:flex; gap:16px; flex-wrap:wrap; margin-top:14px}
.wcpitch{flex:1 1 260px; min-width:0}
.wcpitch h4{
  margin:0 0 8px; font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:var(--on-surface-variant); text-align:center;
}
.pitch.mini{padding:12px 6px; border-radius:var(--radius-s)}
/* Scoped to .wcpitch, not .pitch.mini, so the same small-card sizing also
   reaches the bench strip below the pitch - a sibling of .pitch.mini in
   the markup, not a descendant of it. */
.wcpitch .row{gap:5px; margin-bottom:8px}
.wcpitch .pl{width:60px}
.wcpitch .pl .crest{height:30px}
/* Same specificity as .pl .crest img.kit/.crestimg (three classes, one
   element) further down this sheet, which otherwise wins the 40px/32px
   full-size shirt image on source order alone and overflows this 30px-tall
   crest box - matching the class names here, not just "img", closes that
   tie in this rule's favour. */
.wcpitch .pl .crest img.kit,
.wcpitch .pl .crest img.crestimg{width:20px; height:20px}
.wcpitch .pl .nm{font-size:9px; padding:2px 3px}
.wcpitch .pl .pk-fx{padding:2px 2px 0}
.wcpitch .pl .fxpill{padding:1px 4px; font-size:8px; gap:2px}
.wcpitch .pl-in-tag{font-size:7px; padding:0 4px; top:2px; right:2px}
.wcpitch .benchstrip{padding:10px 6px; border-radius:var(--radius-s); margin-top:8px}
.wcpitch .benchstrip .lbl{margin-bottom:6px}
@media (max-width:640px){.wcpitches{flex-direction:column}}

/* --- collapsible cards --- */
/* A card that is also a <details>. The generic `details summary` rules below
   supply the chevron; these restore the card-head look the plain <div> had,
   and drop the row divider a card should not have. */
details.card{border-bottom:none}
details.collapsible > summary.card-head{cursor:pointer; list-style:none}
details.collapsible > summary.card-head::-webkit-details-marker{display:none}
details.collapsible > summary.card-head:hover{background:var(--surface-variant)}
details.collapsible > summary.card-head:focus-visible{outline:3px solid var(--accent); outline-offset:-3px}
details.collapsible:not([open]) > summary.card-head{border-bottom:none}
/* Shut by default and quiet about it: reference material, not a headline. */
.lastseason{margin-top:12px}
.lastseason > summary.card-head h2{color:var(--on-surface-variant)}

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
tbody tr.me{background:#fff0f7}
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
.meter-fill{display:block; height:100%; background:var(--accent); border-radius:9999px}
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
.tag-mine{background:var(--accent); color:#fff}
.pw-alert{
  background:var(--surface-variant); border-left:4px solid var(--accent);
  border-radius:var(--radius-s); padding:10px 14px; margin-bottom:16px; font-size:14px;
}

/* --- scatter --- */
:root{--mark-mkt:#bcae9e; --mark-mine:var(--mine); --mark-outlier:var(--ink)}
.chartfilter{display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px}
.chip{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface); font:inherit; font-size:13px; font-weight:600;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.chip[aria-pressed="true"]{background:var(--ink); color:#fff; border-color:var(--ink)}
.chip:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
/* The viewBox is the chart's own coordinate space, so a container wider
   than it upscales every dot, stroke and label together - at the 1400px
   shell a 760-wide box was being blown up 1.76x and the 11px tick labels
   were landing at 19px. The box is 1040 wide now, and capped there, so
   the chart fills the card at 1:1 and only ever scales down. */
.scatter{width:100%; min-width:560px; max-width:1040px; height:auto;
  display:block; margin:0 auto}
.scatter .grid line{stroke:var(--outline-variant); stroke-width:1}
.scatter .axlab text{fill:var(--on-surface-variant); font-size:11px; font-variant-numeric:tabular-nums}
.scatter .axtitle{fill:var(--on-surface-variant); font-size:12px; font-weight:600}
.scatter .mkt circle{fill:var(--mark-mkt); opacity:.55}
.scatter .mine circle{fill:var(--mark-mine); stroke:var(--surface); stroke-width:2}
/* Furthest from the norm, on whichever two measures are picked right now -
   a market dot (not yours) gets this hollow ring instead of the plain
   market fill, so it reads as "flagged" rather than as a third colour. */
.scatter .outlier circle:first-child{
  fill:none; opacity:.9; stroke:var(--mark-outlier); stroke-width:2;
}
.scatter .pt{cursor:pointer}
.scatter .pt:hover circle{opacity:1; stroke:var(--on-surface); stroke-width:2}
.scatter .ptlabel{
  fill:var(--on-surface); font-size:11px; font-weight:600; pointer-events:none;
  paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round;
}
.scatter .ptlabel.outlier-label{fill:var(--mark-outlier)}
.scatter .hide{display:none}

/* The enlarged hit target must out-specify the mark fill rules above,
   or it paints as a second, much fatter dot. */
.scatter .mkt circle.hit, .scatter .mine circle.hit{
  fill:transparent; opacity:0; stroke:none;
}
.scatter .pt:focus{outline:none}
.scatter .pt:focus-visible circle:first-child{stroke:var(--accent); stroke-width:3}
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
.key.outlier{background:var(--mark-outlier)}

/* --- league position over time -------------------------------------------
   One line per manager, straight segments between gameweeks - there is
   nothing to smooth between two discrete, already-final scores. */
.lptoggle{display:flex; gap:6px; margin-bottom:10px}
.lpbtn{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface-variant); font:inherit; font-weight:600; font-size:12px;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.lpbtn[aria-pressed="true"]{background:var(--ink); color:#fff; border-color:var(--ink)}
.lpbtn:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
/* Capped for the same reason as .scatter - see the note there. */
.lpchart{width:100%; min-width:520px; max-width:1040px; height:auto;
  display:block; margin:0 auto}
.lpgrid line{stroke:var(--outline-variant); stroke-width:1}
.lpgrid text{fill:var(--on-surface-variant); font-size:10px; font-variant-numeric:tabular-nums}
.lpline{transition:opacity .15s}
.lpline.dim{opacity:.15}
.lphit{cursor:pointer}
.lpval{
  font-size:10px; font-weight:700; font-variant-numeric:tabular-nums;
  opacity:0; transition:opacity .15s; pointer-events:none;
}
.lpline.active .lpval{opacity:1}
.lplegend{
  list-style:none; margin:12px 0 0; padding:0; display:flex; flex-wrap:wrap;
  gap:8px 14px; font-size:12px;
}
.lpleg{
  display:flex; align-items:center; gap:6px; cursor:pointer; color:var(--on-surface-variant);
  transition:opacity .15s; border-radius:var(--radius-xs);
}
.lpleg.dim{opacity:.35}
.lpleg.lp-mine{font-weight:700; color:var(--ink)}
.lpleg:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.lpswatch{width:10px; height:10px; border-radius:50%; flex:none}

/* --- captaincy radar ---
   Three candidate colours, each a fill/stroke pair from the page's own
   palette: full-strength purple, mine-magenta, and the amber "third
   state" used for defensive thresholds - each fill uses the vivid
   version for real hue separation, each stroke the darker text-safe
   version so the outline stays legible on white. Green is dropped here on
   purpose: green means "good" everywhere else on the page, and a green
   radar shape read as the recommended one regardless of what the numbers
   said. Capped at three candidates deliberately: a fourth colour pulled
   from this palette (the mid-purple step) sat too close to the ink purple
   to tell apart at a glance, and three is what the shape needs to be
   usefully read. */
:root{
  --radar-c0-fill:var(--ink); --radar-c0-stroke:var(--ink);
  --radar-c1-fill:var(--mine); --radar-c1-stroke:var(--mine-ink);
  --radar-c2-fill:var(--attention); --radar-c2-stroke:var(--attention-ink);
}
.cap-layout{display:flex; align-items:center; gap:20px; flex-wrap:wrap}
/* Fixed width (not max-width) and a fixed-height readout line below - both
   used to be auto-sized to their own content, so a longer or shorter hover
   readout resized .cap-side itself. With align-items:center on the row,
   that resize recentred the whole column (the names visibly shifted up or
   down) and, since .cap-side's width could shift too, nudged the chart
   sideways as its flex sibling. Fixed dimensions here mean hovering never
   changes either box's size, so nothing next to it has to move. */
.cap-side{flex:0 0 240px; width:240px; display:flex; flex-direction:column; gap:12px}
/* Centred rather than pushed to the chart's own right edge, and a wider cap
   on both the column and the chart it holds - a 360px chart right-aligned
   inside a much wider flex column left a dead gap between the legend and
   the chart itself on any card wider than about 620px. A bigger chart
   drawn dead-centre in the space it's given closes most of that gap
   directly instead of needing a second column to fill it. */
.cap-chart{
  flex:1 1 380px; display:flex; flex-direction:column; align-items:center;
  gap:10px; margin:0;
}
.radar{width:100%; min-width:320px; max-width:600px; height:auto; display:block}
.radar-ring{fill:none; stroke:var(--outline-variant); stroke-width:1}
.radar-axis-line{stroke:var(--outline-variant); stroke-width:1}
.radar-label{fill:var(--on-surface-variant); font-size:12px; font-weight:700}
.radar-fill{
  fill-opacity:.22; stroke-width:2;
  transition:fill-opacity .15s, opacity .15s, stroke-width .15s;
}
.radar-dot{
  stroke:var(--surface); stroke-width:1.5; cursor:pointer;
  transition:r .15s;
}
.radar-area{
  transform-box:view-box; transform-origin:210px 195px;
  transition:transform .18s ease, opacity .15s;
}
.radar-area.dim{opacity:.25}
.radar-area.active{transform:scale(1.045)}
.radar-area.active .radar-fill{fill-opacity:.34; stroke-width:3}
.radar-area.active .radar-dot{r:5.5}
.radar-c0 .radar-fill, .radar-c0 .radar-dot{fill:var(--radar-c0-fill); stroke:var(--radar-c0-stroke)}
.radar-c1 .radar-fill, .radar-c1 .radar-dot{fill:var(--radar-c1-fill); stroke:var(--radar-c1-stroke)}
.radar-c2 .radar-fill, .radar-c2 .radar-dot{fill:var(--radar-c2-fill); stroke:var(--radar-c2-stroke)}
.radar-legend{
  list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px;
}
.radar-leg{
  display:flex; align-items:flex-start; gap:8px; font-size:13px; cursor:pointer;
  transition:opacity .15s; border-radius:var(--radius-xs);
}
.radar-leg:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.radar-leg.dim{opacity:.4}
.radar-leg.active .radar-leg-name{color:var(--ink)}
.radar-swatch{width:10px; height:10px; border-radius:50%; flex:none; margin-top:4px}
.radar-swatch.radar-c0{background:var(--radar-c0-fill)}
.radar-swatch.radar-c1{background:var(--radar-c1-stroke)}
.radar-swatch.radar-c2{background:var(--radar-c2-fill)}
.radar-leg-text{display:flex; flex-direction:column; gap:1px}
.radar-leg-name{font-weight:600}
.radar-leg-sub{color:var(--on-surface-variant); font-variant-numeric:tabular-nums; font-size:12px}
.radar-readout{
  margin:0; font-size:13px; line-height:1.4; height:4.2em; overflow:hidden;
  color:var(--on-surface-variant); font-variant-numeric:tabular-nums;
  border-top:1px solid var(--outline-variant); padding-top:8px;
}
.venue-icon{
  width:12px; height:12px; vertical-align:-1px; margin-right:4px;
  color:var(--on-surface-variant); flex:none;
}
/* Hover shows one metric at a time; a click pins all five instead - "how
   does he actually break down" needs the full set together. A separate
   boxed panel elsewhere on the card used to hold those five, which read as
   a second block bolted beside the chart it described. Pinning now draws
   directly on the chart instead: each axis's plain name swaps for a short
   arrow running from that shape's own vertex out to a label and value, in
   the exact spot the name sat a moment ago - a mind-map reading of one
   shape's own numbers, nothing elsewhere on the card changing size to
   show it. */
.radar-callout-line{stroke-width:1.5; opacity:.85}
.radar-callout-label{
  font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; fill:var(--on-surface-variant);
}
.radar-callout-value{font-size:17px; font-weight:800; font-variant-numeric:tabular-nums}
.radar-callout:focus-visible .radar-callout-value{outline:2px solid var(--accent); outline-offset:2px}
.radar-c0 .radar-callout-line{stroke:var(--radar-c0-stroke)}
.radar-c1 .radar-callout-line{stroke:var(--radar-c1-stroke)}
.radar-c2 .radar-callout-line{stroke:var(--radar-c2-stroke)}
.radar-c0 .radar-callout-value{fill:var(--radar-c0-stroke)}
.radar-c1 .radar-callout-value{fill:var(--radar-c1-stroke)}
.radar-c2 .radar-callout-value{fill:var(--radar-c2-stroke)}
/* The arrowhead <path> lives inside <defs>, one <marker> per candidate
   colour - see captaincy.js for why a single shared marker cannot just
   follow the referencing line's own colour. */
.radar-arrow-head.radar-c0{fill:var(--radar-c0-stroke)}
.radar-arrow-head.radar-c1{fill:var(--radar-c1-stroke)}
.radar-arrow-head.radar-c2{fill:var(--radar-c2-stroke)}

/* --- ownership doughnuts + carousel --- */
.carnav{margin-left:auto; display:flex; gap:6px}
.arrow{
  appearance:none; width:32px; height:32px; border-radius:50%;
  border:1px solid var(--outline); background:var(--surface); color:var(--on-surface);
  font-size:18px; line-height:1; cursor:pointer; font-family:inherit;
}
.arrow:hover{background:var(--surface-variant)}
.arrow:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.carousel{
  list-style:none; margin:0; padding:4px; display:flex; gap:12px;
  overflow-x:auto; scroll-snap-type:x mandatory; scroll-behavior:smooth;
}
.carousel:focus-visible{outline:3px solid var(--accent); outline-offset:2px; border-radius:var(--radius-s)}
.ocard{
  flex:0 0 148px; scroll-snap-align:start; text-align:center;
  background:var(--surface-variant); border-radius:var(--radius-m);
  padding:12px 8px; border:2px solid transparent;
}
.ocard.mine{border-color:var(--accent); background:var(--surface)}
.donut{width:90px; height:90px; display:block; margin:0 auto}
.dtrack{fill:none; stroke:var(--outline-variant); stroke-width:9}
.dval{fill:none; stroke-width:9; stroke-linecap:round}
.dnum{fill:var(--on-surface); font-size:19px; font-weight:700}
.dsub{fill:var(--on-surface-variant); font-size:11px}
.oname{margin:8px 0 0; font-weight:700; font-size:14px}
.oteam,.onote{margin:1px 0 0; font-size:11px; color:var(--on-surface-variant)}
.oyou{margin:4px 0 0; font-size:11px; font-weight:700; color:var(--good-ink)}
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
.axpick select:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
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
.spicon{width:17px; height:17px; flex:none; color:var(--accent)}
/* --- price movement: risers against fallers ---
   Same two-column grammar as the set-piece card, since the question has
   the same shape - a short grouped list where the group is the point. */
.pmwrap{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:14px; padding:0 14px 14px;
}
.pmgroup h4{
  display:flex; align-items:center; gap:6px; margin:0 0 8px;
  font-size:11px; text-transform:uppercase; letter-spacing:0.06em;
}
.pm-up h4{color:var(--good-ink)}
.pm-down h4{color:var(--bad-ink)}
.pmicon{width:15px; height:15px; flex:none}
.pmlist{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:8px}
.pmname{display:block; font-size:13px; font-weight:600}
.pmprice{
  display:block; font-family:var(--mono); font-size:11px;
  color:var(--on-surface-variant); letter-spacing:-0.02em;
}
.pmprice i{font-style:normal; padding:0 4px; opacity:.65}
.pm-up .pmprice{color:var(--good-ink)}
.pm-down .pmprice{color:var(--bad-ink)}

.splist{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:5px}
.splist li{display:flex; align-items:baseline; gap:8px; font-size:13px}
.sprank{
  flex:none; width:19px; height:19px; border-radius:50%; font-size:11px;
  font-weight:700; display:grid; place-items:center;
  background:var(--surface-variant); color:var(--on-surface-variant);
}
.splist li.first .sprank{background:var(--accent); color:#fff}
.spname{font-weight:600}
.spteam{margin-left:auto; color:var(--on-surface-variant); font-size:11px}
.mkt-cs,.mkt-xg{color:var(--market); font-weight:700}

/* --- pick team: the eleven fold into a column, the bars extend beside it ---
   No length is transitioned here, for the reason recorded further down this
   file the last time it was tried: Chrome will not interpolate a grid track
   between 0fr and 1fr, and a max-width transition sticks at its start value.
   So the layout snaps and every bit of the motion is a transform or an
   opacity, which are reliable and cheap to composite. */
.pkstage{display:flex; align-items:flex-start}
.pkboard{flex:1 1 auto; min-width:0}
.epside{flex:0 0 0; width:0; overflow:hidden; opacity:0; padding:0}
/* Matches .epside's own top padding, so the two headers - and therefore the
   two lists under them - start on the same line. */
.pkstage.ep-on .pkboard{flex:0 0 214px; padding:12px 0 0 12px}
.pkstage.ep-on .epside{
  flex:1 1 auto; width:auto; opacity:1; padding:12px 16px 14px;
  transition:opacity .28s ease .06s;
}
/* These two headers exist to be the same height as each other: the eleven
   on the left and their bars on the right have to start level, or every bar
   reads as belonging to the card above it. */
.epside-head,.pkboard-head{
  display:flex; align-items:baseline; gap:7px; height:34px;
  border-bottom:1px solid var(--outline-variant); margin-bottom:10px;
}
.pkboard-head{
  display:none; padding:0 2px; font-size:10px; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em;
  color:var(--on-surface-variant); align-items:flex-end; padding-bottom:8px;
}
.pkstage.ep-on .pkboard-head{display:flex}
.epside-k,.epside-u{font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:var(--on-surface-variant)}
.epside-head b{font-size:24px; line-height:1}
/* The 12px is the pitch's own top padding, which sits between the left
   header and the first card and has no counterpart on this side. */
.epclist{list-style:none; margin:0; padding:12px 0 0; display:flex;
  flex-direction:column; gap:6px}
/* Row height and gap are the pick card's, so bar N sits level with card N.
   Change one and the other has to move with it. */
.epcr{display:flex; align-items:center; gap:10px; height:42px}
.epcr .epbar{flex:1 1 auto; min-width:0; transform-origin:left center}
.epcr .eptot{flex:0 0 38px; text-align:right; font-size:14px}
.epcname{display:none; flex:0 0 96px; font-size:12px; font-weight:600;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}

.pkstage.ep-on .pitch{
  display:flex; flex-direction:column; gap:6px; padding:12px 10px;
  background:var(--pitch-b);
}
.pkstage.ep-on .pitch::before,
.pkstage.ep-on .pmk{display:none}
.pkstage.ep-on .pitch .row{display:contents}
.pkstage.ep-on .benchstrip{display:none}
.pkstage.ep-on .pk{
  width:auto; height:42px; display:flex; align-items:center;
  border-radius:var(--radius-xs);
  animation:pkfold .34s cubic-bezier(.2,.7,.3,1) both;
}
.pkstage.ep-on .pk .crest{
  height:42px; width:38px; flex:none; background:none;
}
.pkstage.ep-on .pk .crest img{width:24px; height:24px}
.pkstage.ep-on .pk .nm{
  flex:1 1 auto; min-width:0; background:none; color:var(--on-surface);
  text-align:left; padding:0 4px 0 0; font-size:12px;
}
.pkstage.ep-on .pk .pk-fx{flex:none; padding:0 8px 0 0}
/* The form line is a second row of text this strip has no height for, and
   the bar beside it now says the same thing better. */
.pkstage.ep-on .pk .pk-form{display:none}
.pkstage.ep-on .pk .arm{top:50%; left:2px; transform:translateY(-50%);
  width:16px; height:16px; font-size:10px}
@keyframes pkfold{
  from{opacity:0; transform:translateX(-12px)}
  to{opacity:1; transform:none}
}

/* Same plain-text treatment as the figure selector beside it - this row
   should never look like two sets of tabs. */
.epbtn{
  appearance:none; border:0; background:none; cursor:pointer; margin-left:auto;
  color:var(--on-surface-variant); font:inherit; font-family:var(--mono);
  font-size:11px; font-weight:500; padding:5px 6px;
  border-radius:var(--radius-xs);
}
.epbtn::before{
  content:""; display:inline-block; width:7px; height:7px; margin-right:6px;
  border-radius:50%; vertical-align:1px;
  border:1.5px solid var(--outline); background:none;
}
.epbtn[aria-pressed="true"]{color:var(--on-surface); font-weight:700}
.epbtn[aria-pressed="true"]::before{background:var(--good); border-color:var(--good-ink)}
.epbtn:hover{color:var(--on-surface)}
.epbtn:focus-visible{outline:3px solid var(--accent); outline-offset:1px}

@media (max-width:760px){
  /* Two columns of this width would leave the bars a few pixels wide. The
     board keeps the full width and the column stacks under it. */
  .pkstage{flex-direction:column}
  .pkstage.ep-on .pkboard{flex:1 1 auto; width:100%}
  .pkstage.ep-on .epside{width:100%; padding:12px 0 0}
  /* Nothing sits level with these rows any more, so each says who it is. */
  .epcname{display:block}
  .epcr{height:34px}
  .epside-head,.pkboard-head{height:auto; min-height:30px}
}
@media (prefers-reduced-motion:reduce){
  .pkstage.ep-on .pk{animation:none}
  .pkstage.ep-on .epside{transition:none}
}

/* The reveal is driven from JavaScript rather than a keyframe. A delayed CSS
   animation with fill-mode both holds its opening frame, and that kept the
   bars pinned at scaleX(0); the Web Animations API with fill "none" cannot
   leave anything stuck, because the element returns to its own styles the
   moment the animation ends. */

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
  background:var(--market-wash); border-top:3px solid var(--oi-tone);
}
.oi-icon{width:20px; height:20px; color:var(--oi-tone)}
.oi-good{--oi-tone:var(--success)}
.oi-bad{--oi-tone:var(--error)}
.oi-info{--oi-tone:var(--market)}
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
  background:var(--surface-variant);
  border-top:3px solid var(--cp-tone,var(--outline-variant));
}
/* The rule and the pill below it were disagreeing: every one of the four
   cards wore the same bright accent along the top while the pill under it
   said "flexible". Four identical accents in one grid is decoration, and
   it was the loudest decoration on the page. The rule now carries the
   confidence the card already states, so the accent is spent on the one
   chip that has actually earned a week. */
.cp-strong{--cp-tone:var(--good)}
.cp-watch{--cp-tone:var(--p40)}
.cp-flexible{--cp-tone:var(--outline-variant)}
.cp.used{opacity:.55}
.cp-label{margin:0; font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant)}
.cp-gw{margin:4px 0 0; font-size:22px; font-weight:700; font-variant-numeric:tabular-nums}
.cp-reason{margin:4px 0 0; font-size:13px; color:var(--on-surface-variant)}
.cp-conf{
  display:inline-block; margin-top:8px; padding:2px 8px; border-radius:9999px;
  font-size:11px; font-weight:700;
}
/* Not var(--success) as a background: that token is the FPL green, and
   white on it measures about 1.3:1. The dark green does the same job. */
.cp-conf-strong{background:var(--good-ink); color:#fff}
.cp-conf-watch{background:var(--p40); color:var(--ink)}
.cp-conf-flexible{background:var(--outline-variant); color:var(--on-surface-variant)}
.cp-used-tag{font-size:11px; color:var(--on-surface-variant); margin-top:8px}

/* --- predicted line-ups card -------------------------------------------
   A donut and an exception list. Fifteen rows saying "starting" is fifteen
   rows of nothing. Full squad, XI and bench cycle through the one donut,
   since a gap in the bench and the same gap in the XI are not the same
   question. */
.lcnav{
  display:flex; align-items:center; justify-content:center; gap:10px;
  margin-bottom:6px;
}
.lc-navlabel{
  font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:var(--on-surface-variant); min-width:7em;
  text-align:center;
}
/* Boxed the same way the mini-league ownership doughnuts are - a surface
   tint and real padding round the ring, rather than it floating loose
   against the card background with only a margin to separate it. */
.lc-donut-row{
  display:flex; justify-content:center; margin-bottom:10px;
  padding:14px 8px; border-radius:var(--radius-m); background:var(--surface-variant);
}
.lcpanel{
  padding-top:10px; border-top:1px solid var(--outline-variant);
}
.lc-clear{margin:0; font-size:12px; color:var(--on-surface-variant); text-align:center}
.lc-block + .lc-block{margin-top:10px}
.lc-block h4{
  margin:0 0 5px; padding:0 14px; display:flex; align-items:center; gap:6px;
  font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em;
}
.lc-block h4 .ic{width:14px; height:14px; flex:none}
.lc-out h4{color:var(--bad-ink)}
.lc-unk h4{color:var(--attention-ink)}
.lc-block ul{list-style:none; margin:0; padding:0; display:grid; gap:5px}
.lc-block li{display:flex; align-items:center; gap:7px; flex-wrap:wrap}
.lc-name{font-size:13px; font-weight:600}
.lc-club{font-size:10px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--p60)}
.lc-fx{margin-left:auto; display:flex; gap:3px}

/* --- fixture swings -------------------------------------------------------
   "Kind"/"hard" comes from FPL's own FDR; the fixtures themselves are drawn
   with our own rating pills so the claim is checkable, not just a number. */
.fsw-kind h4{color:var(--good-ink)}
.fsw-hard h4{color:var(--bad-ink)}
.fsw-row{display:flex; align-items:center; gap:8px; flex-wrap:wrap}
.fsw-club{font-size:13px; font-weight:600}
.fsw-fdr{font-size:10px; font-family:var(--mono); color:var(--on-surface-variant)}
.fsw-fx{margin-left:auto; display:flex; gap:3px; flex-wrap:wrap}

/* --- fixture run summary ------------------------------------------------
   Best/worst three, model and FDR side by side - two rankings because they
   answer different questions, not one dressed up twice. */
.frowrap{display:flex; flex-direction:column; gap:18px}
.frogroup h4{margin:0; font-size:13px; font-weight:700}
.fronote{margin:2px 0 10px; font-size:12px; color:var(--on-surface-variant)}
.frocols{display:grid; grid-template-columns:1fr 1fr; gap:14px}
.frocol h5{margin:0 0 6px; font-size:10px; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em}
.frocol.fro-col-good h5{color:var(--good-ink)}
.frocol.fro-col-bad h5{color:var(--bad-ink)}
.frolist{list-style:none; margin:0; padding:0; display:grid; gap:6px}
.fro-row{
  display:flex; align-items:center; gap:8px; padding:6px 9px 6px 8px;
  border-radius:var(--radius-s); background:var(--surface-variant);
  border-left:3px solid transparent;
}
/* A pale wash alone read almost the same on both sides at a glance - a
   solid colour edge plus a stronger fill make "good" and "bad" tell apart
   without reading the number first. */
.fro-row.fro-good{background:var(--good-wash); border-left-color:var(--good)}
.fro-row.fro-bad{background:var(--bad-wash); border-left-color:var(--bad)}
.fro-club{font-size:13px; font-weight:600; flex:1}
.fro-val{font-family:var(--mono); font-size:13px; font-weight:600}
.fro-row.fro-good .fro-val{color:var(--good-ink)}
.fro-row.fro-bad .fro-val{color:var(--bad-ink)}
.fro-mine{
  display:inline-flex; align-items:center; gap:4px;
  font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.04em; color:var(--accent-ink); white-space:nowrap;
  padding:2px 7px 2px 5px; border-radius:9999px; background:var(--accent-wash);
}
/* One dot per owned player (max 3, the club cap) - text alone read
   identically whether it said "1 owned" or "3 owned" from a normal
   reading distance; the dot count makes the difference visible instantly. */
.fro-dots{display:inline-flex; gap:2px}
.fro-dot{width:5px; height:5px; border-radius:50%; background:var(--accent-ink)}
@media (max-width:520px){.frocols{grid-template-columns:1fr}}

/* --- wildcard / bench boost rebuild -------------------------------------
   Both now shirt-and-pitch views rather than a table of price deltas -
   "would I actually want this squad/bench" reads off shirts faster than a
   table of price deltas. wcstats is the numeric case above the pitches:
   is the resulting XI actually stronger on points, fixtures, underlying
   attacking numbers and form, not just "N swaps happened". */
.swapcard summary{cursor:pointer}
.wcstats{
  display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));
  gap:10px 16px; padding-bottom:14px; margin-bottom:2px;
  border-bottom:1px solid var(--outline-variant);
}
.wcstat{display:flex; align-items:baseline; gap:6px; flex-wrap:wrap}
.wcstat-k{
  font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; color:var(--on-surface-variant); flex-basis:100%;
}
.wcstat-b{font-family:var(--mono); font-size:13px; color:var(--on-surface-variant)}
.wcstat-arrow{color:var(--p40); font-size:12px}
.wcstat-a{font-family:var(--mono); font-size:15px; font-weight:700}
.wcstat-d{font-family:var(--mono); font-size:11px; margin-left:2px}
.wcstat-d.wc-up{color:var(--good-ink)}
.wcstat-d.wc-down{color:var(--bad-ink)}
.wcstat-d.wc-flat{color:var(--on-surface-variant)}

/* --- highest predicted points XI ----------------------------------------
   Positions down, not one ranked eleven: the question this answers is
   "where is my team behind", which only reads position by position. */
.bxi-head{
  display:flex; flex-wrap:wrap; align-items:baseline; gap:8px 18px;
  padding-bottom:12px; margin-bottom:12px;
  border-bottom:1px solid var(--outline-variant);
}
.bxi-big{display:flex; align-items:baseline; gap:7px}
.bxi-big .num{font-size:34px; font-weight:700; line-height:1}
.bxi-big small{font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:var(--on-surface-variant); max-width:6em}
.bxi-own{margin:0; display:inline-flex; align-items:center; gap:5px;
  font-size:13px; color:var(--on-surface-variant)}
.bxi-own .ic{width:15px; height:15px; color:var(--good-ink)}
.bxi-own b{color:var(--on-surface)}
.bxi-read{margin:0; flex:1 1 260px; font-size:12px;
  color:var(--on-surface-variant); line-height:1.45}
.bxi-grid{display:grid; gap:14px 22px;
  grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.bxi-group h4{
  margin:0 0 5px; font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.07em; color:var(--on-surface-variant);
}
.bxi-group ul{list-style:none; margin:0; padding:0}
.bxi-row{
  display:grid; align-items:center; gap:0 7px; padding:3px 0 3px 2px;
  grid-template-columns:15px minmax(0,1fr) auto 46px 30px;
}
.bxi-mark .ic{width:13px; height:13px; color:var(--good-ink)}
.bxi-name{font-size:13px; font-weight:600; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap}
.bxi-club{font-size:10px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--p60)}
.bxi-bar{display:block; height:5px; border-radius:3px; background:var(--p10)}
.bxi-bar i{display:block; height:100%; border-radius:3px; background:var(--p30)}
.bxi-ep{font-size:12px; text-align:right; color:var(--on-surface-variant)}
/* Owned men are the reference, so they carry the colour; the ones you are
   missing stay plain and let the tick count do the talking. */
.bxi-row.is-mine .bxi-bar i{background:var(--accent)}
.bxi-row.is-mine .bxi-name,.bxi-row.is-mine .bxi-ep{color:var(--on-surface)}
.bxi-row.is-mine .bxi-ep{font-weight:700}

/* --- the knee-jerk ------------------------------------------------------
   The one card arguing with the reader, so the one card on ink. */
.kjcard{
  background:var(--ink); color:var(--white); border:0;
  border-left:5px solid var(--attention); overflow:hidden;
}
.kjcard.kj-good{border-left-color:var(--accent)}
.kjcard.kj-bad{border-left-color:var(--bad)}
.kj-tag{
  padding:9px 18px 0; font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.14em; color:var(--accent);
}
.kj-body{padding:2px 18px 16px}
.kj-lead{margin:2px 0 0; font-size:15px; color:rgb(255 255 255 / 76%)}
.kj-lead b{color:var(--white)}
.kj-score{margin:2px 0 0; display:flex; align-items:baseline; gap:9px}
.kj-score .num{font-size:52px; font-weight:700; line-height:1; color:var(--accent)}
.kj-score small{font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:rgb(255 255 255 / 62%)}
.kj-facts{
  display:flex; flex-wrap:wrap; gap:6px 26px; margin:14px 0 0;
  padding-top:12px; border-top:1px solid rgb(255 255 255 / 16%);
}
.kj-facts dt{font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:rgb(255 255 255 / 55%)}
.kj-facts dd{margin:1px 0 0; font-size:17px; font-weight:700}
.kj-verdict{margin:12px 0 0; font-size:13px; line-height:1.5;
  color:rgb(255 255 255 / 80%)}
.kj-fx{
  display:inline-block; margin-left:4px; padding:1px 7px; border-radius:9999px;
  font-size:11px; font-weight:700; background:rgb(255 255 255 / 12%);
  color:var(--white);
}

/* --- buy / sell / keep / avoid ------------------------------------------ */
.vb-grid{display:grid; gap:12px;
  grid-template-columns:repeat(auto-fit,minmax(216px,1fr))}
.vb-col{padding:11px 12px 10px; border-radius:var(--radius-m);
  background:var(--surface-variant); border-top:3px solid var(--p30)}
.vb-col h4{margin:0; font-size:13px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em}
.vb-rule{margin:2px 0 8px; font-size:11px; line-height:1.35;
  color:var(--on-surface-variant)}
.vb-col ul{list-style:none; margin:0; padding:0; display:grid; gap:7px}
.vb-top{display:flex; align-items:baseline; justify-content:space-between; gap:8px}
.vb-top b{font-size:13px}
.vb-ep{font-size:13px; font-weight:700}
.vb-sub{display:block; font-size:11px; line-height:1.35;
  color:var(--on-surface-variant)}
.vb-none{font-size:12px; color:var(--p60)}
.vb-good{border-top-color:var(--good); background:var(--good-wash)}
.vb-good .vb-ep{color:var(--good-ink)}
.vb-bad{border-top-color:var(--bad); background:var(--bad-wash)}
.vb-bad .vb-ep{color:var(--bad-ink)}
.vb-accent{border-top-color:var(--ink)}
.vb-warn{border-top-color:var(--attention); background:var(--attention-wash)}
.vb-warn .vb-ep{color:var(--attention-ink)}

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
/* Twenty clubs, eight shown at a time - the table itself never scrolls
   internally (rows are hidden/shown, not overflowed), so the card's
   height is only ever one page tall. */
.fxnav{
  display:flex; align-items:center; justify-content:center; gap:12px;
  padding:0 16px 10px;
}
.fxnav-btn{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface); width:28px; height:28px; border-radius:50%;
  font-size:16px; line-height:1; cursor:pointer; display:grid; place-items:center;
}
.fxnav-btn:disabled{opacity:.35; cursor:default}
.fxnav-btn:not(:disabled):hover{background:var(--surface-variant)}
.fxnav-btn:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.fxnav-pos{
  font-size:11px; font-weight:600; color:var(--on-surface-variant);
  font-variant-numeric:tabular-nums; min-width:5em; text-align:center;
}
/* Top-right of the card head, level with the title - not its own row
   above the table - the same margin-left:auto used to push .statsel to
   the far side of its own header row. */
.fxcontrols{
  display:flex; align-items:center; gap:14px; flex-wrap:wrap;
  margin-left:auto; align-self:center;
}
/* A stepper, not a <select> - two round arrow buttons either side of the
   number, the same shape as the club-paging arrows below (.fxnav-btn) so
   the card doesn't introduce a second way of doing the same kind of thing. */
.fxgames{display:flex; align-items:center; gap:8px}
.fxgames-label{font-size:13px; font-weight:600}
.fxgames-n{
  min-width:1.4em; text-align:center; font-weight:700;
  font-variant-numeric:tabular-nums;
}
.fxtable td.fxc{
  text-align:center; padding:6px 8px; border:2px solid var(--surface);
  border-radius:var(--radius-xs); min-width:58px; line-height:1.2;
  transition:opacity .15s, filter .15s;
}
.fxc-blank{background:var(--surface-variant); color:var(--on-surface-variant)}
/* Target fixtures: everything that doesn't clear TARGET_RATING fades out,
   so the genuinely good match-ups are the only thing that still pops. A
   fade rather than display:none - removing cells would shift every later
   column in that row out of alignment with the header above it. */
.fxtable.target-on .fxc:not(.fxc-target):not(.fxc-blank){
  opacity:.18; filter:grayscale(.5);
}
.fxc-opp{display:block; font-size:11px; font-weight:700}
.fxc-score{display:block; font-size:13px; font-weight:700;
  font-variant-numeric:tabular-nums}
.fx-mkt{
  display:inline-block; width:4px; height:4px; border-radius:50%;
  background:var(--market); margin-left:4px; vertical-align:middle; opacity:.9;
}
.fxclub{white-space:nowrap}
.fxavg{
  display:inline-block; padding:4px 9px; border-radius:9999px;
  font-weight:700; font-variant-numeric:tabular-nums;
}
.fxtable thead th{white-space:nowrap}
/* No scroll container on this table (see fixture_ticker) - so on a narrow
   card, the later gameweek columns have to actually disappear rather than
   sit clipped and invisible past the card's own edge the way removing
   .scroll here would otherwise leave them. Nearest weeks matter most, so
   those are the ones kept as the width shrinks. */
/* Indices bumped by one for the Owned column inserted after Club - same
   number of gameweek columns kept visible at each breakpoint as before. */
@media (max-width:640px){.fxtable th:nth-child(n+8),.fxtable td:nth-child(n+8){display:none}}
@media (max-width:460px){.fxtable th:nth-child(n+7),.fxtable td:nth-child(n+7){display:none}}
/* The Games selector: GW columns start at nth-child(4) (after Club, Owned,
   Rating), so showing only the first N hides from nth-child(4+N) on -
   ticker.js sets data-games to match the <select>. 8 needs no rule, every
   column FIXTURE_GAMES_MAX renders is already shown. Composes fine with
   the responsive rules above - whichever applies hides that column. */
.fxtable[data-games="1"] th:nth-child(n+5),.fxtable[data-games="1"] td:nth-child(n+5){display:none}
.fxtable[data-games="2"] th:nth-child(n+6),.fxtable[data-games="2"] td:nth-child(n+6){display:none}
.fxtable[data-games="3"] th:nth-child(n+7),.fxtable[data-games="3"] td:nth-child(n+7){display:none}
.fxtable[data-games="4"] th:nth-child(n+8),.fxtable[data-games="4"] td:nth-child(n+8){display:none}
.fxtable[data-games="5"] th:nth-child(n+9),.fxtable[data-games="5"] td:nth-child(n+9){display:none}
.fxtable[data-games="6"] th:nth-child(n+10),.fxtable[data-games="6"] td:nth-child(n+10){display:none}
.fxtable[data-games="7"] th:nth-child(n+11),.fxtable[data-games="7"] td:nth-child(n+11){display:none}
/* The page's one "top reward" look, for the rare figure that earns its own
   treatment rather than blending into the top step of an ordinary scale.
   A fixture rated above 9 is the current holder; reach for this class
   again elsewhere only when a stat is genuinely that rare, not as
   decoration for an everyday good number. Used to be a three-stop diagonal
   gradient (green, through silver, to blue) that read as a broken image
   on the live page rather than as a reward - flat --premium and a star
   glyph say "special" without looking like a rendering glitch. */
.fx-premium{background:var(--premium)}
.fx-premium .fxc-opp,.fx-premium .fxc-score,.rpill.fx-premium,.fxavg.fx-premium{
  color:#fff;
}
.fx-star{font-style:normal; margin-right:2px; font-size:.85em; vertical-align:1px}
.fxown{
  display:inline-flex; align-items:center; justify-content:center;
  min-width:16px; height:16px; padding:0 4px;
  border-radius:9999px; background:var(--accent-wash); color:var(--accent-ink);
  font-size:10px; font-weight:700; vertical-align:middle;
}
/* Its own Owned column now, not a badge tucked into the club name - the
   accent pill makes sense for "you have exposure here" but would read as a
   false highlight repeated down a column of mostly zeroes, so a club with
   none gets a plain muted number instead. */
.fxown-0{background:none; color:var(--on-surface-variant); font-weight:500}

/* --- priced round --- */
.mlist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px}
.mcard{background:var(--surface-variant); border-radius:var(--radius-m); padding:13px}
.mteams{display:flex; align-items:baseline; gap:7px; margin-bottom:9px}
.mt{font-weight:700; font-size:15px}
.mt.mine{color:var(--accent)}
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
.pr-tag{
  margin:0 0 8px; font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; color:var(--attention-ink);
}
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
  background:var(--surface-variant); border:1px solid var(--outline-variant);
  color:var(--p60)}
.pr-blank img{width:30px; height:30px; object-fit:contain; display:block}
.pr-kit{position:absolute; right:-5px; bottom:-4px; width:18px; height:18px;
  border-radius:50%; background:var(--surface); padding:1px}
.pr-out .pr-photo{filter:grayscale(.75) opacity(.7)}
.pr-name{font-size:12px; font-weight:600; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap}
.pr-arrow{flex:none; width:28px; color:var(--on-surface-variant)}
.pr-arrow svg{width:28px; height:12px; display:block}
.pr-gain{flex:none; font-size:12px; font-weight:700; color:var(--good-ink);
  font-variant-numeric:tabular-nums}
.pr-foot{margin:12px 0 0; font-size:11px}
.pr-yes{color:var(--good-ink); font-weight:700}
.pr-no{color:var(--on-surface-variant)}

/* --- league template pitch + differentials --- */
.tplpitch .pl{width:86px}
.tplpitch .pl .sc .p{font-size:11px}
.pl.tpl-mine{outline:2px solid var(--mine); outline-offset:1px}
.dflist{list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px}
.df-card{display:flex; gap:14px; align-items:center;
  background:var(--surface-variant); border-radius:var(--radius-m); padding:12px}
.df-frame{position:relative; flex:none}
.df-photo{width:84px; height:106px; border-radius:var(--radius-s);
  object-fit:cover; background:var(--surface); flex:none}
.df-blank{display:grid; place-items:center; font-size:34px; font-weight:700;
  background:var(--p10); border:1px solid var(--p20);
  color:var(--p60)}
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

/* --- scoring against you ------------------------------------------------
   Deliberately not the same card as Your differentials sitting above it.
   That one is four facts about one player and is drawn as a portrait; this
   one is a ranking, so it is drawn as a ranking - rows down the page with a
   bar you can compare along, red because the whole point is that these went
   onto somebody else's score. */
.rvtabs{display:flex; gap:6px; margin-bottom:12px}
.rvtab{
  appearance:none; border:1px solid var(--outline); background:var(--surface);
  color:var(--on-surface-variant); font:inherit; font-weight:600; font-size:12px;
  padding:5px 12px; border-radius:9999px; cursor:pointer;
}
.rvtab[aria-selected="true"]{background:var(--ink); color:#fff; border-color:var(--ink)}
.rvtab:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.rvlist{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:8px}
.rv-row{
  display:grid; align-items:center; gap:2px 12px;
  grid-template-columns:44px minmax(110px,175px) 34px minmax(90px,1fr);
  grid-template-areas:"face who pts track" ". note note note";
}
.rv-photo{grid-area:face; width:44px; height:56px; border-radius:var(--radius-xs);
  object-fit:cover; background:var(--surface-variant); flex:none}
.rv-blank{display:grid; place-items:center; font-size:19px; font-weight:700;
  background:var(--surface-variant); border:1px solid var(--outline-variant);
  color:var(--p60)}
.rv-who{grid-area:who; min-width:0; display:flex; flex-direction:column}
.rv-who b{font-size:14px; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap}
.rv-who span{font-size:10px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--p60)}
.rv-pts{grid-area:pts; font-size:19px; font-weight:700; text-align:right;
  color:var(--bad-ink)}
.rv-track{grid-area:track; height:9px; border-radius:5px;
  background:var(--outline-variant); overflow:hidden}
.rv-track i{display:block; height:100%; border-radius:5px; background:var(--rival)}
.rv-note{grid-area:note; font-size:11px; color:var(--on-surface-variant)}
@media (max-width:620px){
  .rv-row{grid-template-columns:44px minmax(0,1fr) 34px;
    grid-template-areas:"face who pts" "face track track" ". note note"}
}

/* --- league leaders --- */
.slwrap{
  list-style:none; margin:0; padding:0; display:grid;
  /* Six leaders divide as 3x2. Left to auto-fit they wrapped 5 + 1, which put
     a lone card beside a long empty gap. */
  grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px;
}
.slcard{
  background:var(--surface-variant); border-radius:var(--radius-m);
  padding:12px 12px 10px; border-top:3px solid var(--accent,var(--p30));
}
/* Ink, not the card's own tone. Six cards were each colouring their
   heading with an arbitrary hue, and two of those hues - a muted purple
   that is literally the secondary-text token, and a dark magenta - came
   out reading as disabled text. The tone survives on the rule and the
   icon, which is enough to tell six cards apart; legibility should not
   depend on which measure a card happens to be about. */
.slcard h4{
  margin:0; font-size:12px; text-transform:uppercase; letter-spacing:.04em;
  display:flex; align-items:center; gap:7px; color:var(--on-surface);
}
.slicon{color:var(--accent)}
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
/* Your own players are the one thing worth spotting across all six cards,
   so they are marked the same green everywhere rather than in whatever
   hue the card was assigned - which also retires white-on-#01fc7a. */
.sllist li.mine .slrank{background:var(--good); color:var(--ink)}
.sllist li.mine .slname{font-weight:700; color:var(--on-surface)}
.sllist li.mine .slval{color:var(--good-ink)}
.slname{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.slteam{font-size:10px; color:var(--on-surface-variant)}
.slval{margin-left:auto; font-weight:700; font-variant-numeric:tabular-nums}
/* A paired stat (big chances, chances) reads as one bold headline number
   with the second figure along for context, not two numbers of equal
   weight fighting for the eye. */
.slval .pairsub{font-weight:400; color:var(--on-surface-variant); font-size:12px}
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
  background:linear-gradient(90deg,var(--accent),#01fc7a);
}
.tf-swap{display:flex; align-items:flex-start; gap:8px}
.tf-face{flex:1 1 0; text-align:center; min-width:0}
.tf-frame{position:relative; width:72px; margin:0 auto}
.tf-photo{
  width:72px; height:92px; border-radius:var(--radius-s); object-fit:cover;
  background:var(--surface); display:block;
}
/* A player with no portrait used to draw as a white box on a white card
   with a letter floating in it - indistinguishable from an image that had
   failed to load, and four of them sat in one row of suggested transfers.
   The club kit is an asset we already have for that player, so a missing
   face falls back to the shirt on the same warm ground the pitch cards use
   for a crest, and only a player with neither gets the letter. */
.tf-blank{
  display:grid; place-items:center; font-size:30px; font-weight:700;
  background:var(--surface-variant); border:1px solid var(--outline-variant);
  color:var(--p60);
}
.tf-blank img{width:48px; height:48px; object-fit:contain; display:block}
.tf-kit{
  position:absolute; right:-8px; bottom:-6px; width:26px; height:26px;
  border-radius:50%; background:var(--surface); padding:2px;
  box-shadow:0 1px 4px rgb(0 0 0 / 25%);
}
.tf-out .tf-photo{filter:grayscale(.75) opacity(.72)}
/* Set-piece duties on a suggested target - who takes pens, free kicks or
   corners is worth knowing right next to the signing, not only on the
   set-piece card three sections away. */
.duty-badges{display:inline-flex; gap:2px; vertical-align:middle}
.duty-badges .spicon{width:11px; height:11px; color:var(--accent-ink)}
.tf-frame .duty-badges,.pr-frame .duty-badges,.df-frame .duty-badges{
  position:absolute; top:-4px; left:-4px; background:var(--surface);
  border-radius:var(--radius-xs); padding:2px; box-shadow:0 1px 3px rgb(0 0 0 / 20%);
}
.pr-frame .duty-badges .spicon{width:8px; height:8px}
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
.tf-ep-in .tf-track i{background:var(--accent)}
.tf-gain{
  font-size:19px; font-weight:700; color:var(--good-ink); text-align:center;
  line-height:1.05; font-variant-numeric:tabular-nums;
}
.tf-gain small{display:block; font-size:10px; font-weight:600;
  text-transform:uppercase; letter-spacing:.04em; color:var(--on-surface-variant)}
.tf-foot{margin:12px 0 0; font-size:11px; color:var(--on-surface-variant);
  text-align:center}
.tf-elite{font-weight:600; color:var(--good-ink)}

/* --- expected points, stacked --- */
.epbar{
  display:flex; height:16px; border-radius:9999px; overflow:hidden;
  background:var(--outline-variant);
}
.epbar.wide{height:20px; margin-top:6px}
.epbar .seg{display:block; height:100%; box-shadow:inset -2px 0 0 var(--surface)}
.epbar .seg:last-child{box-shadow:none}
.eptot{text-align:right; font-weight:700; font-size:15px}
.eplegend{
  display:flex; flex-wrap:wrap; gap:14px; margin:14px 0 0; padding:0 14px;
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

/* --- dumbbell + threshold bars ---
   The track is the thing worth looking at, so it gets the room: the name
   column is tighter, the figures are mono and so need less width than the
   proportional text they replaced, and everything left over goes to the bar.
   Rows are taller too - these were drawn at 16px in a card that had hundreds
   of pixels going spare. */
.gapcard{padding-bottom:14px}
.gaplist,.dclist{list-style:none; margin:0; padding:0 14px; display:flex;
  flex-direction:column; gap:11px}
.gap,.dcr{display:grid; align-items:center; gap:9px}
.gap{grid-template-columns:82px 1fr 74px}
.dcr{grid-template-columns:78px 1fr 58px auto}
.gapname,.dcname{font-size:13px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.gaptrack,.dctrack{position:relative; height:22px}
.gaptrack::before,.dctrack::before{
  content:""; position:absolute; left:0; right:0; top:10px; height:2px;
  background:var(--outline-variant);
}
.gapline{position:absolute; top:9px; height:4px; border-radius:2px}
.gapdot{
  position:absolute; top:5.5px; width:11px; height:11px; border-radius:50%;
  box-shadow:0 0 0 2px var(--surface);
}
.gapdot.d-a{background:var(--on-surface)}
.gapdot.d-x{background:var(--surface); border:2px solid var(--on-surface-variant)}
.gapnum,.dcnum{
  font-family:var(--mono); font-variant-numeric:tabular-nums;
  font-size:12px; text-align:right; color:var(--on-surface-variant);
  white-space:nowrap; letter-spacing:-0.02em;
}
.dchits{
  font-family:var(--mono); font-size:11px; color:var(--on-surface-variant);
  text-align:right; white-space:nowrap;
}
.dcr .good-pill,.dcr .bad-pill,.dcr .warn-pill{white-space:nowrap; justify-self:end}
.good-pill,.bad-pill,.warn-pill{white-space:nowrap}
.dcfill{position:absolute; top:8px; height:7px; border-radius:9999px}
.dcmark{
  position:absolute; top:3px; width:2px; height:17px;
  background:var(--on-surface); opacity:.5;
}
.spark{vertical-align:middle}

/* --- expanded player view --- */
.rowlink{
  appearance:none; background:none; border:0; padding:0; font:inherit;
  color:inherit; cursor:pointer; text-align:left; text-decoration:underline;
  text-decoration-color:var(--outline); text-underline-offset:3px;
}
.rowlink:hover{text-decoration-color:var(--accent)}
.rowlink:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.pl[role="button"]{cursor:pointer}
.pl[role="button"]:hover{transform:translateY(-2px)}
.pl[role="button"]:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
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
.pv-close:focus-visible{outline:3px solid var(--accent); outline-offset:2px}
.pv-body{padding:20px 20px 24px; overflow-y:auto; max-height:88vh}
.pv-head{display:flex; align-items:flex-start; gap:12px; padding-right:38px}
.pv-head h2{font-size:22px}
.pv-sub{margin:2px 0 0; font-size:13px; color:var(--on-surface-variant)}
.pv-pricechange{font-family:var(--mono); font-size:12px}
.pv-pricechange.up{color:var(--good-ink)}
.pv-pricechange.down{color:var(--bad)}
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

/* --- findings ---
   `align-items:start` is the whole fix for the dead space these cards used
   to carry. A grid stretches its items to the tallest in the row by default,
   so one long set-piece list gave every card beside it several hundred pixels
   of nothing. Ragged bottoms are the correct trade: the cards are independent
   readings, not a table, and nothing about them wants a shared baseline.

   This was multi-column for a while, which balanced the nine cards into
   columns of equal height and so put the reading order down column one and
   back up to the top of column two. They are nine independent readings of
   one squad; they should read left to right, in the order they were
   ranked. */
.finds{
  display:grid; gap:12px; align-items:start;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
}
.find{
  background:var(--surface); border-radius:var(--radius-m);
  box-shadow:var(--shadow); overflow:hidden; margin:0;
}
.find h3{
  font-size:12px; text-transform:uppercase; letter-spacing:0.06em;
  font-stretch:112%; padding:11px 14px 9px;
  border-top:3px solid var(--tone,var(--p60));
}
.find .note{padding:0 14px 10px; font-size:13px; color:var(--on-surface-variant); margin-top:-4px}
.find ul{margin:0; padding:0 14px 14px; font-size:14px; list-style:none}

/* A findings row, borrowing the set-piece card's grammar outright: subject
   left in semibold, evidence pushed right and quieter, no rules between
   rows. The tag pill that used to hold the subject - grey chip, coloured
   left tip - is gone. Repeated down a card it turned a short list into
   something that looked like far more information than it was, which is
   the opposite of what a findings card is for. */
.filist{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:7px}
.fi{display:flex; align-items:baseline; gap:12px; font-size:13px}
.fi-sub{font-weight:600; flex:none}
.fi-det{
  margin-left:auto; text-align:right; color:var(--on-surface-variant);
  font-size:12px; line-height:1.4;
}
/* A row with no subject is a plain sentence and should read as one. */
.fi-det:only-child{margin-left:0; text-align:left}
.fnum{font-family:var(--mono); font-weight:600; letter-spacing:-0.02em}

/* --- attacking returns ---------------------------------------------------
   Goals and assists as the one number FPL managers already mean by
   "returns", not the two parts it's made of. A defender's row is marked
   and picked out, since the same total is the rarer, more valuable one. */
.arrlist{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:7px}
.arr{display:flex; align-items:center; gap:9px; font-size:13px}
.arr-name{font-weight:600; display:flex; align-items:center; gap:6px}
.arr-club{font-size:10px; text-transform:uppercase; letter-spacing:.04em;
  color:var(--p60)}
.arr-detail{
  margin-left:auto; color:var(--on-surface-variant); font-size:12px;
  font-family:var(--mono);
}
.arr-total{font-size:16px; font-weight:700; min-width:1.4em; text-align:right}
.arr-def{
  font-size:9px; font-weight:800; letter-spacing:.05em; padding:1px 5px;
  border-radius:9999px; background:var(--accent-wash); color:var(--accent-ink);
}
.arr-isdef .arr-total{color:var(--accent-ink)}
/* Rows with no .arr-detail column (e.g. big chances/chances) have nothing
   else to carry the flex auto-margin that pushes the total flush right. */
.arr-nodetail .arr-total{margin-left:auto}
/* A paired stat (big chances, chances) reads as one bold headline number
   with the second figure along for context, not two of equal weight. */
.arr-total .pairsub{font-weight:400; font-size:13px; color:var(--on-surface-variant)}

/* --- match logs --- */
details{border-bottom:1px solid var(--outline-variant)}
details summary{
  padding:10px 14px; cursor:pointer; font-weight:600; font-size:14px;
  display:flex; align-items:center; gap:10px;
}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"\\25B8"; color:var(--on-surface-variant); transition:transform .15s}
details[open] summary::before{transform:rotate(90deg)}
details summary:focus-visible{outline:3px solid var(--accent); outline-offset:-3px}
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
CAPTAINCY_JS = (Path(__file__).with_name("captaincy.js")).read_text(encoding="utf-8")
LEAGUECHART_JS = (Path(__file__).with_name("leaguechart.js")).read_text(encoding="utf-8")
TICKER_JS = (Path(__file__).with_name("ticker.js")).read_text(encoding="utf-8")

JS = """
(function(){
  // The "i" beside a title reveals that card's explanation. Delegated once
  // rather than wired per-card, since the same markup shape (title, button,
  // then the text it reveals as the next sibling in a .card-head or .find)
  // repeats everywhere on the page.
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.infobtn');
    if (!btn) return;
    var scope = btn.closest('.card-head, .find');
    if (!scope) return;
    var show = btn.getAttribute('aria-expanded') !== 'true';
    scope.querySelectorAll(':scope > .sub, :scope > .note').forEach(function(t){
      t.hidden = !show;
    });
    btn.setAttribute('aria-expanded', String(show));
    // Some of these buttons live inside a <summary> - without this, opening
    // the explanation also springs the whole collapsible card open.
    if (btn.closest('summary')) { ev.preventDefault(); ev.stopPropagation(); }
  });

  // Predicted line-ups: full squad, XI or bench answer different questions
  // about the same fifteen, so one donut cycles between them rather than
  // showing three at once.
  document.querySelectorAll('.lcnav').forEach(function(nav){
    var card = nav.closest('.lccard');
    var panels = Array.from(card.querySelectorAll('.lcpanel'));
    var label = nav.querySelector('.lc-navlabel');
    var idx = panels.findIndex(function(p){ return !p.hidden; });
    if (idx < 0) idx = 0;
    function show(i){
      idx = (i + panels.length) % panels.length;
      panels.forEach(function(p, j){ p.hidden = j !== idx; });
      label.textContent = panels[idx].dataset.lclabel;
    }
    nav.querySelector('.lc-prev').addEventListener('click', function(){ show(idx - 1); });
    nav.querySelector('.lc-next').addEventListener('click', function(){ show(idx + 1); });
  });

  // Scoring against you: this week vs the last few weeks summed.
  document.querySelectorAll('.rvtabs').forEach(function(tabs){
    var card = tabs.closest('.card');
    var buttons = tabs.querySelectorAll('.rvtab');
    var panels = card.querySelectorAll('.rvpanel');
    buttons.forEach(function(b){
      b.addEventListener('click', function(){
        buttons.forEach(function(o){ o.setAttribute('aria-selected', String(o===b)); });
        panels.forEach(function(p){ p.hidden = p.dataset.rv !== b.dataset.rv; });
      });
    });
  });

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
      buildRail();
    });
  });

  // --- the chapter rail ---------------------------------------------------
  // Built from whichever chapters the open tab has rather than from a fixed
  // list, so it can never offer a section that is not on screen. A tab with
  // one chapter gets no rail at all - a nav of length one is furniture.
  var railWrap=document.querySelector('.railwrap');
  var rail=document.querySelector('.rail');
  var railTargets=[];

  function buildRail(){
    if(!rail) return;
    var panel=document.querySelector('.panel:not([hidden])');
    var chapters=panel ? panel.querySelectorAll('.chapter') : [];
    rail.textContent='';
    railTargets=[];
    if(chapters.length < 2){ railWrap.hidden=true; return; }
    railWrap.hidden=false;
    chapters.forEach(function(ch,i){
      var h=ch.querySelector('h2');
      if(!h) return;
      if(!ch.id) ch.id='ch-'+(panel.id||'p')+'-'+i;
      var b=document.createElement('button');
      b.type='button';
      b.className='railbtn';
      b.textContent=h.textContent.trim();
      b.addEventListener('click',function(){
        // An explicit position rather than scrollIntoView, and no smooth:
        // the sticky bar's height is the offset, and it is measured now
        // rather than assumed, because the bar grows a second row the
        // moment this rail exists.
        var bar=document.querySelector('.topbar');
        var off=(bar ? bar.getBoundingClientRect().height : 0) + 8;
        window.scrollTo(0, ch.getBoundingClientRect().top + window.scrollY - off);
        markRail();
      });
      rail.appendChild(b);
      railTargets.push({el:ch, btn:b});
    });
    markRail();
  }

  // Which chapter you are actually in: the last one whose top has passed
  // under the bar. Cheaper and steadier than an observer per section, and
  // it agrees with what is under the heading rather than what is centred.
  function markRail(){
    if(!railTargets.length) return;
    var cut=110, current=railTargets[0];
    railTargets.forEach(function(t){
      if(t.el.getBoundingClientRect().top <= cut) current=t;
    });
    railTargets.forEach(function(t){
      t.btn.setAttribute('aria-current', String(t===current));
    });
  }

  // Called straight from the scroll event rather than deferred into a frame.
  // The rAF-throttled version had a real failure mode: it raised a "already
  // queued" flag before asking for the frame, so anywhere frames are paused -
  // a background tab, a hidden view - the flag was set, the callback never
  // ran to clear it, and every later scroll was dropped for the life of the
  // page. markRail is four getBoundingClientRect calls against a list that
  // is at most four long; it does not need deferring.
  window.addEventListener('scroll', markRail, {passive:true});
  buildRail();

  // Starting XI: overview vs pick-team pitch. Same swap as the tabs above,
  // scoped to whichever card the clicked button lives in, since the page
  // only has one of these but a second squad card could add one later.
  // "Gameweek" is not a third pitch - it is the overview pitch with the
  // first figure swapped. Rendering another eleven shirt cards to change
  // one number per card would have put the same images on the page a third
  // time, and this page is already better than a megabyte.
  document.querySelectorAll('.pkview').forEach(function(group){
    var btns = group.querySelectorAll('.pkbtn');
    var card = group.closest('.card');
    function points(view){
      var key = view === 'gw' ? 'ptsNow' : 'ptsSeason';
      card.querySelectorAll('.pkpanel[data-view="ov"] .pl').forEach(function(pl){
        var cell = pl.querySelector('.sc .p');
        if (cell && pl.dataset[key] !== undefined) { cell.textContent = pl.dataset[key]; }
      });
    }
    btns.forEach(function(b){
      b.addEventListener('click', function(){
        var view = b.dataset.view;
        btns.forEach(function(o){ o.setAttribute('aria-selected', String(o===b)); });
        // Overview and Gameweek share one panel, so the panel to show is the
        // view itself for 'pk' and the overview panel for either other.
        var panel = view === 'pk' ? 'pk' : 'ov';
        card.querySelectorAll('.pkpanel').forEach(function(p){
          p.hidden = p.dataset.view !== panel;
        });
        card.querySelectorAll('[data-pkview]').forEach(function(p){
          p.hidden = p.dataset.pkview !== view;
        });
        // The figure selector only means anything on the two views that
        // share the overview pitch; the predicted-points toggle only means
        // anything on the one that does not.
        var sel = group.querySelector('.statsel');
        if (sel) { sel.hidden = view === 'pk'; }
        var epb = group.querySelector('.epbtn');
        if (epb) { epb.hidden = view !== 'pk'; }
        // The hero's one-liner belongs to the view, not to the card: on
        // Pick team it should be looking at the week ahead rather than
        // reporting the one just gone. It lives above the tabs, outside
        // this card, so it is switched separately.
        // Only two lines exist - looking forward on Pick team, looking back
        // on either of the other two - so they key off the same collapse
        // the panels use rather than off all three view names.
        var heroKey = view === 'pk' ? 'pk' : 'back';
        document.querySelectorAll('.hero [data-pkview]').forEach(function(p){
          p.hidden = p.dataset.pkview !== heroKey;
        });
        points(view);
      });
    });
  });

  // Predicted points: the eleven shrink into a column and the bars extend
  // across the space that opens beside them.
  document.querySelectorAll('.epbtn').forEach(function (btn) {
    var stage = btn.closest('.card').querySelector('.pkstage');
    if (!stage) { btn.hidden = true; return; }
    var side = stage.querySelector('.epside');
    var reduce = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    btn.addEventListener('click', function () {
      var on = btn.getAttribute('aria-pressed') !== 'true';
      btn.setAttribute('aria-pressed', String(on));
      stage.classList.toggle('ep-on', on);
      if (side) { side.setAttribute('aria-hidden', String(!on)); }
      if (!on || reduce || !side) { return; }
      // Run the bars out only once the column has finished opening,
      // otherwise they animate to a width that is still changing.
      window.setTimeout(function () {
        side.querySelectorAll('.epcr .epbar').forEach(function (bar, i) {
          if (!bar.animate) { return; }
          bar.animate(
            [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
            { duration: 340, delay: i * 45, easing: 'cubic-bezier(.2,.7,.3,1)' }
          );
        });
      }, 260);
    });
  });

  // Click a figure to bring it forward on every card at once.
  document.querySelectorAll('.statsel').forEach(function (group) {
    var btns = group.querySelectorAll('.stbtn');
    var wrap = group.closest('.card').querySelector('.ovwrap');
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        btns.forEach(function (o) {
          o.setAttribute('aria-pressed', String(o === b));
        });
        if (!wrap) { return; }
        wrap.classList.remove('emph-p', 'emph-g', 'emph-x');
        wrap.classList.add('emph-' + b.dataset.stat);
      });
    });
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

def gw_points(r, gw):
    """A player's points in one gameweek. Summed rather than found, because
    a double gameweek is two rows in the same history."""
    return sum(h["total_points"] for h in r.history if h.get("round") == gw)


def player_card(r, ctx, badges, shirts, captain_id, vice_id, played=True,
                gw=None):
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
    # Season points beside season xGI, with no sense of how many matches
    # either came from, flattered anyone who had simply played more. Points
    # per game is the fair comparison and costs one more cell; the raw
    # totals stay, since per-game alone hides who has actually been
    # available. The two gameweek figures ride along as data attributes so
    # the selector can swap them in without re-rendering the pitch.
    ppg = f(el.get("points_per_game"))
    now = gw_points(r, gw) if gw else 0
    prev = gw_points(r, gw - 1) if gw and gw > 1 else 0
    return (
        f'<div class="{cls}" title="{e(title)}" data-player="{el["id"]}" '
        f'data-pts-season="{r.points}" data-pts-now="{now}" '
        f'data-pts-prev="{prev}" data-apps="{r.appearances}" '
        f'role="button" tabindex="0" aria-label="{e(title)}">{arm}{pip}'
        f'<div class="crest">{crest}</div>'
        f'<div class="nm">{e(r.name)}</div>'
        f'<div class="sc tnum"><div class="p" title="Points">{r.points}</div>'
        f'<div class="g" title="Points per game across {r.appearances} '
        f'appearances">{ppg:.1f}</div>'
        f'<div class="x" title="Season xGI">{r.xgi:.2f}</div></div></div>'
    )


def pitch(xi, bench, ctx, badges, shirts, captain_id, vice_id, gw=None):
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    # The stat selector itself lives up in the view-tab row, so this only
    # supplies the wrapper its classes are toggled on.
    out = ['<div class="ovwrap emph-p">']
    out.append('<div class="pitch">' + components.PITCH_MARKS)
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            player_card(r, ctx, badges, shirts, captain_id, vice_id,
                        r.minutes > 0, gw=gw)
            for r in rows[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        player_card(r, ctx, badges, shirts, captain_id, vice_id, r.minutes > 0,
                    gw=gw)
        for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div>'
    )
    out.append("</div>")   # .ovwrap
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
                    proj, market, next_gw, eps=None):
    """The pick-team pitch, and the expected-points column it folds out to.

    Both live in one `.pkstage` so the Predicted points toggle can move
    between them as a single layout change rather than swapping one block
    of markup for another - the eleven cards shrink into a column on the
    left and the bars extend across the space that opens on the right,
    which only reads as the same eleven if they are the same elements
    throughout.

    Keeper first, forwards last, top to bottom. That is already the order
    the pitch draws in, so the folded-out column inherits it for free, and
    `ep_column` is handed the ids in exactly that order so every bar sits
    level with its own card."""
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    rows = {1: [], 2: [], 3: [], 4: []}
    for r in xi:
        rows[order.get(r.pos, 4)].append(r)
    # The left column carries a header of its own only so the two columns
    # start at the same height - without it the eleven began level with the
    # side panel's title and every bar sat one card low.
    out = ['<div class="pkstage"><div class="pkboard">'
           '<div class="pkboard-head">Your eleven</div>'
           '<div class="pitch">' + components.PITCH_MARKS]
    pitch_order = []
    for k in (1, 2, 3, 4):
        if not rows[k]:
            continue
        cards = "".join(
            pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj,
                     market, next_gw, r.minutes > 0)
            for r in rows[k]
        )
        pitch_order.extend(r.element["id"] for r in rows[k])
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    cards = "".join(
        pick_card(r, ctx, badges, shirts, captain_id, vice_id, proj, market,
                 next_gw, r.minutes > 0)
        for r in bench
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{cards}</div></div></div>'
    )
    out.append(components.ep_column(eps or [], pitch_order))
    out.append("</div>")
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
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})
    body = []
    for r in reports:
        el = r.element
        flag, news = r.availability
        fx = "".join(
            ticker.rating_pill(row["opp"], row["home"], row["score"])
            for row in ticker._rows_for(r.team, proj, market, next_gw, 3,
                                        baseline_xg.get(r.team), club_mean_cs.get(r.team))
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
    # The delta chip carries the direction, so the arrow glyph that used to
    # sit here is gone: one component says "this moved, this way, by this
    # much" everywhere on the page rather than each card inventing its own.
    tone = "var(--good)" if rising else "var(--bad)"
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
        f'<span class="delta {"delta-up" if rising else "delta-down"}">'
        f'{abs(r["pct"]):.0f}%</span>'
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
        f'<div class="card-head"><h2>Price watch{components.info_btn()}</h2>'
        '<span class="sub" hidden>A change fires at 100%. Prices update once a day, so this '
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
        f'<div class="card-head"><h2>Value scatter{components.info_btn()}</h2>'
        '<span class="sub" hidden>Pick any two measures. Hover or click a dot to see the '
        "player. Your squad and the biggest outliers are always labelled.</span></div>"
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
        '<div class="scroll"><svg class="scatter" viewBox="0 0 1040 520" '
        'role="img" aria-label="Scatter plot of player metrics"></svg></div>'
        '<p class="readout" aria-live="polite">Hover or click any dot to identify the player.</p>'
        '<p class="legend"><span class="key mkt"></span>Every player with 60+ minutes'
        '<span class="key mine"></span>Your squad'
        '<span class="key outlier"></span>Furthest from the norm</p>'
        f'<script type="application/json" class="scatter-data">{json.dumps(data)}</script>'
        "</div></section>"
    )


def donut(pct, label, center, sub, tone="var(--accent)"):
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
        tone = "var(--accent)" if mine else "var(--p60)"
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
        f'<div class="card-head"><h2>Who owns whom{components.info_btn()}</h2>'
        f'<span class="sub" hidden>Share of the {n} managers in this league holding each '
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
    """What proven managers own, against what everyone owns."""
    if not res:
        return ""
    if res.get("insufficient"):
        return (
            '<section class="card">'
            f'<div class="card-head"><h2>What proven managers own{components.info_btn()}</h2></div>'
            '<div class="card-body"><p class="tnote">Elite ownership needs '
            "~10 gameweeks before the top of the table means anything - too "
            "few managers with a proven top-100k season are in the current "
            "top ranks yet.</p></div></section>"
        )
    caveat = (
        f" Read from {res['managers']} proven managers, so each figure "
        f"carries about &plusmn;{res['moe']:.1f} points at 95% confidence."
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
                f'<td class="num" data-v="{r["elite"]}">{r["elite"]:.0f}%</td>'
                f'<td class="num" data-v="{r["overall"]}">{r["overall"]:.0f}%</td>'
                f'<td class="num" data-v="{r["edge"]}" style="color:{edge_tone}">'
                f'<b>{r["edge"]:+.0f}</b></td></tr>'
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

    parts = [table(res["most_owned"], "Most owned by proven managers.")]
    if res["elite_edge"]:
        parts.append(table(
            res["elite_edge"],
            "Owned far more by proven managers than by the crowd - and you do not own them.",
        ))
    if res["against"]:
        parts.append(table(
            res["against"],
            "You own these; proven managers largely do not.",
        ))
    return (
        '<section class="card">'
        f'<div class="card-head"><h2>What proven managers own{components.info_btn()}</h2>'
        f'<span class="sub" hidden>{e(res["label"])}, read from the global FPL league at '
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


def _next_three(r, ctx, proj, market, next_gw, baseline_xg=None, club_mean_cs=None):
    """Three fixture pills for one player, market-rated where the odds
    priced the game and on FPL's own difficulty rating where they did not."""
    baseline_xg = baseline_xg or {}
    club_mean_cs = club_mean_cs or {}
    pills = "".join(
        ticker.rating_pill(row["opp"], row["home"], row["score"])
        for row in ticker._rows_for(r.team, proj, market, next_gw, 3,
                                    baseline_xg.get(r.team), club_mean_cs.get(r.team))
    )
    return pills or "".join(
        fdr_pill(ctx.team_name(o), h, d)
        for o, h, d, _ev in ctx.next_fixtures(r.element["team"], 3)
    )


def lineup_card(reports, ctx, proj, market, next_gw, xi_ids=None):
    """Who is predicted to start, as a donut and then an exception list.

    Fifteen rows saying "predicted to start" is fifteen rows of nothing:
    the information is entirely in the handful who are not, and in how many
    that is. So the count leads with a donut, and only the men who need a
    decision are named - each with the three fixtures that decide whether
    he is worth keeping through it.

    Three different subsets of the same squad answer three different
    questions - a gap in the bench barely matters, the same gap in the
    starting XI is the whole ballgame - so the donut switches between
    full squad, XI and bench rather than only ever answering the first one.

    Unknown is kept separate from no. Fantasy Football Scout not having
    published a side yet is a gap in the feed; being left out of a
    published side is a fact about the player."""
    if not ctx.lineups_known():
        return ""
    xi_ids = xi_ids or set()
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})
    views = [
        ("squad", "Full squad", reports),
        ("xi", "Starting XI", [r for r in reports if r.element["id"] in xi_ids]),
        ("bench", "Bench", [r for r in reports if r.element["id"] not in xi_ids]),
    ]

    def block(rows, cls, label, fixtures=True):
        if not rows:
            return ""
        items = "".join(
            f'<li><span class="lc-name">{e(r.name)}</span>'
            f'<span class="lc-club">{e(r.team)}</span>'
            + (f'<span class="lc-fx">'
               f'{_next_three(r, ctx, proj, market, next_gw, baseline_xg, club_mean_cs)}'
               f"</span>" if fixtures else "")
            + "</li>"
            for r in rows
        )
        return (f'<div class="lc-block {cls}"><h4>{WARN_SVG}{e(label)}</h4>'
                f"<ul>{items}</ul></div>")

    panels = []
    for i, (key, label, rows) in enumerate(views):
        out, unknown = [], []
        for r in rows:
            pred = ctx.is_predicted(r.element)
            if pred is False:
                out.append(r)
            elif pred is None:
                unknown.append(r)
        total = len(rows)
        starting = total - len(out) - len(unknown)
        pct = (starting / total * 100) if total else 0.0
        # A clean sweep gets the same bright accent green as the set-piece
        # card's "1" badge - the colour this page already uses to say "this
        # one's the best of its kind" - rather than the duller ink tone that
        # merely clearing 90% gets.
        tone = ("var(--accent)" if starting == total and total else
                "var(--good-ink)" if pct >= 90 else
                "var(--attention-ink)" if pct >= 60 else "var(--bad-ink)")
        if not total:
            body = '<p class="lc-clear">Nobody in this group.</p>'
        elif not out and not unknown:
            body = ('<p class="lc-clear">Every one of them is named in a '
                    'published side. Nothing to decide here.</p>')
        else:
            # No fixtures for the "out" block: he is not playing this week
            # regardless of who it is against, so a fixture rating there
            # answers a question nobody is asking. "Unknown" still gets
            # them, because there the question is live - a side has not
            # been named yet.
            body = (block(out, "lc-out", "Not predicted to start:", fixtures=False)
                    + block(unknown, "lc-unk", "No side published yet"))
        panels.append(
            f'<div class="lcpanel" data-lcview="{key}" data-lclabel="{e(label)}"'
            f'{" hidden" if i else ""}>'
            '<div class="lc-donut-row">'
            + donut(pct, f"{label} - {starting} of {total} predicted to start",
                    f"{starting}/{total}", "starting", tone)
            + f"</div>{body}</div>"
        )

    nav = (
        '<div class="lcnav" role="group" aria-label="Squad subset">'
        '<button class="arrow lc-prev" type="button" aria-label="Previous group">'
        "&#8249;</button>"
        f'<span class="lc-navlabel">{e(views[0][1])}</span>'
        '<button class="arrow lc-next" type="button" aria-label="Next group">'
        "&#8250;</button></div>"
    )

    return (
        f'<div class="find gapcard lccard"><h3>Predicted line-ups'
        f'{components.info_btn()}</h3>'
        f'<p class="note" hidden>Fantasy Football Scout\'s predicted elevens. '
        f'They are re-tuned after each press conference, so they sharpen '
        f'closer to the deadline.</p>'
        f'{nav}{"".join(panels)}</div>'
    )


def attacking_returns_card(reports):
    """Goals and assists as one number - a "return" in the sense every FPL
    manager already means it, rather than broken back into the two halves
    that made it. A defender's return is marked: the same haul means more
    from the back, and the badge is the reward for scoring rarer points."""
    rows = [
        (r.name, r.team, r.pos, r.goals + r.assists, r.goals, r.assists)
        for r in reports if (r.goals + r.assists) > 0
    ]
    if not rows:
        return ""
    rows.sort(key=lambda x: -x[3])
    items = "".join(
        '<li class="arr{defcls}"><span class="arr-name">{name}{badge}</span>'
        '<span class="arr-club">{club}</span>'
        '<span class="arr-detail">{g:g}G {a:g}A</span>'
        '<span class="arr-total num">{total:g}</span></li>'.format(
            defcls=" arr-isdef" if pos == "DEF" else "",
            name=e(name), club=e(club),
            badge='<span class="arr-def" title="Defender">DEF</span>' if pos == "DEF" else "",
            g=g, a=a, total=total,
        )
        for name, club, pos, total, g, a in rows
    )
    return (
        f'<div class="find gapcard"><h3>Attacking returns{components.info_btn()}</h3>'
        '<p class="note" hidden>Goals and assists combined, one number per player. '
        "A defender's return is marked - the same haul is worth more from the "
        "back than from the front.</p>"
        f'<ul class="arrlist">{items}</ul></div>'
    )


def big_chances_card(reports):
    """Big chances created, with the wider chances-created figure alongside.

    A big chance is a clear opening - a subset of every chance created - so
    the two numbers belong on one row, not two cards that happen to share a
    subject. Ranked on the big-chance figure, since that is the rarer, more
    valuable half."""
    rows = []
    for r in reports:
        ps = r.element.get("_pulse") or {}
        bcc = ps.get("big_chance_created")
        if not bcc:
            continue
        rows.append((r.name, r.team, bcc, ps.get("total_att_assist") or 0))
    if not rows:
        return ""
    rows.sort(key=lambda x: (-x[2], -x[3]))
    items = "".join(
        '<li class="arr arr-nodetail"><span class="arr-name">{name}</span>'
        '<span class="arr-club">{club}</span>'
        '<span class="arr-total num"><b>{bcc:g}</b>'
        '<span class="pairsub">, {tac:g}</span></span></li>'.format(
            name=e(name), club=e(club), bcc=bcc, tac=tac)
        for name, club, bcc, tac in rows
    )
    return (
        f'<div class="find gapcard"><h3>Big chances/chances{components.info_btn()}</h3>'
        '<p class="note" hidden>Shown as big chances, chances - a big chance is a '
        "clear opening, a chance is any pass leading to a shot.</p>"
        f'<ul class="arrlist">{items}</ul></div>'
    )


def fixture_swings_card(reports, ctx, proj, market, next_gw):
    """Clubs with a notably kind or hard run next, with the fixtures that
    make it one rather than just the average that summarises it.

    "Kind"/"hard" still comes from FPL's own 1-5 difficulty rating - a
    different, deliberately independent signal from our own model (see
    ticker.fixture_run_summary's before/after split for why both exist) -
    but the actual fixtures are drawn with our own rating and its pill,
    the same as everywhere else on the page, so a run called "kind" is a
    claim you can see rather than a number you have to take on trust."""
    kind, hard, seen = [], [], set()
    for r in reports:
        if r.team in seen:
            continue
        seen.add(r.team)
        near = ctx.fixture_score(r.element["team"], 3)
        if near is None:
            continue
        if near <= 2.4:
            kind.append((r.team, r.element["team"], near))
        elif near >= 3.6:
            hard.append((r.team, r.element["team"], near))
    if not kind and not hard:
        return ""
    kind.sort(key=lambda x: x[2])
    hard.sort(key=lambda x: -x[2])
    baseline_xg, club_mean_cs = ticker._club_norms(ctx, proj) if proj else ({}, {})

    def block(rows, cls, label):
        if not rows:
            return ""
        items = "".join(
            '<li class="fsw-row"><span class="fsw-club">{club}</span>'
            '<span class="fsw-fdr">FDR {fdr:.1f}</span>'
            '<span class="fsw-fx">{pills}</span></li>'.format(
                club=e(club), fdr=fdr,
                pills="".join(
                    ticker.rating_pill(row["opp"], row["home"], row["score"])
                    for row in ticker._rows_for(club, proj, market, next_gw, 3,
                                                baseline_xg.get(club), club_mean_cs.get(club))
                ),
            )
            for club, _tid, fdr in rows
        )
        return f'<div class="lc-block {cls}"><h4>{e(label)}</h4><ul>{items}</ul></div>'

    body = block(kind, "fsw-kind", "Kind run") + block(hard, "fsw-hard", "Hard run")
    return (
        f'<div class="find gapcard"><h3>Fixture swings{components.info_btn()}</h3>'
        '<p class="note" hidden>FPL\'s own 1-5 difficulty rating, averaged over '
        'the next 3 gameweeks - the fixtures behind a "kind" or "hard" run, '
        "not just the number that summarises it.</p>"
        f'{body}</div>'
    )


def findings_section(finds, reports, ctx, proj=None, market=None, next_gw=None,
                      weekly_price=None, xi_ids=None):
    """Findings, with the ones that have a shape drawn rather than listed.

    Three of these are genuinely numeric comparisons and were being written
    out as sentences: goals against expected goals is a gap, defensive
    contribution is a distance to a threshold, and both read better as marks
    than as prose. The rest stay as lists, because a set-piece order or an
    injury note is text and dressing it up as a chart would be decoration."""
    drawn = {"cold", "hot", "defcon", "setpieces", "sample", "price",
             "lineups", "fixtures"}

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
    lu = lineup_card(reports, ctx, proj, market, next_gw, xi_ids)
    if lu:
        cards.append(lu)
    ar = attacking_returns_card(reports)
    if ar:
        cards.append(ar)
    bc = big_chances_card(reports)
    if bc:
        cards.append(bc)
    fsw = fixture_swings_card(reports, ctx, proj, market, next_gw)
    if fsw:
        cards.append(fsw)
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

    # Old price to new, rather than the size of the change: what you would
    # have paid is the number you actually want. Scoped to the last week,
    # not the season - see _update_price_history for why that needs our own
    # snapshot rather than a field FPL's API already gives us.
    moves = []
    for r in reports:
        delta = (weekly_price or {}).get(r.element["id"], 0.0)
        if abs(delta) >= 0.1:
            moves.append((r.name, r.price - delta, r.price))
    moves.sort(key=lambda m: -(m[2] - m[1]))
    pm = components.price_move_card(moves)
    if pm:
        cards.append(pm)
    tail = []
    for fnd in finds:
        if fnd["key"] in drawn:
            continue
        if fnd["key"] in COLLAPSED:
            tail.append(collapsed_finding(fnd))
            continue
        cards.append(finding_card(fnd))
    return (f'<div class="finds">{"".join(cards)}</div>'
            f'{"".join(tail)}')


# Findings that stay shut. Worth keeping, not worth a column of the page.
COLLAPSED = {"baseline"}


def compact_rank(n):
    """Ranks run to eight figures, and no headline needs all of them."""
    n = abs(int(n))
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return f"{n:,}"


def next_week_line(ctx, xi, eps, next_gw):
    """The forward-looking counterpart to week_verdict, for Pick team.

    The same sentence a manager would say out loud, pointed the other way:
    what the eleven is projected to score, where most of it is expected to
    come from, and the one thing that could stop it. Anyone in the eleven
    left out of a published side is that thing, and it leads if it exists -
    a projection is worth nothing if the man carrying it is on the bench."""
    xi_ids = {r.element["id"] for r in xi}
    picked = [(r, ep) for r, ep in (eps or []) if r.element["id"] in xi_ids]
    if not picked:
        return ""
    total = sum(ep["total"] for _r, ep in picked)
    lead_r, lead_ep = max(picked, key=lambda x: x[1]["total"])
    where = "at home to" if lead_ep["home"] else "away at"
    line = (f"Gameweek {next_gw}: this eleven projects "
            f"<b>{total:.1f}</b>, the biggest single piece of it "
            f"{e(lead_r.name)} {where} {e(lead_ep['opponent'])}.")

    benched = [e(r.name) for r in xi if ctx.is_predicted(r.element) is False]
    if benched:
        who = benched[0] if len(benched) == 1 else (
            ", ".join(benched[:-1]) + " and " + benched[-1])
        verb = "is" if len(benched) == 1 else "are"
        line += (f" {who} {verb} not in a predicted eleven, so that number "
                 f"is soft until the team news lands.")
    return line


def week_verdict(ctx, gw, squad_ids, captain_id, points, average, pending):
    """One line on where the week actually stands.

    The tiles say what happened; none of them says whether it was good, and
    a score is meaningless without the average beside it. This is the
    sentence a manager would say out loud - the gap to the average, then the
    single biggest reason for it.

    Whether the round is still running changes the question entirely. With
    players left it is "what needs to happen"; once they have all played it
    is "what happened", and the most useful answer to that is nearly always
    a heavily-owned player who hauled and who you did not have."""
    ev = next((x for x in ctx.events if x["id"] == gw), None)
    if not ev or not points:
        return ""

    if pending:
        n = len(pending)
        who = ", ".join(pending[:3]) + ("&hellip;" if n > 3 else "")
        if average and points < average:
            need = average - points
            return (f"<b>{n}</b> still to play &mdash; {who}. "
                    f"You need <b>{need}</b> more to reach this week's "
                    f"<b>{average}</b> average.")
        return (f"<b>{n}</b> still to play &mdash; {who}. "
                f"You are already past the <b>{average}</b> average."
                if average else f"<b>{n}</b> still to play &mdash; {who}.")

    if not average:
        return ""
    gap = points - average
    frame = (f"<b>{points}</b> against a <b>{average}</b> average, "
             f"{'up' if gap >= 0 else 'down'} <b>{abs(gap)}</b>.")

    # The week's biggest miss: the top scorer, if enough managers owned him
    # that not owning him is a real decision rather than bad luck.
    top = (ev.get("top_element_info") or {})
    tid, tpts = top.get("id"), top.get("points")
    if tid and tid not in squad_ids and tpts:
        el = ctx.players.get(tid)
        owned = f(el.get("selected_by_percent")) if el else 0
        if el and owned >= 15:
            # The same miss means different things either side of the
            # average: below it, it is the explanation; above it, it is
            # what the week could still have been.
            tail = ("and not owning him is most of that gap"
                    if gap < 0 else
                    "and you got there without him")
            return (f"{frame} {e(el['web_name'])} scored <b>{tpts}</b> for the "
                    f"<b>{owned:.0f}%</b> who own him, {tail}.")

    # Failing that, the armband is the next biggest single swing.
    cap = ctx.players.get(captain_id)
    if cap:
        cpts = cap.get("event_points") or 0
        most = ctx.players.get(ev.get("most_captained"))
        if most and most["id"] != captain_id and (most.get("event_points") or 0) > cpts:
            return (f"{frame} {e(cap['web_name'])} returned <b>{cpts}</b> as "
                    f"captain against {e(most['web_name'])}'s "
                    f"<b>{most['event_points']}</b> for the crowd.")
        return (f"{frame} {e(cap['web_name'])} brought "
                f"<b>{cpts * 2}</b> back as captain.")
    return frame

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _figures(text):
    """Set the numbers inside a sentence in the mono face.

    Only digits are touched, so there is nothing here that can mangle the
    words around them. It is what makes a findings list scannable: the eye
    goes to the figures without every line having to shout in bold."""
    return _NUM_RE.sub(lambda m: f'<span class="fnum">{m.group()}</span>',
                       e(text))


def finding_card(fnd):
    tone = TONE_COLOR.get(fnd["tone"], "var(--p60)")
    items = []
    for raw in fnd["items"]:
        lead, sep, detail = raw.partition(" - ")
        # Subject as a mono tag, evidence as ordinary prose beside it. The
        # pattern this replaced set the subject in heavy bold on its own line
        # with the evidence in grey underneath, which is the house style of
        # every dashboard template there is - and it made the evidence, the
        # part actually worth reading, the quietest thing on the card.
        if sep and len(lead) < 40:
            items.append(
                f'<li class="fi"><span class="fi-sub">{e(lead)}</span>'
                f'<span class="fi-det">{_figures(detail)}</span></li>'
            )
        else:
            items.append(f'<li class="fi"><span class="fi-det">'
                         f'{_figures(raw)}</span></li>')
    note = f'<p class="note" hidden>{e(fnd["note"])}</p>' if fnd["note"] else ""
    infobtn = components.info_btn() if fnd["note"] else ""
    return (
        f'<div class="find" style="--tone:{tone}">'
        f"<h3>{e(fnd['title'])}{infobtn}</h3>{note}"
        f"<ul class=\"filist\">{''.join(items)}</ul></div>"
    )


def collapsed_finding(fnd):
    """A finding that is worth keeping but not worth showing.

    Last season's numbers are the case: fifteen full-sentence paragraphs of
    context nobody reads before a deadline, taking a whole column of the
    page to say something that only matters when you go looking for it. It
    lives at the bottom, shut, and opens when asked."""
    items = []
    for raw in fnd["items"]:
        lead, sep, detail = raw.partition(" - ")
        if sep and len(lead) < 40:
            items.append(f'<li class="fi"><span class="fi-sub">{e(lead)}</span>'
                         f'<span class="fi-det">{_figures(detail)}</span></li>')
        else:
            items.append(f'<li class="fi"><span class="fi-det">'
                         f'{_figures(raw)}</span></li>')
    note = f'<p class="note">{e(fnd["note"])}</p>' if fnd["note"] else ""
    return (
        '<details class="card collapsible lastseason">'
        f'<summary class="card-head"><h2>{e(fnd["title"])}</h2>'
        f'<span class="sub">{len(fnd["items"])} players &middot; '
        "open for the full-season comparison</span></summary>"
        f'<div class="card-body">{note}'
        f"<ul class=\"filist\">{''.join(items)}</ul></div></details>"
    )


def template_xi(own, by_name, ctx):
    """The most-started legal eleven in the mini-league.

    Not simply the eleven most-owned players: that could be six defenders and
    no keeper. It is also not raw squad ownership, which was the actual bug
    here - a cheap enabler bought purely to free up budget and left on the
    bench everywhere ends up "owned" by half the league without ever being
    part of anyone's eleven. Ranking by how often a player is actually
    started fixes that without a hand-picked price cutoff to call something
    an "enabler". Every legal shape is tried - one keeper, three to five
    defenders, two to five midfielders, one to three forwards, eleven in all -
    and the one with the most total starts wins, which is what "the
    template" actually means. Ties go to the pricier player: when two
    players are started equally often, the more expensive one is the one
    actually earning that XI slot rather than sitting in it as a value pick."""
    n = len(by_name)
    if not own or not n:
        return None
    pools = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pid, rec in own.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        pools[ctx.pos(el)].append((len(rec["starters"]), el, rec))
    for key in pools:
        pools[key].sort(key=lambda x: (-x[0], -x[1]["now_cost"], -x[1]["total_points"]))

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


def template_pitch(tpl, ctx, shirts, my_name, known_ids=frozenset()):
    """The template eleven, laid out on a pitch.

    `known_ids` are the ids the player dialog has a payload for (the
    manager's own squad) - most of a league template is other managers'
    picks, so only those cards get the clickable attributes."""
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
            mine = my_name in rec["starters"]
            pct = 100.0 * count / n
            clickable = (
                f'data-player="{el["id"]}" role="button" tabindex="0" '
                if el["id"] in known_ids else ""
            )
            cards.append(
                f'<div class="pl{" tpl-mine" if mine else ""}" '
                f'{clickable}'
                f'title="{e(el["web_name"])} - started by {count} of {n}'
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
        if my_name in rec["starters"]
    )
    return (
        f'<section class="card"><div class="card-head"><h2>League template{components.info_btn()}</h2>'
        f'<span class="sub" hidden>The most-started legal eleven across {n} managers, '
        f'in a {tpl["shape"]}. You have {owned_by_you} of them &mdash; the rest '
        "is where your rank moves.</span></div>"
        f'<div class="pitch tplpitch">{components.PITCH_MARKS}'
        f'{"".join(rows)}</div></section>'
    )


def differential_watchlist(own, ctx, proj, market, baselines, next_gw, squad_ids,
                           limit=6):
    """Players performing well that nobody in this league owns - not you,
    not any rival.

    Scored with transfers.case_score, the same several-week, form-and-
    underlying-numbers logic the Planning tab's transfer suggestions use -
    "performing well" means the same thing here as everywhere else that
    phrase appears on this page, not a separate reading of the numbers."""
    if not own:
        return []
    priors = transfers.positional_priors(ctx)
    owned_ids = set(own.keys()) | set(squad_ids)
    rows = []
    for el in ctx.players.values():
        pid = el["id"]
        if pid in owned_ids or not transfers._eligible(el, ctx):
            continue
        s = transfers.case_score(el, ctx, proj, next_gw, market, baselines, priors)
        if not s or s["total"] <= 0:
            continue
        rows.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "price": el["now_cost"] / 10.0,
            "ep": s["total"], "opponent": s["opponent"], "home": s["home"],
            "owned_pct": f(el.get("selected_by_percent")),
            "duties": components.duty_badges(el),
        })
    rows.sort(key=lambda r: -r["ep"])
    return rows[:limit]


def differential_watchlist_card(rows, photos, weeks):
    """The Your differentials card, run the other direction and forward-
    looking: not what you already hold that's rare, but what's rare and
    still worth going and getting."""
    if not rows:
        return ""
    cards = []
    for r in rows:
        el_photo = photos.get(r["id"])
        face = (
            f'<img class="df-photo" src="{el_photo}" alt="" width="84" height="106">'
            if el_photo else f'<div class="df-photo df-blank">{e(r["name"][:1])}</div>'
        )
        fixture = f'{"vs" if r["home"] else "at"} {e(r["opponent"])}'
        cards.append(
            f'<li class="df-card"><div class="df-frame">{face}{r["duties"]}</div>'
            f'<div class="df-body"><p class="df-name">{e(r["name"])}</p>'
            f'<p class="df-meta">{e(r["pos"])} &middot; '
            f'{e(r["club"])} &middot; {r["price"]:.1f}m</p>'
            f'<dl class="df-stats">'
            f'<div><dt>{weeks}-week</dt><dd>{r["ep"]:.1f}</dd></div>'
            f'<div><dt>Next</dt><dd>{fixture}</dd></div>'
            f'<div><dt>Owned</dt><dd>{r["owned_pct"]:.0f}%</dd></div>'
            f"</dl></div></li>"
        )
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Differential watchlist{components.info_btn()}</h2>'
        '<span class="sub" hidden>Nobody in this league owns these - scored the '
        f'same way as every transfer suggestion on the Planning tab, over the '
        f'next {weeks} gameweeks.</span></div>'
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
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
            f'<section class="card"><div class="card-head"><h2>Your differentials{components.info_btn()}</h2>'
            '<span class="sub" hidden>Players nobody else in the league owns.</span></div>'
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
        f'<section class="card"><div class="card-head"><h2>Your differentials{components.info_btn()}</h2>'
        f'<span class="sub" hidden>Nobody else in this league owns '
        f'{"them" if len(mine) > 1 else "him"}. Every point '
        f'{"they score" if len(mine) > 1 else "he scores"} is a point on the '
        "whole league.</span></div>"
        f'<div class="card-body"><ul class="dflist">{"".join(cards)}</ul></div>'
        "</section>"
    )


def rival_returns(own, by_name, ctx, my_name, squad_ids, limit=5):
    """Players who scored for the rest of this league last week, and not
    for you - ranked by the points themselves, highest first.

    An earlier version ranked by points times how many rivals started him,
    on the reasoning that a haul only costs you ground in proportion to how
    much of the league held it. In practice that produced a top-to-bottom
    order that did not read as "who hurt me" at a glance - a 6-pointer
    could outrank a 13-pointer - so the simpler, checkable number leads
    instead. How many rivals held him is still shown, just as context
    rather than the sort key."""
    if not own or not my_name:
        return []
    rows = []
    for pid, rec in own.items():
        if pid in squad_ids:
            continue
        starters = [n for n in rec["starters"] if n != my_name]
        if not starters:
            continue
        el = ctx.players.get(pid)
        if not el:
            continue
        pts = el.get("event_points") or 0
        if pts <= 0:
            continue
        caps = [n for n in rec["captains"] if n != my_name]
        rows.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "points": pts,
            "starters": len(starters), "captains": len(caps),
        })
    rows.sort(key=lambda r: -r["points"])
    return rows[:limit]


def rival_returns_window(rows, ctx, my_name, squad_ids, gw, weeks=3, limit=5,
                         ttl=fplapi.DEFAULT_TTL):
    """rival_returns, summed over the last `weeks` gameweeks rather than
    the one just gone - a single bad week can be an anomaly; a player who
    keeps doing it to you over a month is a pattern.

    The current gameweek's rival squads are already fetched elsewhere in
    build(), but an earlier gameweek is a different squad for each of them
    and needs its own picks request - this refetches those specifically,
    bounded to the same rivals (`rows[:limit]`) already shown everywhere
    else on the mini-league tab, so the added cost is `weeks` extra picks
    calls per existing rival, not any new managers. Each gameweek's player
    points come from one shared event_live call covering everyone, rather
    than one request per player."""
    if not rows or not my_name:
        return []
    totals = {}
    start = max(1, gw - weeks + 1)
    for week in range(start, gw + 1):
        try:
            live = fplapi.event_live(week, ttl=ttl)
        except fplapi.FplError:
            continue
        points_by_pid = {
            e["id"]: e.get("stats", {}).get("total_points", 0)
            for e in live.get("elements", [])
        }
        by_name_week = {}
        for r in rows[:limit]:
            try:
                by_name_week[r["entry_name"]] = analysis.squad_for(r["entry"], week, ctx)
            except fplapi.FplError:
                continue
        own_week = analysis.league_ownership(by_name_week)
        for pid, rec in own_week.items():
            if pid in squad_ids:
                continue
            starters = [n for n in rec["starters"] if n != my_name]
            if not starters:
                continue
            pts = points_by_pid.get(pid, 0)
            if pts <= 0:
                continue
            caps = [n for n in rec["captains"] if n != my_name]
            agg = totals.setdefault(
                pid, {"points": 0, "weeks": 0, "starters": 0, "captains": 0})
            agg["points"] += pts
            agg["weeks"] += 1
            agg["starters"] = max(agg["starters"], len(starters))
            agg["captains"] += len(caps)

    out = []
    for pid, agg in totals.items():
        el = ctx.players.get(pid)
        if not el:
            continue
        out.append({
            "id": pid, "name": el["web_name"], "pos": ctx.pos(el),
            "club": ctx.team_name(el["team"]), "points": agg["points"],
            "starters": agg["starters"], "captains": agg["captains"],
            "weeks": agg["weeks"],
        })
    out.sort(key=lambda r: -r["points"])
    return out[:limit]


def _rivals_list(rows, rivals, photos, weeks_note=False):
    if not rows:
        return '<p class="lc-clear">Nobody else in the league returned against you.</p>'
    top = max(r["points"] for r in rows) or 1
    items = []
    for r in rows:
        photo = photos.get(r["id"])
        face = (
            f'<img class="rv-photo" src="{photo}" alt="" width="44" height="56">'
            if photo
            else f'<span class="rv-photo rv-blank">{e(r["name"][:1])}</span>'
        )
        bits = [e(f'started by {r["starters"]} of {rivals}')]
        if r["captains"]:
            bits.append(e(f'{r["captains"]} captained him'))
        if weeks_note:
            bits.append(e(f'returned in {r["weeks"]} of the weeks shown'))
        items.append(
            f'<li class="rv-row">{face}'
            f'<span class="rv-who"><b>{e(r["name"])}</b>'
            f'<span>{e(r["pos"])} &middot; {e(r["club"])}</span></span>'
            f'<span class="rv-pts num">{r["points"]}</span>'
            f'<span class="rv-track"><i style="width:'
            f'{r["points"] / top * 100:.0f}%"></i></span>'
            f'<span class="rv-note">{" &middot; ".join(bits)}</span></li>'
        )
    return f'<ul class="rvlist">{"".join(items)}</ul>'


def rivals_card(rows, window_rows, rivals, photos, weeks=3):
    """The counterpart to Your differentials, from the other direction.

    Not called "reverse differentials" - the thing worth naming here is the
    consequence, not the jargon. These are points that went onto other
    people's scores and not yours, which in a mini-league is the only kind
    of points that actually moves you.

    Two views, toggled rather than shown one below the other: the week
    just gone, and the last few weeks summed - a single bad week can be a
    fluke, a name that keeps showing up over a month is a pattern. Both
    rank by points scored, highest first; the bar is that same number, not
    a separate "damage" figure - the previous version ranked and drew the
    bar by points times how many rivals held him, which read as
    unpredictable (a 6-pointer could sit above a 13-pointer) rather than
    as "who hurt me"."""
    if not rows and not window_rows:
        return ""
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Scoring against you{components.info_btn()}</h2>'
        '<span class="sub" hidden>Players you did not own who returned for the '
        "rest of this league. Ranked by points scored, highest first.</span></div>"
        '<div class="card-body">'
        '<div class="rvtabs" role="tablist" aria-label="Time range">'
        '<button class="rvtab" role="tab" aria-selected="true" data-rv="now">'
        "This week</button>"
        f'<button class="rvtab" role="tab" aria-selected="false" data-rv="window">'
        f"Last {weeks} weeks</button>"
        "</div>"
        f'<div class="rvpanel" data-rv="now">{_rivals_list(rows, rivals, photos)}</div>'
        f'<div class="rvpanel" data-rv="window" hidden>'
        f'{_rivals_list(window_rows, rivals, photos, weeks_note=True)}</div>'
        "</div></section>"
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

    def _rank(key, fmt, ascending, opta, positions):
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
        return [
            (el["web_name"], ctx.team_name(el["team"]), fmt.format(v),
             el["id"] in mine)
            for v, el in rows[:depth]
        ]

    def build(title, note, icon, tone, key, fmt="{:.2f}", ascending=False,
              opta=False, positions=None):
        return {
            "title": title, "note": note, "icon": icon, "tone": tone,
            "rows": _rank(key, fmt, ascending, opta, positions),
        }

    def build_pair(title, note, icon, tone, primary_key, secondary_key):
        # One player per row, ranked on the primary measure, with a second
        # measure of the same family shown alongside rather than as a card
        # of its own - "how many big chances" and "how many chances overall"
        # are the same question asked at two thresholds, and a big chance is
        # a subset of a chance, so the pair is one player's answer, not two
        # separate leaderboards that happen to share a topic.
        rows = []
        for el in pool:
            ps = el.get("_pulse") or {}
            primary = ps.get(primary_key)
            if not primary:
                continue
            rows.append((primary, ps.get(secondary_key) or 0, el))
        rows.sort(key=lambda x: (-x[0], -x[1]))
        return {
            "title": title, "note": note, "icon": icon, "tone": tone,
            "pair": True,
            "rows": [
                (el["web_name"], ctx.team_name(el["team"]), primary, secondary,
                 el["id"] in mine)
                for primary, secondary, el in rows[:depth]
            ],
        }

    # Six cards used to carry six unrelated hues, which meant colour never
    # carried information across this row - a card's tone told you nothing
    # you couldn't already get from its icon. One hue per role instead: ink
    # for the four attacking measures, premium teal for the one defensive
    # card that flips the ranking (xGC), attention amber for DefCon.
    groups = [
        build("Expected goals", "xG this season", "ball", "var(--ink)",
              "expected_goals"),
        build("Expected assists", "xA this season", "key", "var(--ink)",
              "expected_assists"),
        build("Goal involvement", "xG plus xA", "spark", "var(--ink)",
              "expected_goal_involvements"),
        build_pair(
            "Big chances/chances",
            "Shown as big chances, chances - a big chance is a clear "
            "opening, a chance is any pass leading to a shot",
            "run", "var(--ink)", "big_chance_created", "total_att_assist",
        ),
        build("Fewest goals expected against", "xGC, defenders and keepers",
              "shield", "var(--accent-ink)", "expected_goals_conceded", ascending=True,
              positions=("GKP", "DEF")),
        build("Defensive contributions", "Tackles, recoveries and blocks banked this season",
              "shield", "var(--accent-ink)", "defensive_contribution", fmt="{:.0f}"),
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
        "priceChange": round(el.get("cost_change_start", 0) / 10.0, 1),
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


def _mini_shirt_card(pid, pos, team_id, team_name, name, price, ctx, badges,
                     shirts, fx_html="", incoming=False, known=True):
    """One shirt card for a compact pitch/bench view - the same `.pl`
    component the Squad tab pitch uses, but built from whatever identifies
    a player rather than requiring a full PlayerReport, since a proposed
    incoming man has no match history to build one from. `incoming` adds a
    distinct outline and an IN tag, for a squad view that mixes players
    actually owned with ones only being suggested. `known` is False when
    the player dialog has no payload for this id (a suggested player who
    is not in the manager's own squad) - those cards render without the
    clickable attributes rather than opening a dialog that silently does
    nothing."""
    shirt = shirts.get((team_id, pos == "GKP"))
    uri = shirt or badges.get(team_id)
    crest = (
        f'<img class="kit" src="{uri}" alt="{e(team_name)}">' if shirt
        else f'<img class="crestimg" src="{uri}" alt="{e(team_name)}">' if uri
        else f'<span class="letters">{e(team_name)}</span>'
    )
    tag = ('<span class="pl-in-tag" title="Suggested incoming">IN</span>'
           if incoming else "")
    cls = "pl pk pl-incoming" if incoming else "pl pk"
    title = f"{name} - {pos}, {team_name}, {price:.1f}m"
    fx = f'<div class="pk-fx">{fx_html}</div>' if fx_html else ""
    clickable = f'data-player="{pid}" role="button" tabindex="0" ' if known else ""
    return (
        f'<div class="{cls}" {clickable}title="{e(title)}">'
        f'{tag}<div class="crest">{crest}</div>'
        f'<div class="nm">{e(name)}</div>{fx}</div>'
    )


def _fixture_pill_for(team_name, pos, proj, market, next_gw):
    rows = ticker._rows_for(team_name, proj, market, next_gw, 1)
    if not rows:
        return ""
    r = rows[0]
    return pos_fixture_pill(pos, r["opp"], r["home"], r["cs"], r["xg"])


def _report_row(r):
    return (r.element["id"], r.pos, r.element["team"], r.team, r.name, r.price)


def _pool_row(p, ctx):
    el = ctx.players[p["id"]]
    return (p["id"], p["pos"], el["team"], p["club"], el["web_name"], p["price"])


def mini_pitch(xi_rows, bench_rows, ctx, badges, shirts, incoming_ids=frozenset(),
               known_ids=None):
    """A much smaller version of the Squad tab pitch - shirts and names
    only, no stats footer - for a before/after comparison where two full
    squads need to sit side by side without either one dominating the
    card. Starting XI grouped by position on the pitch, bench below in its
    own strip, the same split the real FPL app shows - not all fifteen
    lumped into position rows with no start/bench distinction. `xi_rows`
    and `bench_rows` are each a list of (id, pos, club_id, club_name, name,
    price) tuples, the common shape _report_row and _pool_row reduce a
    PlayerReport or a squadbuilder pool entry to, so this does not need to
    care which kind of squad it was given. Bench cards run cheapest to
    priciest left to right, matching how the Wildcard bench itself is now
    chosen (see squadbuilder.best_squad)."""
    order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    by_pos = {1: [], 2: [], 3: [], 4: []}
    for row in xi_rows:
        by_pos[order.get(row[1], 4)].append(row)
    out = ['<div class="pitch mini">' + components.PITCH_MARKS]
    for k in (1, 2, 3, 4):
        if not by_pos[k]:
            continue
        cards = "".join(
            _mini_shirt_card(pid, pos, team_id, team_name, name, price,
                             ctx, badges, shirts, incoming=pid in incoming_ids,
                             known=known_ids is None or pid in known_ids)
            for pid, pos, team_id, team_name, name, price in by_pos[k]
        )
        out.append(f'<div class="row">{cards}</div>')
    out.append("</div>")
    bench_cards = "".join(
        _mini_shirt_card(pid, pos, team_id, team_name, name, price,
                         ctx, badges, shirts, incoming=pid in incoming_ids,
                         known=known_ids is None or pid in known_ids)
        for pid, pos, team_id, team_name, name, price
        in sorted(bench_rows, key=lambda row: row[5])
    )
    out.append(
        f'<div class="benchstrip"><div class="lbl">Bench</div>'
        f'<div class="row">{bench_cards}</div></div>'
    )
    return "".join(out)


def wildcard_section(wc, xi_reports, bench_reports, ctx, badges, shirts):
    """The proposed full-squad rebuild as two small pitches, not a table of
    price deltas - "would I actually want this squad" is a look-at-the-
    shirts question. Now above, Proposed below, with a distinct outline
    and an IN tag on whichever names in the proposed squad are not already
    owned - the eye only needs to find the outlined shirts to see what a
    Wildcard here would actually change, rather than reading fifteen rows
    of a table to work it out."""
    if not wc or not wc.get("ideal_xi"):
        return ""
    before_xi = [_report_row(r) for r in xi_reports]
    before_bench = [_report_row(r) for r in bench_reports]
    after_xi = [_pool_row(p, ctx) for p in wc["ideal_xi"]]
    after_bench = [_pool_row(p, ctx) for p in wc["ideal_bench"]]
    incoming_ids = wc.get("incoming_ids") or set()
    after_known_ids = {row[0] for row in after_xi + after_bench} - incoming_ids
    start, weeks = wc["gw_window"]
    stats_html = components.wc_stats_block(wc.get("before"), wc.get("after"))
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        f'<h2>Wildcard rebuild{components.info_btn()}</h2>'
        f'<span class="sub" hidden>The full squad this would become, scored '
        f'across GW{start}-{start + weeks - 1}. Outlined shirts with an IN '
        f'tag are not already owned.</span></summary>'
        f'<div class="card-body">{stats_html}'
        '<div class="wcpitches">'
        f'<div class="wcpitch"><h4>Now</h4>'
        f'{mini_pitch(before_xi, before_bench, ctx, badges, shirts)}</div>'
        f'<div class="wcpitch"><h4>Proposed</h4>'
        f'{mini_pitch(after_xi, after_bench, ctx, badges, shirts, incoming_ids, after_known_ids)}</div>'
        "</div></div></details>"
    )


def bench_boost_pitch(bb, bench_reports, ctx, badges, shirts, proj, market,
                      next_gw):
    """The four names actually proposed for the bench on Bench Boost week,
    laid out as the same bench strip the Squad tab pitch already draws -
    not a table of price deltas, since "is this a bench worth boosting" is
    a look-at-the-shirts-and-fixtures question, not a spreadsheet one. A
    suggested incoming swap replaces the outgoing man's slot outright, so
    this shows the bench as it WOULD be, not the one sitting there today -
    with a distinct outline and an IN tag on whichever slots changed, so a
    glance tells you which of the four are new."""
    if not bb:
        return ""
    out_by_id = {t["out"].element["id"]: t
                for t in (bb.get("transfers") or [])}
    cards = []
    for r in bench_reports:
        t = out_by_id.get(r.element["id"])
        if t:
            el = t["in"]
            team_name = ctx.team_name(el["team"])
            cards.append(_mini_shirt_card(
                el["id"], ctx.pos(el), el["team"], team_name,
                el["web_name"], el["now_cost"] / 10.0, ctx, badges, shirts,
                fx_html=_fixture_pill_for(team_name, ctx.pos(el), proj,
                                          market, next_gw),
                incoming=True, known=False))
        else:
            cards.append(_mini_shirt_card(
                r.element["id"], r.pos, r.element["team"], r.team, r.name,
                r.price, ctx, badges, shirts,
                fx_html=_fixture_pill_for(r.team, r.pos, proj, market, next_gw),
                incoming=False))
    note = ("Moves that would improve that specific week, not this one."
           if bb["transfers"] else
           "Your bench as it stands - nothing here is worth changing "
           "for that week.")
    return (
        '<details class="card collapsible swapcard"><summary class="card-head">'
        f'<h2>Bench Boost rebuild, GW{bb["gw"]}{components.info_btn()}</h2>'
        f'<span class="sub" hidden>{e(note)}</span></summary>'
        f'<div class="card-body"><div class="benchstrip bbpitch">'
        f'<div class="row">{"".join(cards)}</div></div></div></details>'
    )


def _cp_card(label, used_gw, body_html, level=None):
    if used_gw:
        return (
            f'<div class="cp used"><p class="cp-label">{e(label)}</p>'
            f'<p class="cp-used-tag">Already used, GW{used_gw}</p></div>'
        )
    tone = f" cp-{level}" if level else ""
    return (f'<div class="cp{tone}"><p class="cp-label">{e(label)}</p>'
            f'{body_html}</div>')


def chip_planner_card(fh, tc, bb, wc, used, xi, bench, ctx, badges, shirts,
                      proj, market, next_gw):
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
            f'against your XI\'s {pt["ours_value"]:.1f} that week - a gap of '
            f'{fh["gap"]:.1f}.</p>'
            f'{conf_pill(fh["confidence"])}'
        )
        cards.append(_cp_card("Free Hit", used.get("freehit"), body,
                              fh["confidence"]))

    if tc:
        body = (
            f'<p class="cp-gw">GW{tc["gw"]}</p>'
            f'<p class="cp-reason">Captain {e(tc["player"].name)} for '
            f'{tc["ep"]:.1f} pts ({tc["ep"] * 2:.1f} with the armband).</p>'
            f'{conf_pill(tc["confidence"])}'
        )
        cards.append(_cp_card("Triple Captain", used.get("3xc"), body,
                              tc["confidence"]))

    if bb:
        body = (
            f'<p class="cp-gw">GW{bb["gw"]}</p>'
            f'<p class="cp-reason">Bench projects {bb["ep"]:.1f} pts that week'
            f'{" - if your bench stays as it is." if not bb["transfers"] else "."}</p>'
            f'{conf_pill(bb["confidence"])}'
        )
        cards.append(_cp_card("Bench Boost", used.get("bboost"), body,
                              bb["confidence"]))

    if wc:
        start, weeks = wc["gw_window"]
        body = (
            f'<p class="cp-gw">GW{start}-{start + weeks - 1}</p>'
            f'<p class="cp-reason">{wc["gap"]:.1f} pts of upside available '
            f'over the window.</p>'
            f'{conf_pill(wc["confidence"])}'
        )
        cards.append(_cp_card("Wildcard", used.get("wildcard"), body,
                              wc["confidence"]))

    # The grid above is the compact per-chip summary only; each chip's
    # actual squad change is its own collapsed card below it - a rebuild
    # you are not doing this week does not deserve a screen of its own
    # every visit.
    extra = []
    if bb:
        extra.append(bench_boost_pitch(bb, bench, ctx, badges, shirts,
                                       proj, market, next_gw))
    if wc:
        extra.append(wildcard_section(wc, xi, bench, ctx, badges, shirts))

    return (
        f'<section class="card"><div class="card-head"><h2>Chip planner{components.info_btn()}</h2>'
        '<span class="sub" hidden>Best gameweek for each chip in the current half, '
        'scored from the same projections as the rest of the page.</span></div>'
        f'<div class="card-body"><ul class="cplist">{"".join(cards)}</ul></div></section>'
        f'{"".join(extra)}'
    )


TICK_SVG = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M3 8.5 6.4 12 13 4.6" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
WARN_SVG = ('<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M8 2.6 15 14H1Z" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linejoin="round"/>'
            '<path d="M8 6.6v3.2" stroke="currentColor" stroke-width="1.7" '
            'stroke-linecap="round"/><circle cx="8" cy="11.9" r="1" '
            'fill="currentColor"/></svg>')

HOME_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 11.5 12 4l8 7.5V19a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1Z" '
            'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>')
AWAY_SVG = ('<svg class="venue-icon" viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="4" y="8" width="16" height="11" rx="2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/>'
            '<path d="M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" fill="none" '
            'stroke="currentColor" stroke-width="1.7"/></svg>')

POS_LABEL = {"GKP": "Goalkeeper", "DEF": "Defenders",
             "MID": "Midfielders", "FWD": "Forwards"}
POS_SEQ = ("GKP", "DEF", "MID", "FWD")


def best_xi_card(pt, ctx, squad_ids, next_gw):
    """The highest-projecting eleven available in the whole game for the
    coming week, against the eleven actually owned.

    Sorted into positions rather than one ranked list, because the useful
    question is not "who scores most" - it is "where is my team behind",
    and that only reads position by position. Owned players are ticked
    rather than pulled out into their own group, so the gap between the
    two teams is a count you can see rather than a number to be trusted.

    No budget cap, but the real 3-per-club squad limit still applies - the
    literal highest-scoring valid formation in the game (see
    chips.literal_best_xi), not the best one affordable at the manager's
    own squad value."""
    if not pt or not pt.get("ideal_xi"):
        return ""
    xi = pt["ideal_xi"]
    owned_n = sum(1 for p in xi if p["id"] in squad_ids)
    top = max(p["value"] for p in xi) or 1.0

    groups = []
    for pos in POS_SEQ:
        men = sorted((p for p in xi if p["pos"] == pos),
                     key=lambda p: -p["value"])
        if not men:
            continue
        rows = []
        for p in men:
            el = ctx.players.get(p["id"])
            name = el["web_name"] if el else "?"
            mine = p["id"] in squad_ids
            rows.append(
                f'<li class="bxi-row{" is-mine" if mine else ""}">'
                f'<span class="bxi-mark" aria-hidden="true">'
                f'{TICK_SVG if mine else ""}</span>'
                f'<span class="bxi-name">{e(name)}</span>'
                f'<span class="bxi-club">{e(p["club"])}</span>'
                f'<span class="bxi-bar"><i style="width:'
                f'{p["value"] / top * 100:.0f}%"></i></span>'
                f'<span class="bxi-ep num">{p["value"]:.1f}</span></li>'
            )
        groups.append(
            f'<div class="bxi-group"><h4>{e(POS_LABEL[pos])}</h4>'
            f'<ul>{"".join(rows)}</ul></div>'
        )

    gap = pt["gap"]
    if gap < 0.5:
        read = ("Your eleven is already within half a point of the best "
                "possible one in the game. There is nothing to chase here.")
    else:
        read = (f"Your eleven projects {pt['ours_value']:.1f}. The gap is "
                f"{gap:.1f} points, spread across the "
                f"{11 - owned_n} name{'s' if 11 - owned_n != 1 else ''} you "
                f"do not own.")

    return (
        '<section class="card bxicard"><div class="card-head">'
        f'<h2>Highest predicted points XI{components.info_btn()}</h2>'
        f'<span class="sub" hidden>The literal highest-scoring valid eleven in the '
        f'game for gameweek {next_gw} - no budget, but the real 3-per-club '
        f'limit and formation rules still apply.</span></div>'
        '<div class="card-body">'
        '<div class="bxi-head">'
        f'<div class="bxi-big"><span class="num">{pt["ideal_value"]:.1f}</span>'
        f'<small>projected, best XI</small></div>'
        f'<p class="bxi-own">{TICK_SVG}<b>{owned_n} of 11</b> already yours</p>'
        f'<p class="bxi-read">{e(read)}</p></div>'
        f'<div class="bxi-grid">{"".join(groups)}</div>'
        "</div></section>"
    )


def kneejerk_card(kj, gw):
    """The player who hauled last week and is not in the squad.

    Deliberately named for the impulse rather than dressed up as a
    recommendation, and deliberately loud - it is the one card on the page
    arguing with the reader rather than informing them. Last week's points
    are the single number here with no predictive weight whatsoever, so
    they are printed at full size and then immediately answered by the
    projection for the coming week and the best alternative at the same
    money. If the case survives that, it was never a knee-jerk."""
    if not kj:
        return ""
    ep = kj["ep"]
    next_gw_ep = kj["next_gw_ep"]
    rival = kj["rival"]
    funder = kj["funder"]

    funder_pair = kj.get("funder_pair")
    if ep is None:
        verdict, tone = "No fixture priced for him yet this week.", "warn"
    elif rival and rival["ep"] > ep:
        verdict = (f'{rival["name"]} at {rival["price"]:.1f}m projects '
                   f'{rival["ep"] - ep:+.2f} more over the next '
                   f'{transfers.TRANSFER_HORIZON_WEEKS} gameweeks for the same slot.')
        tone = "bad"
    elif not funder and funder_pair:
        verdict = (
            f"One transfer will not reach him, but selling "
            f"{e(funder_pair['primary'].name)} and "
            f"{e(funder_pair['second'].name)} together would, backfilled "
            f"by {e(funder_pair['replacement']['web_name'])} at "
            f"{funder_pair['replacement']['now_cost'] / 10.0:.1f}m - see "
            f"Suggested pairs below."
        )
        tone = "warn"
    elif not funder:
        verdict = (f"You cannot reach him: nobody you own at {kj['pos']} "
                   f"frees up {kj['price']:.1f}m, even in a pair.")
        tone = "warn"
    else:
        verdict = (f"He also holds up on the projection, and selling "
                   f"{e(funder.name)} would pay for him.")
        tone = "good"

    fixture = ""
    if kj["opponent"]:
        fixture = (f'<span class="kj-fx">{"vs" if kj["home"] else "at"} '
                   f'{e(kj["opponent"])}</span>')
    ep_txt = f"{next_gw_ep:.1f}" if next_gw_ep is not None else "&mdash;"
    ep5_txt = f"{ep:.1f}" if ep is not None else "&mdash;"

    return (
        f'<section class="card kjcard kj-{tone}">'
        '<div class="kj-tag">The knee-jerk</div>'
        '<div class="kj-body">'
        f'<p class="kj-lead">You did not own <b>{e(kj["name"])}</b>, and he '
        f'scored</p>'
        f'<p class="kj-score"><span class="num">{kj["points"]}</span>'
        f'<small>in gameweek {gw}</small></p>'
        '<dl class="kj-facts">'
        f'<div><dt>Price</dt><dd class="num">{kj["price"]:.1f}m</dd></div>'
        f'<div><dt>Owned</dt><dd class="num">{kj["owned"]:.1f}%</dd></div>'
        f'<div><dt>Bought this week</dt><dd class="num">{kj["bought"]:,}</dd></div>'
        f'<div><dt>Next GW</dt><dd class="num">{ep_txt}</dd></div>'
        f'<div><dt>Next {transfers.TRANSFER_HORIZON_WEEKS} GW</dt><dd class="num">{ep5_txt}</dd></div>'
        "</dl>"
        f'<p class="kj-verdict">{verdict} {fixture}</p>'
        "</div></section>"
    )


VERDICT_COLS = [
    ("buy", "Buy", "good", "Not yours, reachable, projects highest."),
    ("sell", "Sell", "bad", "A named replacement projects meaningfully more."),
    ("keep", "Keep", "accent", "Nothing above wants to move him."),
    ("avoid", "Avoid", "warn", "Being bought hard; a cheaper man projects more."),
]


def verdict_board_card(vb, next_gw):
    """Buy, Sell, Keep, Avoid as four columns with four different rules.

    See transfers.verdict_board for what each one actually means - the
    important part is that they are four questions rather than one ranking
    cut into quarters, and Avoid is the only column reading the transfer
    market rather than the model."""
    if not vb or not any(vb.get(k) for k, _l, _t, _s in VERDICT_COLS):
        return ""
    cols = []
    for key, label, tone, sub in VERDICT_COLS:
        rows = vb.get(key) or []
        if not rows:
            items = '<li class="vb-none">Nothing this week.</li>'
        else:
            items = "".join(
                f'<li><span class="vb-top"><b>{e(r["name"])}</b>'
                f'<span class="vb-ep num">{r["ep"]:.1f}</span></span>'
                f'<span class="vb-sub">{e(r["club"])} &middot; '
                f'{r["price"]:.1f}m &middot; {e(r["note"])}</span></li>'
                for r in rows
            )
        cols.append(
            f'<div class="vb-col vb-{tone}"><h4>{e(label)}</h4>'
            f'<p class="vb-rule">{e(sub)}</p><ul>{items}</ul></div>'
        )
    return (
        '<section class="card vbcard"><div class="card-head">'
        f'<h2>Buy, sell, keep, avoid{components.info_btn()}</h2>'
        f'<span class="sub" hidden>Four different questions, not one ranking split '
        f'four ways. The figure beside each name is total projected points '
        f'across the next {transfers.TRANSFER_HORIZON_WEEKS} gameweeks - not '
        f'gameweek {next_gw} alone - plus a small nudge for recent form and '
        f'underlying numbers, which is why it reads much higher than a '
        f'single week\'s score. The opponent named in each note is still '
        f'just the very next fixture, for context.</span></div>'
        f'<div class="card-body vb-grid">{"".join(cols)}</div></section>'
    )


def captaincy_card(cm):
    """The Captaincy Decision Matrix - a radar chart overlaying this
    gameweek's top expected-points XI candidates across form, fixture
    strength, goal threat, start certainty, and set-piece responsibilities,
    so the shapes can be compared directly. Home/away is a small venue icon
    by each name rather than a sixth axis - see captaincy.py for why, and
    for what each remaining axis actually measures and where the numbers
    come from."""
    if not cm:
        return ""
    # candidates are ranked by projected points, highest first - see
    # captaincy.matrix.
    top = cm["candidates"][0]
    legend = "".join(
        f'<li class="radar-leg" data-i="{i}" tabindex="0" role="button" '
        f'aria-pressed="false">'
        f'<span class="radar-swatch radar-c{i}"></span>'
        f'<span class="radar-leg-text"><span class="radar-leg-name">'
        f'{HOME_SVG if c["home"] else AWAY_SVG}{e(c["player"])}</span>'
        f'<span class="radar-leg-sub">vs {e(c["opponent"])} '
        f'({"H" if c["home"] else "A"}) &middot; {c["ep_total"]:.1f} pts proj</span></span>'
        "</li>"
        for i, c in enumerate(cm["candidates"])
    )
    data = {
        "metrics": [{"key": k, "label": lbl, "unit": u} for k, lbl, u in cm["metrics"]],
        "candidates": cm["candidates"],
    }
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>Captaincy decision matrix{components.info_btn()}</h2>'
        f'<span class="sub" hidden>This gameweek\'s top armband candidates from your XI, '
        f'overlaid across five axes. Each axis is scaled to that metric\'s '
        f'own real range (0.5x-2.0x for the fixture multiplier, 0-100% for '
        f'start certainty, and so on - see captaincy.py) - not to whoever '
        f'else is shown - so the edge of the chart means the same thing '
        f'every week: genuinely one of the best fixtures or returns anyone '
        f'gets, not just the best of this shortlist. Two candidates from the '
        f'same club can also share an axis exactly (same team, same '
        f'fixture), which is a genuine tie, not missing data. Ranked by '
        f'projected points - <b>{e(top["player"])}</b> is on top this week - '
        f'the shape shows why. Click a name for the full breakdown.</span></div>'
        '<div class="card-body cap-layout">'
        f'<div class="cap-side"><ul class="radar-legend">{legend}</ul>'
        '<p class="radar-readout" aria-live="polite">Hover a shape or a dot for its value.</p></div>'
        # Padded well past CX/CY/R/TEXT_R in captaincy.js (currently
        # 210/195/130/174) on every side - a long label like "Fixture (xG
        # mult)" or a pinned callout's value line grows outward from an
        # anchor already near the edge of the plain drawing area, and gets
        # clipped against the SVG's own edge (an SVG root defaults to
        # overflow:hidden) rather than the card if there is no margin left
        # for it. Change CX/CY/R/TEXT_R together with this viewBox, not
        # separately - they size the same canvas.
        '<div class="cap-chart scroll"><svg class="radar" viewBox="-100 -10 640 400" '
        'role="img" aria-label="Captaincy decision matrix radar chart"></svg>'
        "</div>"
        f'<script type="application/json" class="captaincy-data">{json.dumps(data)}</script>'
        "</div></section>"
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


def league_position_series(histories, my_name):
    """Every manager's league position and total points, gameweek by
    gameweek - built entirely from the entry histories already fetched for
    the Chips used table, so this costs no extra requests.

    Position is rank by THIS LEAGUE's total points at each gameweek, not
    each manager's FPL-wide overall rank - "your position" in a
    mini-league context means position among these rivals, not among the
    ten million entries FPL actually has."""
    if not histories:
        return None
    by_gw = {}
    for name, h in histories.items():
        for row in h.get("current", []):
            by_gw.setdefault(row["event"], {})[name] = row["total_points"]
    if not by_gw:
        return None
    gws = sorted(by_gw.keys())
    points = {name: [] for name in histories}
    position = {name: [] for name in histories}
    for gw in gws:
        totals = by_gw[gw]
        ranked = sorted(totals.items(), key=lambda x: -x[1])
        rank_by_name = {name: i + 1 for i, (name, _pts) in enumerate(ranked)}
        for name in histories:
            points[name].append(totals.get(name))
            position[name].append(rank_by_name.get(name))
    series = [
        {"name": name, "mine": name == my_name,
         "points": points[name], "position": position[name]}
        for name in histories
    ]
    return {"gws": gws, "managers": len(histories), "series": series}


def league_position_card(data):
    """Position and total points across the season, one line per manager -
    the line chart the league table itself can only show one frame of."""
    if not data or len(data["series"]) < 2:
        return ""
    legend = "".join(
        '<li class="lpleg{mine}" data-i="{i}" tabindex="0">'
        '<span class="lpswatch" data-i="{i}"></span>{name}</li>'.format(
            mine=" lp-mine" if s["mine"] else "", i=i, name=e(s["name"]))
        for i, s in enumerate(data["series"])
    )
    return (
        '<section class="card"><div class="card-head">'
        f'<h2>League position over time{components.info_btn()}</h2>'
        '<span class="sub" hidden>Every manager\'s rank in this league, gameweek '
        'by gameweek - 1st at the top. Toggle to total points instead.</span></div>'
        '<div class="card-body">'
        '<div class="lptoggle" role="group" aria-label="Y axis">'
        '<button class="lpbtn" data-y="position" aria-pressed="true">Position</button>'
        '<button class="lpbtn" data-y="points" aria-pressed="false">Points</button>'
        "</div>"
        '<div class="scroll"><svg class="lpchart" viewBox="0 0 1040 460" '
        'role="img" aria-label="League position over time"></svg></div>'
        f'<ul class="lplegend">{legend}</ul>'
        f'<script type="application/json" class="lpchart-data">{json.dumps(data)}</script>'
        "</div></section>"
    )


def league_table(rows, squads, ctx, me):
    maxx = max(
        [analysis.squad_underlying(p, ctx)["xgi"] for p in squads.values()] + [0.01]
    )
    # This gameweek's high and low score, and each row's movement since last
    # week - nuggets the raw numbers already carry but the table never
    # pointed at. Skipped when everyone's level, which is common in GW1.
    gw_scores = [r["event_total"] for r in rows]
    best_gw, worst_gw = max(gw_scores), min(gw_scores)
    show_gw_tags = best_gw != worst_gw
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
        move = (r["last_rank"] - r["rank"]) if r.get("last_rank") else None
        if move is None:
            move_html = ""
        elif move > 0:
            move_html = (f' <span class="delta delta-up" '
                         f'title="Up {move} since last gameweek">{move}</span>')
        elif move < 0:
            move_html = (f' <span class="delta delta-down" '
                         f'title="Down {abs(move)} since last gameweek">{abs(move)}</span>')
        else:
            move_html = (' <span class="delta delta-flat" '
                         'title="Unchanged since last gameweek">-</span>')
        gw_tag = ""
        if show_gw_tags and r["event_total"] == best_gw:
            gw_tag = ' <span class="good-pill" title="Highest score this gameweek">Top</span>'
        elif show_gw_tags and r["event_total"] == worst_gw:
            gw_tag = ' <span class="bad-pill" title="Lowest score this gameweek">Low</span>'
        body.append(
            f"<tr{cls}>"
            f'<td class="num" data-v="{r["rank"]}">{r["rank"]}{move_html}</td>'
            f'<td><b>{e(r["entry_name"])}</b></td>'
            f'<td>{e(r["player_name"])}</td>'
            f'<td class="num" data-v="{r["event_total"]}">{r["event_total"]}{gw_tag}</td>'
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

    # Same "this gameweek's decisions" moment as captain picks above, the
    # other place a decision this week actually cost points - who left the
    # most on the bench, from the entry histories already fetched for the
    # league table and chips table, so no extra requests.
    bench = sorted(
        ((name, p.get("entry_history", {}).get("points_on_bench", 0))
         for name, p in by_name.items()),
        key=lambda kv: -kv[1],
    )
    bench = [kv for kv in bench if kv[1] > 0][:5]
    if bench:
        items = [f"{name} - {pts} point{'s' if pts != 1 else ''} benched"
                 for name, pts in bench]
        blocks.append(analysis._finding("b", "Points left on the bench", "warn", items))

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

    # A score with no average beside it, and a rank with no direction, are
    # both half a fact. Both go in as delta chips - the same component the
    # rest of the page uses - deliberately smaller than the figure they
    # qualify, so the tile still reads as one number at a glance.
    # The average belongs beside the score as a number, not as a difference
    # from it - "89 against a 79 average" is a comparison anyone makes
    # instantly, where "10 v avg" made them do the arithmetic backwards to
    # find out what the average even was.
    avg = d.get("gw_average")
    gw_note = f"GW{d['gw']} &middot; {avg} average" if avg else f"GW{d['gw']}"

    move = d.get("rank_move")
    rank_chip = ""
    if move:
        # Positive means the rank number fell, which is a climb.
        rank_chip = (f'<span class="delta delta-{"up" if move > 0 else "down"}">'
                     f'{compact_rank(move)}</span>')
    lg_move = d.get("league_move")
    lg_chip = ""
    if lg_move:
        lg_chip = (f'<span class="delta delta-{"up" if lg_move > 0 else "down"}">'
                   f'{abs(lg_move)}</span>')

    # Two of the six tiles get a tone - not all of them, since a hero row
    # in six different colours would just be noise. These are the two
    # where the number alone already answers "good or bad", so the colour
    # repeats a judgement the reader is about to make anyway rather than
    # asserting a new one: the gameweek score against the average sitting
    # right beside it, and whether anything actually needs the manager's
    # attention this week.
    gw_pts = eh.get("points")
    gw_tone = ""
    if isinstance(gw_pts, (int, float)) and avg:
        gw_tone = "tile-good" if gw_pts >= avg else "tile-bad"
    attn_tone = "tile-warn" if attention else "tile-good"

    tiles = [
        ("Gameweek", eh.get("points", "-"), gw_note, "", gw_tone),
        ("Total", eh.get("total_points", "-"),
         f"{d['overall_rank']:,} overall" if d.get("overall_rank") else "points",
         rank_chip, ""),
        ("League", f"{d['my_rank']}/{d['league_size']}" if d["my_rank"] else "-",
         e(d["league_name"]), lg_chip, ""),
        ("Projected", f"{projected:.1f}" if projected else "-",
         f"your XI, GW{d['next_gw']}", "", ""),
        ("Needs a look", len(attention),
         ", ".join(attention[:2]) + ("&hellip;" if len(attention) > 2 else "")
         if attention else "nobody flagged", "", attn_tone),
        ("In the bank", f"{eh.get('bank', 0) / 10:.1f}m",
         f"squad {eh.get('value', 0) / 10:.1f}m", "", ""),
    ]
    tile_html = "".join(
        f'<div class="tile {tone}"><div class="k">{e(k)}</div>'
        f'<div class="v tnum">{e(v)}{chip}</div><div class="n">{n}</div></div>'
        for k, v, n, chip, tone in tiles
    )
    # Two one-liners, one for each direction the page can be read in. The
    # Pick team view swaps them; see the .pkview handler.
    verdict = d.get("verdict") or ""
    ahead = d.get("next_line") or ""
    verdict_html = (
        (f'<p class="hero-line" data-pkview="back">{verdict}</p>'
         if verdict else "")
        + (f'<p class="hero-line" data-pkview="pk" hidden>{ahead}</p>'
           if ahead else "")
    )

    body = f"""
<header class="topbar"><div class="topbar-in">
  <span class="wordmark"><span class="dot"></span>FPL Insights</span>
  <span class="gw-chip">Gameweek {d['gw']}</span>
  <span class="stamp">{e(d['generated'])}</span>
</div>
<div class="railwrap" hidden><nav class="rail" aria-label="Sections on this tab"></nav></div>
</header>

<div class="wrap">
  <section class="hero">
    <h1>{e(title)}</h1>
    <div class="mgr">{e(d['manager'])} &middot; {e(d['league_name'])}</div>
    {verdict_html}
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
        <span class="sub" data-pkview="ov">Season points, points per game and season xGI on each card - click one to bring it forward. Faded crest = did not play. Green dot = predicted to start, red = not in the predicted eleven.</span>
        <span class="sub" data-pkview="gw" hidden>This gameweek's points on each card, with points per game and season xGI beside them. Faded crest = did not play.</span>
        <span class="sub" data-pkview="pk" hidden>Next fixture and a read on recent form on each card, shaded by clean-sheet odds for keepers and defenders and by expected goals for everyone else.</span>
      </div>
      <div class="pkview" role="tablist" aria-label="Pitch view">
        <button class="pkbtn" role="tab" aria-selected="true" data-view="ov">Overview</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="pk">Pick team</button>
        <button class="pkbtn" role="tab" aria-selected="false" data-view="gw">Gameweek {d['gw']}</button>
        <div class="statsel" role="group" aria-label="Bring a figure forward">
          <button class="stbtn" data-stat="p" aria-pressed="true">points</button>
          <button class="stbtn" data-stat="g" aria-pressed="false">per game</button>
          <button class="stbtn" data-stat="x" aria-pressed="false">xGI</button>
        </div>
        <button class="epbtn" aria-pressed="false" hidden>predicted points</button>
      </div>
      <div class="pkpanel" data-view="ov">{d['pitch']}</div>
      <div class="pkpanel" data-view="pk" hidden>{d['pick_pitch']}</div>
    </section>
    <details class="card collapsible">
      <summary class="card-head"><h2>Squad detail{components.info_btn()}</h2>
        <span class="sub" hidden>Click a column heading to sort. Next 3 fixtures coloured by difficulty.</span>
      </summary>
      {d['squad_table']}
    </details>
    <div class="chapter"><h2>What the numbers say</h2>
      <span class="sub">Nine readings of the same fifteen players.</span></div>
    <section>{d['findings']}</section>
  </div>

  <div class="panel" id="p-market" role="tabpanel" hidden>
    <div class="chapter"><h2>This week</h2>
      <span class="sub">What the fixtures are priced at, and what you missed.</span></div>
    {d['market']}
    {d['best_xi']}
    {d['kneejerk']}

    <div class="chapter"><h2>Your moves</h2>
      <span class="sub">Who to sell, who to buy, and who takes the armband.</span></div>
    {d['verdicts']}
    {d['transfers']}
    {d['pairings']}
    {d['captaincy']}

    <div class="chapter"><h2>Chips and the weeks ahead</h2>
      <span class="sub">Where the fixtures turn, and which chip that is worth.</span></div>
    {d['chip_planner']}
    {d['ticker']}
    {d['fixture_runs']}

    <div class="chapter"><h2>The wider market</h2>
      <span class="sub">Everyone else's squad, and what it is doing to prices.</span></div>
    {d['leaders']}
    {d['price_watch']}
    {d['scatter']}
    {d['elite']}
  </div>

  <div class="panel" id="p-league" role="tabpanel" hidden>
    <section class="card">
      <div class="card-head"><h2>{e(d['league_name'])}{components.info_btn()}</h2>
        <span class="sub" hidden>XI xGI is each starter's expected goal involvement per 90, damped down
        for anyone with still little football behind them, summed across the eleven that started - not a
        season total, which measures minutes played more than quality. A big score beside a small xGI
        came from somewhere that will not repeat.</span>
      </div>
      {d['league_table']}
    </section>
    {d['position_chart']}

    <div class="chapter"><h2>What the league owns</h2>
      <span class="sub">The squad everyone converges on, and where you leave it.</span></div>
    {d['template']}
    {d['carousel']}
    {d['differentials']}
    {d['watchlist']}

    <div class="chapter"><h2>How they are playing it</h2>
      <span class="sub">Who is scoring against you, and how the eight of you differ.</span></div>
    {d['rivals']}
    <section>{d['ownership']}</section>
    <section class="card">
      <div class="card-head"><h2>Chips used{components.info_btn()}</h2>
        <span class="sub" hidden>Two of each per season - one before GW20, one after.</span>
      </div>
      {d['chips']}
    </section>
  </div>



  {d['dialog']}
  <p class="foot">Built from the public Fantasy Premier League API &middot;
  expected goals are Opta's, as used by FPL &middot; {e(d['generated'])}</p>
</div>
"""
    # Archivo is requested across its width axis as well as its weight axis -
    # the expanded headings are the point, and asking only for weights would
    # silently render them at normal width.
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        "family=Archivo:wdth,wght@62..125,400..700&"
        "family=IBM+Plex+Mono:wght@400;500;600&display=swap\">"
    )
    head = f"<title>{e(title)}</title>{fonts}<style>{CSS}</style>"
    page = (
        f"{head}{body}<script>{JS}</script><script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script><script>{CAPTAINCY_JS}</script>"
        f"<script>{LEAGUECHART_JS}</script><script>{TICKER_JS}</script>"
    )
    if not standalone:
        return page
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{head}</head><body>{body}<script>{JS}</script>"
        f"<script>{SCATTER_JS}</script>"
        f"<script>{PLAYERVIEW_JS}</script>"
        f"<script>{CAPTAINCY_JS}</script>"
        f"<script>{LEAGUECHART_JS}</script>"
        f"<script>{TICKER_JS}</script></body></html>"
    )


PRICE_HISTORY_PATH = Path(__file__).with_name("price_history.json")
PRICE_HISTORY_DAYS = 8


def _update_price_history(ctx):
    """Record today's prices and return each player's change over the window.

    FPL's API only ever gives the change since the season started
    (cost_change_start) or since today's single recalculation
    (cost_change_event) - there is no "this week" field to read, so the
    Price movement card needs its own memory of what prices were a few days
    ago. One snapshot per calendar day, trimmed to the last
    PRICE_HISTORY_DAYS and committed to the repo alongside the built
    artifact (see build.yml), the same way the artifact itself persists
    between runs. Until this has run daily for about a week, the oldest
    snapshot for a newly-tracked player is today's, so the reported change
    is 0 - a real gap, not a bug, that closes itself within a week of
    shipping this.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        hist = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hist = {}
    for pid, el in ctx.players.items():
        key = str(pid)
        entries = hist.get(key) or []
        if entries and entries[-1][0] == today:
            entries[-1][1] = el["now_cost"]
        else:
            entries.append([today, el["now_cost"]])
        hist[key] = entries[-PRICE_HISTORY_DAYS:]
    try:
        PRICE_HISTORY_PATH.write_text(json.dumps(hist, separators=(",", ":")),
                                       encoding="utf-8")
    except OSError as ex:
        print(f"[price history] could not save: {ex}")
    weekly = {}
    for pid, el in ctx.players.items():
        entries = hist.get(str(pid)) or []
        baseline = entries[0][1] if entries else el["now_cost"]
        weekly[pid] = (el["now_cost"] - baseline) / 10.0
    return weekly


def build(entry_id, league_id, ttl=fplapi.DEFAULT_TTL, gw=None, limit=25,
          elite_depth=elite.PROVEN_POOL_SIZE):
    """Gather everything the page needs."""
    ctx = analysis.Ctx.load(ttl=ttl)
    gw = gw or ctx.last_event_with_picks()
    weekly_price = _update_price_history(ctx)

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
    eps_by_id = {r.element["id"]: ep for r, ep in eps}
    cap_matrix = captaincy.matrix(ctx, xi, eps_by_id)

    elite_res = None
    if elite_depth:
        try:
            elite_res = elite.compare(ctx, squad_ids, depth=elite_depth, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[elite] skipped: {ex}")

    # --- the week's verdict ------------------------------------------------
    ev_now = next((x for x in ctx.events if x["id"] == gw), None)
    gw_average = (ev_now or {}).get("average_entry_score") or None
    rank_move = None
    try:
        hist = fplapi.entry_history(entry_id, ttl=ttl).get("current", [])
        by_ev = {h["event"]: h for h in hist}
        now_r = (by_ev.get(gw) or {}).get("overall_rank")
        prev_r = (by_ev.get(gw - 1) or {}).get("overall_rank")
        if now_r and prev_r:
            rank_move = prev_r - now_r   # positive is a climb
    except fplapi.FplError as ex:
        print(f"[hero] rank movement unavailable: {ex}")

    # Anyone in the XI whose club has not played this gameweek yet. Drives
    # whether the verdict looks forward or back.
    pending = []
    for r in xi:
        fx = [x for x in ctx.fixtures
              if x.get("event") == gw and r.element["team"] in (x["team_h"], x["team_a"])]
        if fx and not ctx._is_played(fx[0]):
            pending.append(r.name)
    verdict = week_verdict(
        ctx, gw, set(xi_ids + bench_ids), cap,
        picks.get("entry_history", {}).get("points"), gw_average, pending,
    )

    bank = (picks.get("entry_history", {}).get("bank") or 0) / 10.0
    free_ts = analysis.free_transfers(entry_id, next_gw, ttl=ttl)
    pair_hit = analysis.transfer_cost(2, free_ts)
    print(f"[transfers] {free_ts if free_ts is not None else '?'} free, "
          f"a pair costs {pair_hit}")
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
        bank=bank, limit=4, elite=elite_res, hit_cost=pair_hit,
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
    # The handful of rival-owned scorers the card below actually shows, so
    # this is a few extra portrait requests rather than one per player in
    # the league.
    rivals_rows = rival_returns(own, by_name, ctx, my_name, set(squad_ids))
    RIVALS_WINDOW_WEEKS = 3
    rivals_window_rows = rival_returns_window(
        rows, ctx, my_name, set(squad_ids), gw,
        weeks=RIVALS_WINDOW_WEEKS, ttl=ttl)
    for row in rivals_rows + rivals_window_rows:
        league_photos.setdefault(row["id"], fplapi.photo_data_uri(
            ctx.players[row["id"]]["photo"]))

    watchlist_rows = []
    if own and proj:
        watchlist_rows = differential_watchlist(
            own, ctx, proj, market, baselines, next_gw, squad_ids)
        for row in watchlist_rows:
            league_photos.setdefault(row["id"], fplapi.photo_data_uri(
                ctx.players[row["id"]]["photo"]))

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
        fh = chips.free_hit(ctx, xi, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        tc = chips.triple_captain(ctx, xi, proj, market, baselines, next_gw)
        bb = chips.bench_boost(ctx, bench, proj, market, baselines, next_gw,
                               bank=bank_m)
        wc = chips.wildcard(ctx, xi + bench, proj, market, baselines, next_gw,
                            budget=total_sell + bank_m)
        try:
            used = chips.used_chips_this_half(entry_id, next_gw, ttl=ttl)
        except fplapi.FplError as ex:
            print(f"[chips] chip history unavailable: {ex}")

    # One scoring pass over the whole league, shared by the knee-jerk card
    # and the Buy/Sell/Keep/Avoid board so the two cannot disagree with
    # each other about the same player.
    lg_scores = transfers.league_scores(ctx, proj, next_gw, market, baselines)
    kj = transfers.kneejerk(ctx, xi + bench, lg_scores, bank=bank)
    vb = transfers.verdict_board(ctx, xi + bench, lg_scores, bank=bank)

    # The knee-jerk card states in prose that a pair reaches him, but
    # "Suggested pairs" runs its own separate top-gain search and has no
    # reason to have found this specific pairing on its own - the knee-jerk
    # target is a one-week impulse buy, not necessarily one of the best
    # multi-week upgrades in the pool. Built here, once the funder_pair
    # search above has already done the actual sell/buy legwork, and
    # dropped into the same list of cards so "how would I actually get
    # him" has a real answer to look at rather than only a sentence.
    fp = kj.get("funder_pair") if kj else None
    if fp and kj.get("ep") is not None:
        target_el = ctx.players[kj["id"]]
        repl_el = fp["replacement"]
        primary, second = fp["primary"], fp["second"]
        already_shown = any(
            {primary.element["id"], second.element["id"]}
            == {leg["out"].element["id"] for leg in p["legs"]}
            for p in pairings
        )
        if not already_shown:
            primary_gain = kj["ep"] - lg_scores.get(
                primary.element["id"], {}).get("total", 0.0)
            second_gain = fp["replacement_score"]["total"] - lg_scores.get(
                second.element["id"], {}).get("total", 0.0)
            spend = (
                (target_el["now_cost"] + repl_el["now_cost"]) / 10.0
                - primary.price - second.price
            )
            pairings.append({
                "tag": f"Reaches the knee-jerk pick, {target_el['web_name']}",
                "legs": [
                    {"out": primary, "in": target_el, "gain": primary_gain,
                     "out_photo": photos.get(primary.element["id"]),
                     "in_photo": fplapi.photo_data_uri(target_el["photo"]),
                     "out_shirt": shirts.get(
                         (primary.element["team"], primary.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (target_el["team"], ctx.pos(target_el) == "GKP"))},
                    {"out": second, "in": repl_el, "gain": second_gain,
                     "out_photo": photos.get(second.element["id"]),
                     "in_photo": fplapi.photo_data_uri(repl_el["photo"]),
                     "out_shirt": shirts.get(
                         (second.element["team"], second.pos == "GKP")),
                     "in_shirt": shirts.get(
                         (repl_el["team"], ctx.pos(repl_el) == "GKP"))},
                ],
                "gain": primary_gain + second_gain,
                "bank_after": bank - spend,
            })
    # A genuinely different question from Free Hit's budget-capped "ideal" -
    # see chips.literal_best_xi for why reusing that number here was wrong.
    next_ideal = chips.literal_best_xi(ctx, xi, proj, market, baselines, next_gw)

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
        # Standings carry last week's position, so the mini-league gets the
        # same movement arrow the overall rank has. Positive is a climb, to
        # match rank_move - both are "places gained", not "rank delta".
        "league_move": (
            (my_row["last_rank"] - my_row["rank"])
            if my_row and my_row.get("last_rank") else None
        ),
        "my_xgi": my_xgi,
        "xgi_note": xgi_note,
        "pitch": pitch(xi, bench, ctx, badges, shirts, cap, vice, gw=gw),
        "pick_pitch": pick_team_pitch(xi, bench, ctx, badges, shirts, cap,
                                      vice, proj, market, next_gw, eps),
        "chip_planner": chip_planner_card(fh, tc, bb, wc, used, xi, bench,
                                          ctx, badges, shirts, proj, market,
                                          next_gw),
        "best_xi": best_xi_card(next_ideal, ctx, set(squad_ids), next_gw),
        "kneejerk": kneejerk_card(kj, gw),
        "verdicts": verdict_board_card(vb, next_gw),
        "captaincy": captaincy_card(cap_matrix),
        "squad_table": squad_table(xi + bench, ctx, cap, vice,
                                   proj, market, next_gw),
        "ticker": ticker.fixture_ticker(xi + bench, ctx, proj, next_gw,
                                        market=market),
        "fixture_runs": ticker.fixture_run_summary(xi + bench, ctx, proj,
                                                    market, next_gw, weeks=6),
        "market": ticker.odds_insights(market_fixtures, xi, ctx, proj, next_gw),
        "pairings": components.pairing_cards(
            pairings,
            "Two out, two in - moves a single transfer cannot reach, because "
            "one sale funds the other and two sales from a club free a slot. "
            "Same shape, within budget, three per club respected. "
            + (f"You have {free_ts} free transfer{'s' if free_ts != 1 else ''}, "
               f"so this pair costs {pair_hit}."
               if free_ts is not None else
               "Free-transfer count unavailable, so a pair is priced at 4."),
            hit=pair_hit),
        "leaders": components.stat_leaders(leader_groups(ctx, squad_ids)),
        "transfers": components.transfer_cards(
            swaps,
            f"Same position, affordable on {bank:.1f}m in the bank, ranked by "
            f"projected gain over the next {transfers.TRANSFER_HORIZON_WEEKS} "
            f"gameweeks (plus a small form/xGI nudge). Selling price is taken as "
            f"current price - read these as prompts, not instructions."),
        "dialog": player_dialog([
            player_payload(r, ctx, proj, ep, next_gw, photos) for r, ep in eps
        ] + [
            player_payload(r, ctx, proj, None, next_gw, photos)
            for r in xi + bench if not any(r is q for q, _ in eps)
        ]),
        "findings": findings_section(
            analysis.build_findings(list(reports.values()), ctx),
            list(reports.values()), ctx, proj, market, next_gw,
            weekly_price=weekly_price,
            xi_ids={r.element["id"] for r in xi}),
        "price_watch": price_watch_card(pw),
        "scatter": scatter(scatter_pts),
        "league_table": league_table(rows, squads, ctx, entry_id) if rows else "",
        "position_chart": league_position_card(
            league_position_series(histories, my_name)),
        "ownership": ownership_cards(own, by_name, ctx, my_name) if own else "",
        "carousel": ownership_carousel(own, by_name, ctx, my_name) if own else "",
        "template": template_pitch(tpl, ctx, shirts, my_name, set(squad_ids)),
        "differentials": differential_card(own, by_name, ctx, my_name, league_photos),
        "watchlist": differential_watchlist_card(
            watchlist_rows, league_photos, transfers.TRANSFER_HORIZON_WEEKS),
        "rivals": rivals_card(rivals_rows, rivals_window_rows,
                              max(0, len(by_name) - 1), league_photos,
                              weeks=RIVALS_WINDOW_WEEKS),
        "elite": elite_card(elite_res, ctx),
        "chips": chips_table(histories) if histories else "",
        "next_gw": next_gw,
        "overall_rank": meta.get("summary_overall_rank"),
        "gw_average": gw_average,
        "rank_move": rank_move,
        "verdict": verdict,
        "next_line": next_week_line(ctx, xi, eps, next_gw),
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
