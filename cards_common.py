"""Small HTML helpers and palette constants shared by every tab's cards."""

import html



TONE_COLOR = {
    "good": "var(--good)",
    "bad": "var(--bad)",
    "warn": "var(--attention)",
    "info": "var(--p60)",
    "neutral": "var(--p60)",
}


def e(x):
    return html.escape(str(x), quote=True)


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


def meter(value, vmax, label):
    """A single-series magnitude bar. One hue, sequential - no legend needed,
    and the number is always printed beside it so the bar is never the only
    way to read the value."""
    pct = max(0.0, min(100.0, (value / vmax * 100) if vmax else 0))
    return (
        f'<span class="meter" title="{e(label)}">'
        f'<span class="meter-fill" style="width:{pct:.1f}%"></span></span>'
    )
