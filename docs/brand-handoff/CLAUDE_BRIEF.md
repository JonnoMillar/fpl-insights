# Brief for Claude

Read `README.md` in this folder first, then the project's `AGENTS.md` and
`docs/HANDOFF.md`. This package supports your redesign of the entire FPL
Insights dashboard; it is not a request to patch branding into the old UI.

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

Re-use Phosphor's bold family for additional ordinary UI symbols where it
fits. Keep licence attribution and avoid introducing an icon-font/runtime
dependency. Customise only when necessary for clarity or visual consistency.

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
