# REJECTED — do not implement

30 October 2026: Jonno rejected the code-drawn vector suite, particularly Saves. It does not faithfully preserve the generated artwork. All SVGs, compact variants, screenshots and prior verification here are historical rejected studies, not approved assets. Rendering checks established technical integrity only, not design quality.

Return to the image-generated concept sheets and approved Goals/Assist reference. Refine images first; do not substitute freehand code-drawn icons. Earlier downloadable archives ending in `-vectors.zip` are withdrawn from the handoff recommendation.

---

# FPL Insights — vector suite for review

30 October 2026. Forty individually editable monochrome SVGs, with matching compact exports. These resolve the generated concept sheets into reusable geometry. They are ready for design review and implementation prototyping, not blanket final approval or permission to publish.

## Files

- `icons/`: 40 main masters; 32 × 32 viewBox and 2.4-unit base stroke.
- `compact/`: 40 exports for the 16px column. Saves uses fewer glove divisions and Bonus replaces its central motif with a dot; other geometry currently matches the main master. These are not 40 independently optimized drawings.
- `preview.html`: actual-size 16/20/24/32px comparisons, large drawings and a dark-background toggle. All actual-size samples are shown in black or white to assess monochrome clarity; large drawings use aubergine.
- `preview.png`, `preview-dark.png`, `preview-mobile.png`: verified browser captures.
- `catalog.json`: asset names and paths.
- `build.py`: editable construction source, Python standard library only. Rebuild with `python docs/brand-handoff/vector-suite/build.py` from the repository root.
- `verify.py`: optional local Playwright rendering check. It starts and stops its own temporary local server; Playwright is not an application dependency.

## Shared construction

Football: one central pentagon and five cropped peripheral panels, clipped to a circular outline. Goal: same open-bottom crossbar/post path, adjusted only for composition. Arrows: one triangular arrowhead constructor and shaft geometry, including curved trajectories. Shirts have no internal sleeve seams. Captain/vice/3C armbands share one outline; glyphs are vector paths, not embedded fonts. Most icons use the same round joins, caps and stroke. Smaller wall/glove/glyph details use optically lighter strokes to preserve gaps.

Goals and Assist preserve the approved arrangements: shot from lower left into goal; assist pass from lower left toward a smaller ball near the right post, with no second shot arrow. Original approvals remain available at ../concept-suite/approved-goals-assist.png. Final exact vector geometry remains reviewable.

## Corrections and limits

- Deadline is an ordinary clock, distinct from the Minutes stopwatch.
- Red card is a single filled card; Yellow card is an outlined card. Stacking was removed because it can mean a second yellow. Use explicit labels/accessible names and, when appropriate, conventional card colour; the outline/fill distinction is a proposed monochrome convention, not a universally understood code.
- Injury badge has a transparent knockout so shirt and badge strokes do not collide. No white background patch is baked in.
- Detailed football scenes remain crowded at 16px. Prefer 20–24px for Goals/Assist/set pieces/Saves; keep short visible labels on player cards. The preview shows the actual limits, not proof of universal recognition. Recognition testing with Jonno has not occurred.
- Do not enlarge small-size variants and assume they match the main artwork.

## Implementation for Claude

Use inline SVG with CSS `color` to inherit aubergine #37003C, green #01FC7A or white. External `<img>` SVGs render with their own default colour; parent CSS currentColor does not cross the image boundary. Use inline SVG or a suitable mask for themeable icons. When repeating inline markup, namespace internal clip/mask IDs per instance (football and injury assets contain IDs), or create a properly scoped sprite/component. Decorative icons inside labelled controls should be hidden from assistive technology; icon-only controls need an accessible name. No icon-font package or frontend dependency is needed.

The existing logo/goal-chart-draft.svg remains a draft. This pass supplies the icon suite; it does not approve final logo geometry or create final favicon/app-icon exports. Claude owns sidebar layout, selected states and integration into the redesigned dashboard. Application files remain untouched.

## Verification

80 SVG documents parsed; 160 actual-size samples loaded in Chromium. No empty exports or painted outer-border pixels at 64px raster inspection. Desktop 1280px and mobile 390px previews have no horizontal overflow. Light/dark renders visually reviewed. Checks establish file/render integrity; they do not establish user recognition, final design approval or trademark clearance.
