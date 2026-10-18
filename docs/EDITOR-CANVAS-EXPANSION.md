# Editor: the page grows to fit a pasted image (technical design)

Status: **implemented** 2026-10-18 on `feat/editor-shadows-canvas`, with the recommended answers to §7 (1:1 paste,
page padding, image layers only) pending the operator's confirmation. Differences from the design below:
growth is decided in one place, `EditorController._grow_page_for`, called by `_commit` for any `AddLayer` /
`EditAnnotation` on an image layer, and folded into that step with `UndoStack.amend` (`Compound`). The live dashed
outline and the provisional canvas extent while dragging (§4.3) are **not** built yet: growing the canvas mid-drag
re-centres the page under the pointer. The page grows on release. *Fit* fits the image with its shadow, so a
fitted image never grows the page.
Related: [EDITOR-SHADOWS-AND-PREVIEW.md](EDITOR-SHADOWS-AND-PREVIEW.md) (the pasted image's shadow, which this
feature must never clip).

## 1. What the user sees

1. An image is pasted into an open document (Ctrl+V, or *Paste* in the clipboard tray). It keeps its own size.
2. Wherever the pasted image ends up outside the current page (on paste, after a move, after a resize), the page
   grows to contain it, plus **20 px of padding** beyond the image's painted edge (its shadow included). It grows
   only on the sides that overflow.
3. While the user drags the image past the edge, the stage shows a dashed outline of the page it will become.
   On release the page grows in one step. Ctrl+Z restores the old page size and the image's old position together.
4. The new page area is transparent (checkerboard on the stage). PNG and WebP keep the transparency; JPEG fills it
   with white, as `Document.save` already does.
5. The page never shrinks by itself when the image moves back inside. Crop (or the Area tool → Enter) trims it;
   undo reverts a growth.

## 2. Terms

| Term | Meaning |
| --- | --- |
| page | the document's base surface: `Document.width × Document.height` (`model/document.py`) |
| image layer | an `Annotation` of kind `"image"`: its `surface` scaled into `rect` (`annotations._paint_image`) |
| painted extent | `Annotation.bounding_box()`: the rect plus stroke and shadow (`annotations.py:97`) |
| `EXPAND_PADDING` | 20 px, in image pixels, beyond the painted extent |
| stage margin | the screen gap around the page in the stage: `Stage.MARGIN = 40`, centred, so 20 px a side (`ui/stage.py:114`) |

## 3. Current behaviour (what changes)

- `StudioWindow.paste_texture` (`ui/studio_window.py:491`) scales a paste down to fit the page
  (`scale = min(1.0, doc.width / w, doc.height / h)`) and centres it, so a paste never reaches outside.
- A move or resize (`EditorController._drag_end`, `app/editor_controller.py:248`) commits `EditAnnotation` with
  the new coordinates. Pixels outside the page are drawn into the stage overlay but are lost on flatten and save:
  `Document.flatten` renders into a page-sized surface.
- The stage canvas is page size × zoom + `MARGIN` (`Stage._resize_canvas`), so a preview beyond the page is cut
  off 20 screen px past the edge.

## 4. Design

### 4.1 Model: one undo step that grows the page and moves the layers

Growth reuses the existing `TransformBase` (`model/undo.py:153`): a new, larger transparent base with the old base
painted at `(left, top)`, and a mapper that translates every layer by the same amount.

```python
# model/document.py (no GTK)
EXPAND_PADDING = 20

def expansion_for(doc, box, pad=EXPAND_PADDING) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) growth so that ``box`` (x, y, w, h) plus ``pad`` fits; zeros when it fits."""
    x, y, w, h = box
    left = max(0, math.ceil(pad - x))
    top = max(0, math.ceil(pad - y))
    right = max(0, math.ceil(x + w + pad - doc.width))
    bottom = max(0, math.ceil(y + h + pad - doc.height))
    return left, top, right, bottom

def expanded_base(base, left, top, right, bottom) -> cairo.ImageSurface:
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, base.get_width() + left + right, base.get_height() + top + bottom)
    cr = cairo.Context(out)
    cr.set_source_surface(base, left, top)
    cr.paint()
    out.flush()
    return out
```

A new `Compound` command (`model/undo.py`) applies a list of commands in order and reverts them in reverse, with
one label, so "Move + grow page" is a single Ctrl+Z:

```python
@dataclass
class Compound:
    commands: list
    label: str = "Edit"
    def apply(self, doc):  [c.apply(doc) for c in self.commands]
    def revert(self, doc): [c.revert(doc) for c in reversed(self.commands)]
```

The order matters. The layer's own edit is applied first, in old page coordinates. The `TransformBase` growth
follows and translates every layer, the edited one included, by `(left, top)`.

### 4.2 Controller: where growth is decided

One helper in `EditorController`:

```python
def commit_with_growth(self, cmd, layer_or_annotation, label):
    """Commit ``cmd``; if the image layer's painted extent then leaves the page, grow it in the same step."""
```

Called from:

| Trigger | Today | With growth |
| --- | --- | --- |
| Paste (`StudioWindow.paste_texture`) | `AddLayer` of a fitted, centred image | `AddLayer` at 1:1, centred on the visible part of the page → `commit_with_growth` |
| Move of an image layer (`_drag_end`, mode `move`) | `EditAnnotation` | `commit_with_growth` |
| Resize handle (`_drag_end`, mode `handle:*`) | `EditAnnotation` | `commit_with_growth` |
| Header W / H / Scale % / 100 % (`tool_props._image_size`, `_image_scale`, `set_layer_size`) | `EditAnnotation` | `commit_with_growth` |
| Arrow-key nudge (`nudge_selected`) | `EditAnnotation` | `commit_with_growth` (a nudge past the edge grows by the nudge) |
| Duplicate (Ctrl+D) / layer paste (`paste_layer`, offset 12 px) | `AddLayer` | `commit_with_growth` |

Scope: **image layers only** (kind `"image"`). Arrows, text and the other annotations keep today's behaviour. They
may extend past the page and are clipped on flatten. A later setting can widen the scope. See §7.

The *Fit* button (`fit_selected`) still shrinks the image to fit inside the page; it never grows the page.

### 4.3 Stage: live outline while dragging, and keeping the view still

- While an image layer is being moved or resized, `EditorController._draw_overlay` computes
  `expansion_for(doc, preview.bounding_box())`. If it is non-zero, it draws a dashed accent rectangle of the
  future page (`-left, -top, doc.width + left + right, doc.height + top + bottom` in image px). The stage also grows
  its canvas content size for the drag (`Stage.set_provisional_extent(rect)`; cleared on release), so the preview
  is not cut off at the widget edge. Nothing in the document changes until release.
- When the page grows to the left or top, every layer's image coordinates shift by `(left, top)`. To keep the
  picture still on screen, the stage scrolls by `(left × zoom, top × zoom)` after the growth (`Stage.scroll_by`
  exists, `ui/stage.py:203`). Zoom is not changed; the user zooms out (Ctrl+0 fits) if the page no longer fits.
- The stage drop shadow (`SHADOW_REACH = 18`) is drawn around the new page size automatically:
  `_draw_canvas` reads the composite's size.

### 4.4 Padding

`EXPAND_PADDING = 20` image pixels beyond the layer's painted extent. The painted extent already includes the
image's shadow (`bounding_box` adds `shadow_extent`), so the shadow is never cut off and there are 20 px of page
beyond it. The padding is applied only on overflowing sides: an image that overflows on the right adds width on
the right only.

The stage's own screen gap around the page (`Stage.MARGIN = 40`, 20 px a side) is unchanged. If the request was
meant as that gap instead (more room between the page and the stage edge), it is one constant; see §7.

### 4.5 Header, Library and save

- `Document.summary()` shows the new size (`Edit · 2580×1120 · PNG · …`) after a growth; the header subtitle
  updates through the existing `state.subtitle` refresh.
- Saving writes the grown page, so the Library thumbnail shows it.
- A toast on the first growth in a document: "Page enlarged to fit the image · Ctrl+Z undoes".

## 5. Edge cases

| Case | Behaviour |
| --- | --- |
| Paste larger than the page in both directions | page grows on all sides as needed; image centred on the old page centre |
| Paste with no document open | unchanged: the paste becomes the document (`paste_texture`, empty branch) |
| Image dragged far away (e.g. 10 000 px) | growth capped at `MAX_PAGE = 16384` px a side (cairo's limit is 32767); beyond it the move is still committed, and a toast says the page cannot grow further |
| Rotate / flip / crop after a growth | unchanged: they operate on the grown page |
| Flatten | flattens the grown page; the transparent area stays transparent |
| Undo after save | Ctrl+Z restores the old size; the document becomes dirty again |
| Area tool or a crop rectangle pending during a growth | the pending rectangle is translated by `(left, top)` with the layers |

## 6. Tests (`tests/test_canvas_expansion.py`)

- `expansion_for`: no growth inside the page; right-only, left-only and all-side growth; padding counts from the
  shadow edge when the layer has a shadow.
- Move an image layer past the right edge → page width = layer right edge + shadow extent + 20; one undo restores
  width, height and the layer's coordinates; redo re-applies.
- Move past the top-left → every layer (an arrow too) shifts by `(left, top)`; the base pixels sit at
  `(left, top)` in the new base (sample a known pixel).
- Paste a 1.5× page-size texture → page grows; the image is 1:1 (layer rect equals the texture size).
- Save as PNG keeps alpha 0 in the new area; JPEG gives white there.
- Stage: the provisional extent grows the canvas during a drag and is cleared on release (no document change
  before release).

## 7. Open questions for the operator

1. **Paste size.** The design pastes at 1:1 and grows the page (today it fits the paste inside the page). *Fit* in the
   header still shrinks it in one click. Keep 1:1 as the default? (Recommended.)
2. **"20 px padding"** is read as page padding beyond the moved image. The alternative is the stage's screen gap
   around the page, `Stage.MARGIN`. Today that gap is 20 px a side. Which was meant?
3. **Scope.** Image layers only (recommended), or should any annotation dragged off the page grow it as well?
