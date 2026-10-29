# Editor: pasted-image shadow, a shadow switch on every annotation, full-colour drawing preview

Status: **implemented** 2026-10-18 on `feat/editor-shadows-canvas` (A, B and C). Measured for C.3: a shadowed
1400×800 arrow costs 21 ms a frame and a 1000-point pen stroke 16 ms, so while *drawing* the preview leaves out only
the shadow (it appears on release); colour and opacity are the real ones. Moves reuse the cached shadow (A.3 item 4).
Related: [EDITOR-CANVAS-EXPANSION.md](EDITOR-CANVAS-EXPANSION.md) (the page grows to include the image's shadow).

Three changes, in order of size: **C** is a two-line fix, **B** is small, and **A** is a renderer extension.

---

## A. A background shadow under a pasted image, kept through flatten

### A.1 What the user sees

- A pasted image (an `image` layer) gets a soft drop shadow, **on by default**, like a window screenshot dropped
  onto a page.
- With an image layer selected, the header's Image strip shows **Shadow** (switch) and **Intensity** next to W / H /
  Scale % / 100 % / Fit. Changes apply to the selected image and become the default for the next paste.
- The shadow is part of the picture. It shows on the stage and in the Library thumbnail, and it is **kept after
  Flatten, Save and Copy**: it is rendered into the pixels.

### A.2 Why it survives flatten already, once it is drawn

`Document.flatten()` renders every visible layer through `annotations.draw()` (`model/document.py`), and `draw`
calls `_draw_shadow` before the shape (`annotations.py:233`). Any shadow that `draw` paints is therefore baked into
`flatten_into_base`, `save` and the clipboard copy with no extra code. What is missing is only the drawing itself.

### A.3 Renderer changes (`model/annotations.py`)

1. `SHADOW_KINDS` gains `"image"` (and `"step"`, `"callout"`; see B).
2. **Silhouette of an image.** `_shadow_surface` paints a black ghost through the kind's painter, but an image
   ghost is built with `surface=None`, so it paints nothing. For `kind == "image"` paint the silhouette from the
   image's own alpha instead. That gives an opaque screenshot a rectangular shadow, and a transparent PNG a
   shadow of its shape:

   ```python
   if a.kind == "image" and a.surface is not None:
       x, y, w, h = a.rect
       cr.save(); cr.translate(x, y); cr.scale(w / a.surface.get_width(), h / a.surface.get_height())
       cr.set_source_rgb(0, 0, 0); cr.mask_surface(a.surface, 0, 0); cr.restore()
   else:
       _PAINTERS[a.kind](ghost, cr)
   ```

3. **Image shadow geometry.** Stroke shadows scale with the line width (`shadow_sigma = 1.5 + width × 0.35`), which is
   too small for an image. For images use fixed values close to the stage's own page shadow (`Stage.SHADOW_REACH =
   18`): `sigma = 6`, `offset = 4` (down-right), default intensity 0.45. `shadow_extent` then gives
   4 + 18 + 1 = 23 px, which `bounding_box` adds, so selection, hit-testing and the page growth in
   EDITOR-CANVAS-EXPANSION.md all include it.
4. **Cache by size, not position.** `_shadow_key` includes `x1, y1`, so moving a layer recomputes the Gaussian blur
   on every motion event. For a 2560 × 1440 image that is tens of milliseconds per event, and dragging would lag.
   Key the silhouette on the layer's *size* and content (`w, h, id(surface)` for images; the geometry relative to
   `x1, y1` for the rest) and add the position when painting. All shadowed kinds benefit.
5. **Very large images.** `_MAX_SHADOW_PIXELS` (4096²) still applies. Above it, the image gets no shadow and the
   Shadow switch shows a tooltip "too large for a shadow".

### A.4 Settings and UI

- `Settings.TOOLS` (`model/settings.py:24`) gains `"image"`, so `[Tools] shadow_image` and
  `shadow_intensity_image` persist like the other tools, with defaults `shadow=True`, `shadow_intensity=0.45`.
  `StudioWindow.paste_texture` builds the layer's style from `settings.style_for("image")` instead of
  `Style(colour=…)`.
- `ToolProps._image()` (`ui/tool_props.py:279`) adds `labelled("Shadow", switch)` and an Intensity scale, wired
  through the existing `_put("shadow", …)` / `_put("shadow_intensity", …)`. They write the setting and apply it to
  the selected layer (`EditorController.apply_style`, undoable).
- The universal-style switch (`Settings.universal`) leaves `image` out: an arrow's style must not restyle a pasted
  screenshot.

### A.5 Tests

- An opaque 200 × 100 image layer with a shadow: after `flatten()`, a pixel 6 px right of and 6 px below the image
  edge is darker than the background, and the background 40 px away is unchanged.
- A transparent PNG (a disc): the shadow follows the disc, so the pixel at the bounding-box corner is untouched.
- Save as PNG, reload, sample the same pixel: the shadow is in the file.
- Moving a shadowed image 50 times reuses one silhouette (cache-hit counter, or `_shadow_cache` identity).
- Shadow off on the selected image → Ctrl+Z restores it.

---

## B. A shadow switch on every annotation that can have one

### B.1 Audit of today's controls (`ui/tool_props.py`)

| Tool group | Tools | Shadow control | Renders a shadow? |
| --- | --- | --- | --- |
| shape | arrow, line, box, circle | switch + Intensity | yes |
| stroke | pen, marker | switch | yes |
| text | text, callout | switch | text yes; **callout no** (not in `SHADOW_KINDS`, so the switch does nothing) |
| step | step | none | no |
| image | image (paste) | none | no |
| fill, eraser, blur, pixelate, area/cutout | — | none, by design | no: they fill, clear or redact pixels, so a shadow is meaningless |

### B.2 Change

- One rule: **every annotation that draws a visible mark has a Shadow switch**: arrow, line, box, circle, pen,
  marker, text, callout, step and image. A plain switch (the existing `widgets.switch`, "Shadow") is the toggle
  asked for; Intensity stays as the optional second control where it is today (shapes) and is added for image.
- `SHADOW_KINDS` gains `"callout"` (shadow of the bubble and its tail: the painter's path) and `"step"` (the badge
  disc), so the switches that exist actually work.
- `ToolProps._step()` gets `labelled("Shadow", self.step_shadow)` wired like the others.
- The switch follows the selected layer under Select / Move (the strip already syncs from the selection in
  `_sync`), so a shadow can be switched off on one arrow after drawing it.
- Defaults are unchanged (`ToolStyle.shadow = False`), except `image` (on, A.4).

### B.3 Tests

- For each kind in the rule, flip the switch on a selected layer and assert the flattened pixel under the
  shadow offset changes. For fill, eraser, blur and pixelate assert that the strip has no Shadow control.
- Callout with the shadow on renders a shadow (regression for the dead switch).

---

## C. Drawing preview at full colour (bug fix)

### C.1 Symptom

While the user drags out an arrow (any shape, pen, marker or text box), it shows faded and only reaches its real
colour on release.

### C.2 Cause

`EditorController._draw_overlay` (`app/editor_controller.py:682-685`) caps the live preview's opacity at 60 %
while drawing:

```python
ghost = p.copy()
if self._mode in ("draw", "stroke"):
    ghost.style.opacity = min(ghost.style.opacity, 0.6)
draw(ghost, cr, None)
```

Moves and resizes are not capped, so only new annotations look faded.

### C.3 Fix

Draw the preview with its real style: what the user sees while dragging is exactly what is committed.

```python
draw(p, cr, None)            # the live preview uses the real style (colour, opacity, shadow)
```

- The tool's own opacity still applies: a marker at 0.4 previews at 0.4 because that is its real look.
- The shadow is included, so the preview is fully WYSIWYG. With the A.3 cache fix a stroke's shadow is rebuilt
  only when its shape changes, which during a drag is every event. Measure on a long pen stroke. If a frame takes
  more than ~8 ms, skip the shadow during the drag (`replace(p.style, shadow=False)`) and draw it on release. That
  is the one acceptable difference from the committed look, because the colour itself stays full.
- The eraser and area previews keep their special ghosts (`_paint_eraser_ghost`, the dashed area outline):
  clearing pixels in the overlay would also clear the checkerboard.

### C.4 Test

Draw an arrow preview in red at opacity 1.0 into an offscreen surface through `_draw_overlay`, and draw the
committed layer through `Document.render`. The sampled centre pixel of the shaft is identical (alpha 255) in
both. Before the fix the preview's alpha is 153.

---

## Implementation order

1. C (bug fix, with its test): independent and tiny.
2. B (`SHADOW_KINDS` + step switch): small.
3. A (image silhouette, geometry, cache by size, Image strip controls, settings): depends on nothing in B, but
   shares `SHADOW_KINDS`. Then EDITOR-CANVAS-EXPANSION.md, which uses A's `bounding_box` with the shadow.

Docs to update with each step: `docs/FEATURES.md` (§4 header strip, §6 stage, §7 tools, §12 settings), `docs/GUI_SPEC.md` (header
strip per tool), `HANDOFF.md`, `changelog.md`.
