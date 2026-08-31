---
name: project-check
description: Quick health check for the fpl-insights repo - git state, whether the GitHub Actions build is actually running on schedule, whether the Vercel deployment is fresh and still public, whether README's claims still match the code, and a lightweight scan for dead/orphaned code. Use this whenever the user asks to check the project is up to date, wants a status check before starting new work, asks "is everything running okay" / "is this still working" / "did the build run", or wants to verify setup and access are still correct after a break from the project. Also trigger proactively at the start of a session if it's been a while since the repo was last touched and the user's first ask concerns project state, deployment, or "where are we."
---

# Project check

A fast, scannable audit of the things that go wrong silently on this
project - not a deep code review. This exists because exactly this kind
of drift already happened once: a documented publish routine quietly
stopped running with no error, and nobody noticed until the live page was
checked against the repo directly. Every check below targets a specific
way this project has actually gone stale or drifted, not a hypothetical.

Run every check. Report PASS/WARN/FAIL for each with one line of evidence,
even when everything is fine - a silent skip is exactly the failure mode
this skill exists to prevent. Keep the whole report under ~20 lines; this
is a status check, not an essay. Don't fix anything found here without
asking first, except trivial one-line doc corrections.

## 1. Git state

```bash
git status --short
git fetch origin
git log HEAD..origin/main --oneline   # behind
git log origin/main..HEAD --oneline   # ahead
```

- **FAIL** if there are uncommitted changes AND the branch is behind origin
  - a plain pull will conflict. Say what's uncommitted and whether it looks
  safe to discard (stale generated output) or needs a decision.
- **WARN** if behind origin with a clean tree (safe fast-forward, just do
  it and say so) or if there are uncommitted changes with nothing to pull.
- **PASS** if clean and up to date.

## 2. GitHub Actions build

```bash
gh run list --workflow=build.yml --limit 5
```

The build is scheduled every 3 hours (`.github/workflows/build.yml`).
- **FAIL** if the most recent run's conclusion isn't `success`, or the most
  recent run is more than ~4 hours old (one missed cycle is normal
  best-effort scheduling; two or more in a row is not).
- **PASS** otherwise. Note the last run's age and conclusion either way.

## 3. Vercel deployment

Load the Vercel MCP tools if not already available (`ToolSearch` with a
query like "vercel list_deployments" / "vercel get_project_deployment_protection").
Project: `fpl-insights`, team: `jonno-7251s-projects`. If the project or
team ID isn't already known this session, `list_teams` then `list_projects`
to find them rather than guessing - IDs can change if the project is ever
relinked.

- `list_deployments` for the project: latest deployment's `state` should be
  `READY` and its commit SHA should match `git rev-parse HEAD` (or be very
  close - a deploy started right after the latest push is fine, still
  building is fine, but a latest deployment several commits behind HEAD is
  not).
- `get_project_deployment_protection`: `passwordProtection.enabled` and
  `ssoProtection.enabled` should both be `false`. This is deliberate - the
  site is meant to be a plain public URL. If either is now `true`, that's
  a real change worth flagging, not assuming is fine.
- **FAIL** on a broken/stale deployment or unexpected protection change.
  **PASS** otherwise, and name the live URL.

## 4. Docs vs code

README.md makes specific, checkable claims. Spot-check them rather than
re-reading the whole file against the whole codebase:

- Tab names: `grep -n 'class="tab"' dashboard.py` should match the three
  tabs README's "The dashboard" section names (Squad, Planning,
  Mini-league) - if dashboard.py's tabs changed and README wasn't updated,
  or vice versa, that's the exact kind of drift this skill exists to catch.
- The live URL in README's "Access" section should match the production
  domain Vercel actually has assigned (check 3, above).
- "How it stays current" should describe what's actually true today - most
  importantly, it should NOT claim any separate scheduled publish step
  exists unless one genuinely does (verify with `scheduled-tasks` /
  `CronList` before trusting the claim either way, the same way this
  exact drift was caught once already).
- **FAIL** on any claim that's now factually wrong. **WARN** on something
  that's technically true but confusingly worded. **PASS** if the spot-
  checked claims hold.

## 5. Dead code scan (heuristic, not exhaustive)

The dashboard's data flows through one big dict literal, bounded by the
lines containing `"pitch": pitch(` (first key) and `"generated":` (last
key) in `dashboard.py`. The HTML template reads its keys as `d['key']`. A
key assigned in that dict but never read by the template is dead - this
already happened once (`match_logs`/`opta_table`, removed 2026-08-31).

```bash
sed -n '/"pitch": pitch(/,/"generated":/p' dashboard.py \
  | grep -oE '^\s*"[a-z_]+":' | tr -d '": ' | sort -u > /tmp/dict_keys.txt
grep -oE "d\['[a-z_]+'\]" dashboard.py | grep -oE "[a-z_]+" \
  | grep -v '^d$' | sort -u > /tmp/used_keys.txt
comm -23 /tmp/dict_keys.txt /tmp/used_keys.txt
```

Scoping to that one dict (rather than every `"key":` in the file) matters
- an earlier, unscoped version of this check flagged dozens of unrelated
dict keys from elsewhere in the file (JSON payloads read by
`playerview.js`, small label dicts) as false positives, which would have
trained the user to ignore this section entirely. Even scoped, expect the
occasional false positive from a key read via `d.get(...)` instead of
`d['...']` (e.g. `attention`, `projected_xi` are real, working keys that
this grep can't see) - confirm with a targeted `grep` for the specific key
before reporting anything as dead.

- **WARN** if a candidate survives that manual confirmation (name it,
  don't auto-fix). **PASS** if nothing does or every candidate turns out
  to be a `.get()` false positive.

## Report format

```
## Project check - <today's date>

1. Git state       [PASS/WARN/FAIL]  <one line>
2. GH Actions build [PASS/WARN/FAIL]  <one line>
3. Vercel deploy    [PASS/WARN/FAIL]  <one line>
4. Docs vs code     [PASS/WARN/FAIL]  <one line>
5. Dead code scan   [PASS/WARN/FAIL]  <one line>

<one-sentence overall verdict, and anything that needs the user's decision>
```
