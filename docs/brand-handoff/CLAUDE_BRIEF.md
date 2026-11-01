**TYPOGRAPHY / CORNER UPDATE — 1 November: Jonno requested Noto Sans for previews and is considering it for the page. Use the locally bundled font for preview work. Previous corner is rejected; [two generated Noto pairing studies](noto-study/preview.html) await review. No application typography was changed.**

**CURRENT DELIVERABLE — 1 November: [transparent generated icon suite](transparent-suite/README.md), with [working preview](transparent-suite/preview.html). Forty named CSS views use the actual transparent PNG artwork. Use this instead of the rejected vector redraws. Saves B is a working selection.**

**LATEST DECISION — 30 October: the code-drawn `vector-suite/` is REJECTED. Do not implement it or use the earlier `-vectors.zip` package. Return to generated artwork and the approved Goals/Assist composition reference. Image refinement is underway; no replacement suite is approved.**

# Brief for Claude

Read `README.md` in this folder first, then the project's `AGENTS.md` and
`docs/HANDOFF.md`. This package supports your redesign of the entire FPL
Insights dashboard; it is not a request to patch branding into the old UI.
It is a partial working handoff. The current icon deliverable is `vector-suite/`: 40 individual SVGs and compact exports. Read its README and open its preview. Earlier `drafts/` and raster concept sheets are historical proposals. The vector suite still needs Jonno's design review.

## What Jonno chose

- Keep the name **FPL Insights**.
- Proceed with the **goal + ascending data bars logo direction**.
- Use the supplied bold outline navigation icons as the starting set:
  Squad = shirt; Planning = route; Mini-league = trophy; Scout = magnifier.
- Keep the shirt free of internal sleeve seam lines.
- Use the existing aubergine/bright-green palette and Archivo typography.
- Prefer thick, simple geometry with consistent spacing.

## What is still yours to resolve

- Final logo proportions and optical geometry. `goal-chart-draft.svg` is a
  working draft, not an approved master.
- The entire sidebar treatment, including its shape, spacing, icon scale,
  selected states, hover/focus states and motion. Jonno thinks the icons may
  be okay but wants the navigation to feel more distinctive when selected.
  Earlier plain white selection tiles are not a constraint.
- The rest of the dashboard, its responsive layout, components, interactions
  and any additional functional icons, following the separate design work.

Use the vector suite for the supplied icon inventory rather than mixing in unrelated library geometry. Keep the Phosphor licence when using the older navigation starting assets. No icon-font/runtime dependency is needed.

## Show before finalising

Resolve the goal mark and sidebar in the new dashboard, then show Jonno a
concrete preview at actual desktop and phone sizes. Include actual-size
16/24/32px logo checks, selected/unselected navigation and keyboard focus.
Preserve accessible names and a state difference beyond colour alone.

After Jonno accepts the geometry, produce the final SVG/PNG/favicon/app-icon
suite and apply it consistently. Final wordmark spacing and lockups are also
open; earlier sample lockups were exploratory.

Do not revisit the rejected eye concepts. Do not treat this package as
approval to deploy or as permission to change recommendation logic, sources
or data semantics. Preserve the repository's functional and publication
constraints throughout the redesign. Jonno owns the final decisions.


Latest icon direction (30 October): use vector-suite/README.md and preview.html. The vectors supersede the historical bulk dashboard-icons drafts. The approved Goals/Assist raster reference remains in concept-suite/approved-goals-assist.png. Do not use generated sheet crops as UI assets.

Vector checkpoint: shared football/goal/arrow construction is now supplied in vector-suite/build.py and exported SVGs. Browser integrity and actual-size previews checked at 16/20/24/32px. Detailed football scenes are clearer at 20–24px; use labels. No user recognition testing or final suite approval is implied. Final logo exports remain separate work.
