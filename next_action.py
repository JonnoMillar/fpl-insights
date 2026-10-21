"""A concise decision from the existing, guarded recommendation outputs."""

import analysis


def explain_move(move, ctx, next_gw):
    """A short factual case, including caveats; no new recommendation policy."""
    incoming, outgoing = move["in"], move["out"].element
    name, old_name = incoming["web_name"], outgoing["web_name"]
    minutes = incoming.get("minutes", 0) or 0
    old_minutes = outgoing.get("minutes", 0) or 0
    rate = analysis.f(incoming.get("expected_goal_involvements_per_90"))
    old_rate = analysis.f(outgoing.get("expected_goal_involvements_per_90"))
    form, old_form = incoming.get("form"), outgoing.get("form")
    fixtures = ctx.next_fixtures(incoming["team"], 5, from_event=next_gw)
    if minutes >= 90 and rate >= old_rate + .1:
        reason = f"{name}'s chance numbers look promising: {rate:.2f} expected goal involvements per 90"
        reason += (f", but that's only {minutes} minutes of evidence." if minutes < analysis.THIN_SAMPLE_MINUTES
                   else f", against {old_name}'s {old_rate:.2f}." if old_minutes >= analysis.THIN_SAMPLE_MINUTES and outgoing.get("expected_goal_involvements_per_90") is not None
                   else f" across {minutes} minutes.")
    elif form is not None and old_form is not None and analysis.f(form) >= analysis.f(old_form) + 1:
        reason = (f"{name} has been returning more FPL points recently "
                  f"(form {analysis.f(form):.1f} versus {old_name}'s {analysis.f(old_form):.1f}).")
    elif minutes >= old_minutes + 180 and old_minutes < analysis.THIN_SAMPLE_MINUTES:
        reason = f"{name} has played {minutes} minutes this season; {old_name} has managed only {old_minutes}, so there's more playing-time evidence to work with."
    elif fixtures:
        easy = sum(fx[2] <= 2 for fx in fixtures)
        reason = (f"{name} has {easy} of his next {len(fixtures)} fixtures rated 2 or easier out of 5."
                  if easy else f"None of {name}'s next {len(fixtures)} fixtures are rated 2 or easier, so the run doesn't look especially soft.")
    else:
        reason = f"There isn't enough fixture or form evidence to give {name} a clear supporting case yet."
    caveats = []
    chance = incoming.get("chance_of_playing_next_round")
    if incoming.get("status") in ("i", "s", "u", "n"):
        caveats.append("check his availability before committing")
    elif incoming.get("status") == "d" or (chance is not None and chance < 100):
        caveats.append("he's currently flagged as a doubt")
    if fixtures:
        opp, home, difficulty, _ = fixtures[0]
        opponent = ctx.teams[opp].get("name", ctx.team_name(opp))
        fixture = f"{opponent} {'at home' if home else 'away'}"
        if difficulty >= 4:
            caveats.append(f"{fixture} is a tough start")
        elif difficulty <= 2:
            caveats.append(f"he starts with a kinder fixture against {opponent} {'at home' if home else 'away'}")
    if caveats:
        note = "; ".join(caveats)
        reason += " " + note[0].upper() + note[1:] + "."
    return reason


def choose(swaps, pairs, free, supported, next_gw, chip_options=(), used=None):
    """Conservative presentation policy, not a newly calibrated model.

    Prefer rolling unless net five-week gain exceeds two points; spending a
    second transfer must add another two. Chip timing is a separate signal:
    only promote a known-unused chip with a strong next-week recommendation.
    Never rank unlike chip/transfer horizons by their raw scores.
    """
    if next_gw > 38:
        return dict(label="Season complete", detail="No upcoming gameweek.", target=None)
    if not supported or free is None:
        return dict(label="Check before making a move", target="action-method",
                    detail="Advice unavailable: projections, selling prices or free-transfer count could not be verified.")
    singles = [(r["gain"] - analysis.transfer_cost(1, free), i, r)
               for i, r in enumerate(swaps)]
    doubles = [(r["gain"] - analysis.transfer_cost(2, free), i, r)
               for i, r in enumerate(pairs) if not r.get("tag")]
    single = max(singles, key=lambda x: x[0], default=None)
    pair = max(doubles, key=lambda x: x[0], default=None)
    action = dict(label=f"Roll {free} free transfer{'s' if free != 1 else ''}",
                  detail=("No modelled move clears the selection margins after hits. "
                          + ("You are at the five-transfer cap; another cannot be banked."
                             if free >= 5 else "Keep the flexibility for next week.")),
                  target="action-method")
    if free == 0:
        action["label"] = "Hold your squad"
    if single and single[0] > 2:
        gain, i, row = single
        action = dict(label="Make 1 transfer", target=f"transfer-{i}", moves=[row],
                      projected_gain=gain, horizon=5,
                      detail=f"{row['out'].name} → {row['in']['web_name']} · +{gain:.1f} projected XI points over 5 GW after hits.")
    if pair and pair[0] > max(2, (single[0] if single else 0) + 2):
        gain, i, row = pair
        names = "; ".join(f"{leg['out'].name} → {leg['in']['web_name']}" for leg in row["legs"])
        action = dict(label="Make 2 transfers", target=f"pair-{i}", moves=row["legs"],
                      projected_gain=gain, horizon=5,
                      detail=f"{names} · +{gain:.1f} projected XI points over 5 GW after hits.")
    # Confidence here is timing separation, not probability of success. If
    # several chips qualify, retain the transfer action and invite comparison.
    strong = [(key, name, row) for key, name, row in chip_options
              if used is not None and not used.get(key) and row
              and row.get("gw") == next_gw and row.get("confidence") == "strong"
              and (row.get("gap", row.get("ep", 0)) > 0)]
    if len(strong) == 1:
        key, name, row = strong[0]
        action = dict(label=f"Play {name}", target=f"chip-{key}", chip=key,
                      detail=f"GW{next_gw} has a clear edge within the modelled single-fixture window. Review the chip case before playing it.")
    return action
