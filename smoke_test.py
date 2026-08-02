#!/usr/bin/env python3
"""Headless smoke test for poop.py.

Deliberately not a pytest suite: this drives the real app against SDL's dummy
video driver, so it runs anywhere -- CI, a container, an SSH session with no
display -- with nothing installed beyond what the app already needs.

    python smoke_test.py     # 0 if every check passes, 1 otherwise
"""

import os

# Must precede `import pygame`: SDL picks its video driver at init time, and a
# driver chosen after the fact is ignored. setdefault so an explicit
# SDL_VIDEODRIVER from the caller still wins.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import sys
from pathlib import Path

import pygame

from poop import RainingPoopApp

FRAMES = 300
SPAWN_EVERY = 30
ROOT = Path(__file__).resolve().parent


def _step(app, frames=FRAMES):
    """Advance the app by hand.

    run() blocks on the real event loop and its USEREVENT timers, so the
    frame-by-frame calls are driven directly instead.
    """
    for i in range(frames):
        if i % SPAWN_EVERY == 0:
            app.create_poop()
        app.update_counter()
        app.animate_poop()
        app.draw()


def check_assets_load():
    """Every surface is present and the size the app expects."""
    app = RainingPoopApp()
    try:
        assert app.screen.get_size() == (app.WIDTH, app.HEIGHT), app.screen.get_size()

        assert app.background is not None, "background.jpg failed to load"
        assert app.background.get_size() == (app.WIDTH, app.HEIGHT), (
            f"background is {app.background.get_size()}, expected the window size"
        )

        assert app.base_image.get_size() == (app.SPRITE_SIZE, app.SPRITE_SIZE), (
            app.base_image.get_size()
        )
        assert len(app.poop_images) == 36, f"{len(app.poop_images)} rotations, want 36"

        # Rotating a square grows its bounding box, so half must exceed
        # SPRITE_SIZE/2 -- if it doesn't, the margin maths is back to clipping
        # rotated sprites at the window edges.
        assert app.half > app.SPRITE_SIZE / 2, app.half
    finally:
        pygame.quit()


def check_frames_step():
    """A few hundred frames of spawning, animating and drawing don't raise."""
    app = RainingPoopApp()
    try:
        _step(app)
        assert app.poops, "every sprite was culled; spawning or culling is wrong"
        # Culling must leave nothing below the bottom margin.
        assert all(p["y"] - app.half <= app.HEIGHT for p in app.poops)
        assert 1 <= app.count <= app.MAX_COUNT, app.count
    finally:
        pygame.quit()


def check_missing_background_falls_back():
    """A missing backdrop degrades to the plain fill instead of crashing."""
    asset = ROOT / "background.jpg"
    stashed = ROOT / "background.jpg.smoketest-bak"

    asset.rename(stashed)
    try:
        app = RainingPoopApp()
        try:
            assert app.background is None, "expected no background surface"
            _step(app, frames=SPAWN_EVERY)
        finally:
            pygame.quit()
    finally:
        stashed.rename(asset)  # restore even if the check blew up


CHECKS = (
    check_assets_load,
    check_frames_step,
    check_missing_background_falls_back,
)


def main():
    failed = []
    for check in CHECKS:
        try:
            check()
        except Exception as exc:
            failed.append(check.__name__)
            print(f"FAIL  {check.__name__}: {exc}", file=sys.stderr)
        else:
            print(f"ok    {check.__name__}")

    if failed:
        print(f"\n{len(failed)} of {len(CHECKS)} checks failed", file=sys.stderr)
        return 1
    print(f"\nall {len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
