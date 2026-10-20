"""A next-week team from a verified owned squad or its recommended moves."""

import squadbuilder


def _pool(reports, scores):
    return [{"id": r.element["id"], "pos": r.pos, "club": r.element["team"],
             "price": r.price, "value": scores.get(r.element["id"], {}).get("total", 0)}
            for r in reports]


def select(reports, scores, blank_ids=()):
    if any(r.element["id"] not in scores and r.element["id"] not in blank_ids
           for r in reports):
        return None
    selected = squadbuilder.owned_xi(_pool(reports, scores))
    if not selected or selected["value"] <= 0:
        return None
    by_id = {r.element["id"]: r for r in reports}
    ranked = sorted(selected["xi"], key=lambda p: -p["value"])
    bench = sorted(selected["bench"], key=lambda p: (p["pos"] != "GKP", -p["value"]))
    return {"xi": [by_id[p["id"]] for p in selected["xi"]],
            "bench": [by_id[p["id"]] for p in bench],
            "captain": ranked[0]["id"], "vice": ranked[1]["id"],
            "value": selected["value"], "formation": selected["formation"]}


def apply_transfers(reports, incoming, moves, bank, selling):
    if not moves or selling is None or bank is None:
        return None
    owned = {r.element["id"]: r for r in reports}
    additions = {r.element["id"]: r for r in incoming}
    outs = [m["out"].element["id"] for m in moves]
    ins = [m["in"]["id"] for m in moves]
    if (len(set(outs)) != len(outs) or len(set(ins)) != len(ins)
            or any(pid not in owned or pid not in selling for pid in outs)
            or any(pid not in additions or pid in owned for pid in ins)
            or any(owned[old].pos != additions[new].pos for old, new in zip(outs, ins))):
        return None
    if sum(additions[pid].element["now_cost"] / 10 for pid in ins) > bank + sum(selling[pid] for pid in outs) + 1e-9:
        return None
    changed = [r for r in reports if r.element["id"] not in outs] + [additions[pid] for pid in ins]
    return changed if squadbuilder.owned_xi(_pool(changed, {})) else None
