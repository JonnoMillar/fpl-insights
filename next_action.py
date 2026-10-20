"""A concise decision from the existing, guarded recommendation outputs."""

import analysis


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
