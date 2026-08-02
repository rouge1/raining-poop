# CLAUDE.md — Raining Poop

Working notes for anyone (human or agent) changing this project. User-facing
docs live in `README.md`; this file is about *how the code behaves* and the
traps it sets.

## What this is

A single-file pygame toy: a 400×600 window where poop sprites fall in three
patterns while a counter loops 1→50 in the middle, over a photographic sky.
All of it is `RainingPoopApp` in `poop.py` (~200 lines). There is no package,
no test suite, and no build step — resist adding structure the size of the
problem doesn't justify.

## Environment

Use the **`poop`** conda env. It is the only env on this machine with a
compatible pygame:

```bash
conda activate poop        # python 3.12.13, pygame 2.6.1, pillow 12.3.0
python poop.py
```

`~/miniconda3/envs/venv` also has pygame (2.2.0) and works in a pinch, but it
is not the documented env. Do not assume a bare `python3` will do — the system
interpreter has no pygame at all.

### Testing without a display

There is no test suite, so changes get verified by running the app headless and
inspecting a rendered frame:

```python
import os; os.environ["SDL_VIDEODRIVER"] = "dummy"   # must precede `import pygame`
from poop import RainingPoopApp
app = RainingPoopApp()
for i in range(300):
    if i % 30 == 0: app.create_poop()
    app.update_counter(); app.animate_poop(); app.draw()
pygame.image.save(app.screen, "frame.png")           # then actually look at it
```

Stepping `animate_poop()`/`draw()` by hand beats driving `run()`, which blocks
on the real event loop. Keep these harnesses in a scratch dir — don't commit
them.

## File structure

```
poop.py           the entire app
poop_emoji.png    sprite source, 800px, white background (keyed out at load)
background.jpg    sky backdrop, 1920×1280, CC0 (see README "Assets")
requirements.txt  pygame>=2.5.0, pillow>=10.0.0
docs/             design notes for unstarted work
```

## Architecture

**One class, one loop.** `run()` polls events, then calls `animate_poop()` and
`draw()` at `clock.tick(60)`. Two `pygame.time.set_timer` USEREVENTs drive the
counter (200ms) and spawning (500ms) so those rates are independent of frame
rate.

**Sprites are pre-rotated at startup, not per frame.** `_load_poop_images()`
builds 36 rotations (one per 10°) once; `animate_poop()` just advances an index
into that list. Rotating a surface per frame per sprite would be the obvious
way and the wrong one.

**Falling sprites are plain dicts in `self.poops`**, each carrying its own
`pattern`, `speed`, `phase` and `rotating` flag. `animate_poop()` rebuilds the
list to cull off-screen sprites rather than using `list.remove()`, which would
rescan with dict equality.

**Asset loading order matters.** `convert()`/`convert_alpha()` need an existing
display surface, so every image load happens *after* `set_mode()` inside
`__init__`'s try/except. Moving a load earlier breaks it at runtime, not import
time.

**Two tiers of asset failure.** `poop_emoji.png` is essential — missing, it
raises `FileNotFoundError` and `main()` reports it and exits 1.
`background.jpg` is decorative — missing, `_load_background()` returns `None`
and `draw()` falls back to a white fill. Match this split for future assets:
crash only for what the app can't work without.

## Common pitfalls

**Rotating a square grows its bounding box (up to ~1.41×).** Spawn positions,
cull checks and margins must use `self.half` — computed from the largest
surface actually blitted — never `SPRITE_SIZE`. Using `SPRITE_SIZE` clips
rotated sprites at the edges and makes them pop out of existence early.

**`pygame.transform.scale` point-samples.** Going from an 800px source to a
30px sprite with `scale` produces visible jaggies, made worse by rotation. Use
`smoothscale` for any significant downscale.

**The white-key erases white pixels in *any* sprite you add.**
`_load_poop_images()` keys out every pixel with R,G,B all ≥ `threshold = 230`.
That's correct for the poop emoji's white backdrop, but it will punch holes
straight through a new sprite that legitimately contains white or near-white
(e.g. a white glyph on a colored disc). Give new sprites their own loader or a
`key_white=False` path rather than reusing this one blindly.

**Don't stretch a background to `(WIDTH, HEIGHT)`.** The source photo is 3:2
and the window is 2:3; a direct `smoothscale` to window size visibly squashes
it. `_load_background()` scales to *cover* then centre-crops via
`subsurface(...).copy()`. The `.copy()` matters — a bare subsurface keeps the
parent surface alive and shares its pixels.

**Text needs an outline over a photo, not a color.** The counter renders black,
but which patch of cloud sits under centre isn't controlled, so black alone
washes out. `draw()` blits a white copy of the glyph over a 3×3 offset grid,
then the black glyph on top. This is background-agnostic — it survives someone
swapping `background.jpg` for something darker. Any new HUD text needs the same
treatment (or a translucent backing pill).

**`pygame.time.set_timer` *restarts* the countdown on every call.** It replaces
the existing timer for that event type. Calling it once per frame (16ms) with a
500ms interval means the timer never fires and spawning stops entirely. If a
timer interval ever becomes dynamic, re-arm only inside a branch where the
value actually changed.

**`.gitignore` has no image globs.** `Thumbs.db` is a literal Windows filename,
not a pattern. New image assets are tracked normally — verify with
`git check-ignore -v <file>` rather than assuming either way.

## Assets and licensing

Any image committed here must be public domain or CC0-equivalent, with its
source URL and license recorded in the README "Assets" table. Verify the
license at the source before committing — for Wikimedia Commons, the
`extmetadata` fields from the API are authoritative:

```bash
curl -s "https://commons.wikimedia.org/w/api.php?action=query&titles=File:NAME&prop=imageinfo&iiprop=extmetadata&format=json"
```

If a license can't be confirmed, pick a different image. This repo is MIT.

## `bitcoin_widget` is not importable from here

`/data/python/bitcoin_widget` comes up as a data source (see
`docs/issue-5-bitcoin-plan.md`). Its `PriceFetcher` **cannot** be imported into
this app, for two independent reasons:

1. `price_fetcher.py:4` is `from gi.repository import GLib`. PyGObject is an
   apt package in `/usr/lib/python3/dist-packages`. The envs are disjoint — the
   envs with pygame have no `gi`, and the system interpreter that has `gi` has
   no pygame.
2. Every callback is delivered via `GLib.idle_add`, which queues onto the GLib
   default main context. A pygame loop never iterates that context, so the
   callbacks would silently never fire even if `gi` were installed.

Take its *knowledge* (endpoints, fallback order, parse shapes) and reimplement
against the stdlib. Don't depend on the module.

## Dependencies

`requirements.txt` is `pygame>=2.5.0` and `pillow>=10.0.0` — pygame for
everything windowing/blitting/rotation, Pillow only for loading
`poop_emoji.png` and keying its background transparent. The sky backdrop added
no dependency (pygame loads JPEG natively via SDL_image).

Keep it that way where reasonable: prefer the stdlib over a new package for
anything small. If a dependency does get added, update `requirements.txt`, the
README dependency table, and the conda install line in the README together.
