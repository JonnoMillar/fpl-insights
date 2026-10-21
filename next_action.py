"""A concise decision for the hero, read off the transfer plan."""


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


def _names(week):
    return "; ".join(f"{m['out_name']} → {m['in_name']}" for m in week["moves"])


def choose(plan, free, supported, next_gw, chip_options=(), used=None):
    """The plan's first week, said plainly - not a second opinion on it.

    The plan already weighs timing, hits, margins, squad structure, Bench
    Boost and Triple Captain against each other across several weeks, so
    the hero repeats its first week rather than re-ranking moves on a
    different rule. Free Hit is the one chip it does not plan: that is still
    promoted only when it is known to be unused and its own planner is
    strongly in favour of this week.
    """
    if next_gw > 38:
        return dict(label="Season complete", detail="No upcoming gameweek.", target=None)
    if not supported or free is None or not plan:
        return dict(label="Check before making a move", target="action-method",
                    detail="Advice unavailable: projections, selling prices or free-transfer count could not be verified.")
    week = plan["weeks"][0]
    span = f"GW{plan['start_gw']}–{plan['end_gw']}"
    if week["moves"]:
        n = len(week["moves"])
        hit = f" (−{week['hits'] * 4})" if week["hits"] else ""
        action = dict(label=f"Make {n} transfer{'s' if n != 1 else ''}{hit}",
                      target=f"plan-gw-{week['gw']}",
                      detail=f"{_names(week)} · {week['gain']:+.1f} projected points over {span}"
                             f"{' after the hit' if week['hits'] else ''}.")
    else:
        later = next((w for w in plan["weeks"][1:plan["show_weeks"]] if w["moves"]), None)
        label = (f"Roll {free} free transfer{'s' if free != 1 else ''}" if free
                 else "Hold your squad")
        if free >= 5:
            label = "No transfer this week"
        detail = (f"Next planned move: GW{later['gw']}, {_names(later)}." if later else
                  f"No move clears the margins in the next {plan['show_weeks']} gameweeks.")
        if free >= 5:
            detail += " You are at the five-transfer cap, so this week's allowance is not banked."
        action = dict(label=label, detail=detail,
                      target=f"plan-gw-{later['gw']}" if later else "transfer-plan")
    if week["chip"]:
        name = {"bboost": "Bench Boost", "3xc": "Triple Captain"}[week["chip"]]
        action = dict(label=f"Play {name}" + (f", {action['label'].lower()}" if week["moves"] else ""),
                      target=f"plan-gw-{week['gw']}",
                      detail=(action["detail"] if week["moves"] else
                              f"The plan's best week for it in {span} and beyond.")
                      + " Review the chip case before playing it.")
    strong = [(key, name, row) for key, name, row in chip_options
              if key == "freehit" and used is not None and not used.get(key) and row
              and row.get("gw") == next_gw and row.get("confidence") == "strong"
              and row.get("gap", 0) > 0]
    if strong and not week["chip"]:
        key, name, row = strong[0]
        action = dict(label=f"Play {name}", target=f"chip-{key}", chip=key,
                      detail=f"GW{next_gw} has a clear edge within the modelled single-fixture window. Review the chip case before playing it.")
    if action.get("chip") != "freehit":
        action.update(moves=week["moves"], chip=week["chip"])
        if week["moves"]:
            action.update(projected_gain=week["gain"],
                          horizon=plan["end_gw"] - plan["start_gw"] + 1)
    return action
