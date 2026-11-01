**CURRENT DELIVERABLE — 1 November: [transparent generated icon suite](transparent-suite/README.md), with [working preview](transparent-suite/preview.html). Forty named CSS views use the actual transparent PNG artwork. Use this instead of the rejected vector redraws. Saves B is a working selection.**

**LATEST DECISION — 30 October: the code-drawn `vector-suite/` is REJECTED. Do not implement it or use the earlier `-vectors.zip` package. Return to generated artwork and the approved Goals/Assist composition reference. Image refinement is underway; no replacement suite is approved.**

# FPL Insights — brand and icon handoff

Prepared 29 October 2026 for Claude's dashboard redesign.

**Partial working handoff — not the finished delivery.**

30 October: the [vector suite](vector-suite/README.md) supplies 40 individual
SVGs, compact exports and actual-size checks. [Open the vector preview](vector-suite/preview.html).
The [concept sheets](concept-suite/README.md) record the visual direction;
the older `drafts/` proposals are superseded. Final user review, logo geometry,
logo exports and name lockups remain unfinished.

**The goal/chart is the approved logo direction. Its exact geometry is not final.**
This folder contains starting assets and decisions, not a finished identity or
an instruction to preserve the current dashboard layout.

## Decision status

| Item | Status | Guidance |
| --- | --- | --- |
| Product name | Fixed | FPL Insights. |
| Logo concept | Approved direction | Football goal frame with three ascending data bars. |
| Logo geometry | Draft | Proportions, frame/bar weight, gaps, corners, padding and small-size treatment still need review. |
| Navigation symbols | Provisionally accepted starting set | Shirt, route, trophy, magnifier. Use bold outline; shirt has no internal sleeve seams. |
| Sidebar and selected states | Open; Claude to design | Rail shape, width, layout, selection treatment, hover, focus and motion are not approved by these samples. |
| Wider dashboard | Separate design work | This package does not define every component or authorise publication. |

## Files

- `CLAUDE_BRIEF.md`: concise instructions to accompany the package.
- `logo/goal-chart-draft.svg`: editable monochrome draft, not final artwork.
- `icons/{squad,planning,mini-league,scout}.svg`: navigation starting assets.
- `references/dashboard-direction.png`: Jonno's supplied screenshot of the new dashboard, preserved unchanged. It shows the interface direction, not the new logo.
- `preview.html` and `preview.png`: asset-only reference sheet. No proposed sidebar states are included.
- `licenses/PHOSPHOR-MIT.txt`: required attribution/licence for the icon assets.
- `manifest.json`: asset status, source information and file hashes.
- `drafts/README.md`: status and review guidance for 30 additional dashboard icon proposals, with SVGs and two comparison sheets.

## Visual foundation

- Brand aubergine: `#37003C`; darkest structural shade: `#1E0021`.
- Bright green accent: `#01FC7A`. This is the repository's actual value,
  although it has often been described conversationally as "lime".
- White: `#FFFFFF`. Follow the new dashboard reference for colour balance.
- Archivo is the typeface direction. Do not carry IBM Plex Mono forward from
  the older implemented dashboard; Jonno's newer preference is Archivo only.
- No meaning conveyed by colour alone. Preserve labels and use shape,
  lightness and position for state differences.

## Logo construction and next review

The draft is an open-bottom goal frame enclosing three rising bars with a
shared baseline. Jonno selected the squared version with bars wider than the
frame. He values thick simple forms and deliberate, even negative space.

The draft uses a 100 × 62 viewBox, a 10-unit frame, 18-unit bars and four equal
6.5-unit horizontal gaps. These describe the supplied drawing; **they are not
locked brand specifications**. Preserve the concept while resolving its
optical balance and its behaviour at actual sizes. Square corners are the
current starting point, not an instruction to make every UI component square.

Review the logo in the real sidebar and at 16, 24 and 32px. A small-size optical
variant may be appropriate, but do not assume one has already been approved.
Get Jonno's review of the resolved shape before calling it final or publishing
it. Final favicon, app-icon, PNG and wordmark exports have deliberately not
been supplied as production assets while geometry remains open.

## Icon use and provenance

The four icons use 256 × 256 viewBoxes and `currentColor`. The earlier preview
used 18px icons inside a 60px rail with 44px targets. Those were comparison
settings, not approved dimensions for the redesign. Keep targets comfortably
usable and visually align icons; identical boxes alone do not ensure equal
apparent size.

Assets derive from [Phosphor Icons](https://github.com/phosphor-icons/core):
`t-shirt-bold`, `path-bold`, `trophy-bold`, `magnifying-glass-bold`.
The shirt was modified locally to merge the sleeve and body openings, removing
the internal seam lines. The other three retain the downloaded geometry.
Keep the bundled MIT copyright/licence notice with distributions. No package,
icon font, framework or runtime dependency is required to use these SVGs.

Use accessible names on navigation controls. Decorative SVGs inside labelled
controls should be hidden from assistive technology. Use `aria-current` for
links or proper selected-state semantics if implementing tabs. Selected state
must remain clear without relying on the green hue alone.

## Exclusions and authority

Eye/pitch marks, football magnifiers, rejected alternatives and generated
whole-page logo mockups are intentionally absent. Do not revive them or infer
approval from historical files elsewhere in the project. Likewise, the old
white selection tile and green logo container are not mandated by this pack.

The complete redesign still needs the latest F-Kit/F-Desktop/F-Phone work and
Jonno's feedback recorded in `docs/HANDOFF.md`. The screenshot here is useful
visual context, not a complete responsive or interaction specification. Any
figures visible in it are reference content, not current FPL data.

The previous text/image similarity search found no convincing close match for
the specific open-bottom goal/chart construction. That search did not prove
uniqueness and was not a reverse-image or trademark clearance.
