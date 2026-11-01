# FPL Insights — generated icon set

1 November 2026. Forty image-generated icons with transparent backgrounds, Noto Sans preview typography and the latest reference-based corner flag. Rejected code-drawn SVGs and rejected corner studies are excluded from this delivery.

Open preview.html to see the whole set on white, aubergine, green and checkerboard backgrounds. It includes actual-size samples at 16, 20, 24 and 32px. The artwork is raster, not vector.

## For Claude

Copy icons.css and the four PNG files together, preserving filenames. Add the stylesheet, then select any of the 40 icons by its class:

```html
<link rel="stylesheet" href="icons.css">
<span class="fpl-icon fpl-goals" aria-hidden="true"></span>
<span class="fpl-icon fpl-corners" aria-hidden="true"></span>
```

Set `color` to theme the icon (aubergine #37003C, white, green #01FC7A); set `--icon-size:24px` to choose its size. The CSS uses alpha masks to display the generated artwork directly. It does not draw substitute icon shapes. No frontend dependency, font icon library or runtime script is required. For statistics and icon-only controls, supply appropriate visible or accessible labels.

Forty class names and their original source rectangles are listed in catalog.json. Artwork is stored in three shared atlases plus the standalone corners.png. The old corner cell in football.png is unused; always use the named .fpl-corners selector, which points to the replacement. These are 40 independently selectable icons, not 40 separate PNG files. Do not recreate the drawings with improvised SVG geometry.

Noto Sans is bundled under ../fonts/ with its OFL licence. Previews use the real font; application font selection remains Jonno's decision during the redesign. Noto Sans does not need to be installed on the computer to open the preview.

Use 24–32px for detailed football scenes when practical; 16px samples show the limits of the detail. Preserve labels for ambiguous events and card colours. Outline versus solid card is a proposed monochrome distinction, not a universal convention.

## Contents

- icons.css: all 40 named icon selectors.
- football.png, navigation-planning.png, controls.png: original generated transparent atlases, unchanged pixels.
- corners.png: latest generated reference-based corner, unchanged pixels.
- catalog.json: icon names and source view rectangles.
- preview.html and preview-*.png: Noto Sans preview and browser captures.
- transparency-check.json: original atlas alpha checks; corners metadata is added below.

The icon set is packaged for handoff. This does not imply final approval of every symbol, final logo geometry, or permission to publish. The goal/chart logo remains a separate draft direction. Application files have not changed.
