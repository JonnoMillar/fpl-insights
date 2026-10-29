# Managed FPL account

This directory is separate from the dashboard product, its configured manager,
its mini-league and the existing `research/` audit. Nothing here publishes the
site, changes `config.json`, or operates the other account's alert bot.

Preparation and decisions are kept here so a new Codex chat can resume safely.
Read `HANDOFF.md`, `strategy.md`, `rules.md`, and the latest decision before acting.
The signed-in FPL account is authoritative for current holdings and allowances;
the dashboard's public picks are not an authenticated account record.

`prepare.py` is a **read-only** research command. It reuses the existing models
with its own ignored cache, checks fixture coverage, compares legal initial
squads and writes `.cache/preparation.json`. It has no account credentials or write API.
Run from the repository root:

```powershell
python account-management/prepare.py --self-check
python account-management/prepare.py
python account-management/prepare.py --ttl 0  # refresh current inputs
```

The comparison uses heuristic seeds, not an exact global optimiser, calibrated
probabilities or proof of future performance. Its chosen squad needs a dated
news/role review before entry. An input retrieval time is not its publication time.

No password, cookie, token, personal login response or private account export
belongs in committed files. `private/` is ignored, but is not a credential vault.
Use the normal signed-in browser; do not copy another project's saved credentials.
