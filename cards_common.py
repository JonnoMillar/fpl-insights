"""Small HTML helpers and palette constants shared by every tab's cards."""

import html
import json


def e(x):
    return html.escape(str(x), quote=True)


def icon(name, cls=""):
    """One of the generated icons (assets/icons.css), decorative: the label
    beside it, or the control's own accessible name, carries the meaning."""
    return f'<span class="ico ico-{name}{" " + cls if cls else ""}" aria-hidden="true"></span>'


# The goal-and-bars mark (docs/brand-handoff/logo, still a draft geometry).
LOGO_SVG = ('<svg viewBox="0 0 100 62" fill="currentColor" aria-hidden="true">'
            '<path d="M0 62V0H100V62H90V10H10V62Z"/>'
            '<path d="M16.5 40H34.5V62H16.5ZM41 32H59V62H41ZM65.5 20H83.5V62H65.5Z"/></svg>')


def script_json(value):
    """Escape the HTML boundary as well as JSON syntax."""
    return json.dumps(value).replace("<", "\\u003c")


# Same five-step purple ramp and the same split used in the player-detail
# dialog's own fixture strip (playerview.js: csTone/xgTone) - a goalkeeper's
# or defender's points hinge on keeping the ball out, a midfielder's or
# forward's on their side scoring, so each is shaded by the stat that
# actually decides it. Kept as one scale in two places rather than derived,
# so a fixture reads the same color wherever a player appears on the page.
CS_TONE = [(45, "#16001a", "#fff"), (36, "#37003c", "#fff"),
          (28, "#6e6474", "#fff"), (20, "#d3cdd6", "#16001a")]
XG_TONE = [(1.9, "#16001a", "#fff"), (1.6, "#37003c", "#fff"),
          (1.3, "#6e6474", "#fff"), (1.0, "#d3cdd6", "#16001a")]
TONE_FALLBACK = ("#eeecef", "#16001a")


def _step_tone(value, steps):
    for edge, bg, fg in steps:
        if value >= edge:
            return bg, fg
    return TONE_FALLBACK


def pos_fixture_pill(pos, opp, home, cs, xg):
    if opp is None:
        return '<span class="fxpill">Unavailable</span>'
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


def meter(value, vmax, label):
    """A single-series magnitude bar. One hue, sequential - no legend needed,
    and the number is always printed beside it so the bar is never the only
    way to read the value."""
    pct = max(0.0, min(100.0, (value / vmax * 100) if vmax else 0))
    return (
        f'<span class="meter" title="{e(label)}">'
        f'<span class="meter-fill" style="width:{pct:.1f}%"></span></span>'
    )
