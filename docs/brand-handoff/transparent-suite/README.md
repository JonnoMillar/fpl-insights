**1 November update: previews use genuine Noto Sans (bundled in ../fonts/ with OFL licence). The previous corner is rejected; review ../noto-study/preview.html for two generated replacement treatments. Noto Sans is the proposed page font, not an application change.**

# FPL Insights — transparent generated icon suite

1 November 2026. Current deliverable: 40 image-generated icons in three transparent PNG atlases, with 40 named CSS views. Use this suite instead of the rejected vector redraws. The PNG pixel data is copied unchanged from the image-generation outputs. CSS selects and colours the artwork; it does not draw replacement shapes.

## Use

Keep icons.css and the three PNGs together. Include the stylesheet, then use:

```html
<link rel="stylesheet" href="icons.css">
<span class="fpl-icon fpl-goals" aria-hidden="true"></span>
```

Set `color` for aubergine #37003C, white or green #01FC7A; set `--icon-size:24px` (or another size). CSS alpha masks use the actual generated image shapes and make all colours themeable. No library, icon font, SVG substitution or runtime JavaScript is required. Label controls and statistics; hide decorative symbols from assistive technology. For icon-only buttons, put the accessible name on the button.

## Files

- football.png: 16 football/player indicators; Saves uses the generated B composition as a working choice, not explicit final approval.
- navigation-planning.png: 12 navigation/planning icons. Deadline uses an ordinary clock rather than a stopwatch.
- controls.png: 12 controls.
- icons.css: one class per icon, plus the common fpl-icon class. All 40 names are in catalog.json.
- catalog.json: exact square source view rectangles within each atlas. These are not 40 separate PNG files. A future image pipeline may extract the documented rectangles without redrawing the artwork, if standalone PNGs are preferred.
- preview.html: self-contained image data for easy local viewing, with white/aubergine/green/checkerboard controls and 16/20/24/32px samples.
- preview-white.png, preview-aubergine.png, preview-green.png: actual browser captures.
- transparency-check.json: alpha-channel checks and confirmation that delivered PNGs match the generated source files byte for byte.

## Design status and practical limits

Goals/Assist concepts were approved earlier; these generated transparent exports can vary slightly from their earlier images. Other symbols and Saves B are working selections, not a newly approved final identity. No synthetic code-drawn vectors belong in this handoff. Do not trace by inventing new shapes.

These are raster assets. They are intended for small dashboard icons, not large print artwork. Football scenes, Saves and the wall remain dense at 16px; prefer 24–32px and keep a visible label where space permits. The card symbols use outline versus fill to avoid ambiguous stacked cards; labels/context must still distinguish yellow from red. No claim of universal recognition or final approval is made.

Verified: genuine alpha transparency in all three PNGs; internal openings visually checked on white and aubergine, and green background render captured; all 40 CSS views visible; preview has no horizontal overflow at 1200px and 390px. Browser captures are for visual review, not automatic proof of semantic recognition.

## Claude handoff

Use generated artwork directly in the dashboard redesign; no need to redraw it into SVG before implementation. Claude owns sidebar layout and selected states. Preserve the shirt without sleeve seams. The separate goal/chart logo remains an approved direction with draft geometry; final logo exports remain separate. The application has not been modified and publication is not authorised.

Built-in image-generation edit direction: preserve the reference artwork, remove labels/background including white interior areas, produce transparent atlas cells, use Saves B, single red card and ordinary Deadline clock. No fallback API or paid service was introduced.
