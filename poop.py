import math
import random
import sys
from pathlib import Path

import pygame
from PIL import Image


class RainingPoopApp:
    WIDTH = 400
    HEIGHT = 600
    SPRITE_SIZE = 30
    FPS = 60
    MAX_COUNT = 50
    COUNTER_INTERVAL_MS = 200
    SPAWN_INTERVAL_MS = 500
    ZIGZAG_AMPLITUDE = 30
    SPIRAL_MAX_RADIUS = 40
    COUNTER_OUTLINE_WIDTH = 2

    def __init__(self):
        pygame.init()
        try:
            self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
            pygame.display.set_caption("Counting with Raining Poop")
            self.clock = pygame.time.Clock()
            self.font = pygame.font.Font(None, 48)
            # convert_alpha requires a display surface, so load after set_mode
            self.base_image, self.poop_images = self._load_poop_images()
            self.background = self._load_background()
        except Exception:
            pygame.quit()
            raise

        # Rotating a square grows its bounding box (up to ~1.41x), so every
        # spawn/despawn/margin check must use the largest surface we actually
        # blit -- not SPRITE_SIZE, which would clip rotated sprites.
        self.half = (
            max(max(img.get_size()) for img in (self.base_image, *self.poop_images)) / 2
        )

        self.count = 1
        self.poops = []

        pygame.time.set_timer(pygame.USEREVENT, self.COUNTER_INTERVAL_MS)
        pygame.time.set_timer(pygame.USEREVENT + 1, self.SPAWN_INTERVAL_MS)

    def _load_poop_images(self):
        asset_path = Path(__file__).resolve().parent / "poop_emoji.png"
        if not asset_path.is_file():
            raise FileNotFoundError(f"Poop emoji image not found: {asset_path}")

        poop_image = Image.open(asset_path).convert("RGBA")
        threshold = 230
        new_data = [
            (255, 255, 255, 0)
            if item[0] >= threshold and item[1] >= threshold and item[2] >= threshold
            else item
            for item in poop_image.getdata()
        ]
        poop_image.putdata(new_data)

        base_image = pygame.image.frombytes(
            poop_image.tobytes(), poop_image.size, poop_image.mode
        ).convert_alpha()
        # smoothscale interpolates; plain scale point-samples, which turns an
        # 800px source into a visibly jagged 30px sprite once it also rotates.
        base_image = pygame.transform.smoothscale(
            base_image, (self.SPRITE_SIZE, self.SPRITE_SIZE)
        )

        poop_images = [
            pygame.transform.rotate(base_image, angle) for angle in range(0, 360, 10)
        ]
        return base_image, poop_images

    def _load_background(self):
        asset_path = Path(__file__).resolve().parent / "background.jpg"
        if not asset_path.is_file():
            return None  # purely decorative, so draw() falls back to a plain fill

        # convert(), not convert_alpha(): the sky is opaque, and skipping the
        # per-pixel alpha keeps the full-window blit cheap.
        image = pygame.image.load(asset_path).convert()

        # Scale to cover and centre-crop; scaling straight to WIDTH x HEIGHT
        # would squash a 3:2 photo into a 2:3 window.
        scale = max(self.WIDTH / image.get_width(), self.HEIGHT / image.get_height())
        image = pygame.transform.smoothscale(
            image,
            (
                math.ceil(image.get_width() * scale),
                math.ceil(image.get_height() * scale),
            ),
        )
        crop = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        crop.center = image.get_rect().center
        return image.subsurface(crop).copy()

    def run(self):
        running = True
        try:
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.USEREVENT:
                        self.update_counter()
                    elif event.type == pygame.USEREVENT + 1:
                        self.create_poop()

                self.animate_poop()
                self.draw()
                self.clock.tick(self.FPS)
        finally:
            pygame.quit()

    def update_counter(self):
        self.count += 1
        if self.count > self.MAX_COUNT:
            self.count = 1

    def create_poop(self):
        # Margin covers the widest excursion (spiral) plus the rotated sprite
        margin = self.half + self.SPIRAL_MAX_RADIUS
        base_x = random.randint(math.ceil(margin), int(self.WIDTH - margin))

        self.poops.append(
            {
                "base_x": base_x,
                "x": base_x,
                "y": -self.half,
                "speed": random.uniform(2, 5),
                "pattern": random.choice(["zigzag", "spiral", "straight"]),
                "phase": 0.0,
                "rotating": random.choice([True, False]),
                "image_index": 0,
            }
        )

    def animate_poop(self):
        for poop in self.poops:
            if poop["rotating"]:
                poop["image_index"] = (poop["image_index"] + 1) % len(self.poop_images)

            if poop["pattern"] == "zigzag":
                poop["phase"] += 0.05
                poop["x"] = poop["base_x"] + self.ZIGZAG_AMPLITUDE * math.sin(
                    poop["phase"]
                )
            elif poop["pattern"] == "spiral":
                # Helical path: the orbit widens from zero, so there is no
                # sideways jump on the first animated frame.
                poop["phase"] += 0.1
                radius = min(self.SPIRAL_MAX_RADIUS, poop["phase"] * 2.5)
                poop["x"] = poop["base_x"] + radius * math.cos(poop["phase"])

            poop["y"] += poop["speed"]

        # Rebuild rather than list.remove(), which rescans with dict equality
        self.poops = [p for p in self.poops if p["y"] - self.half <= self.HEIGHT]

    def draw(self):
        if self.background is None:
            self.screen.fill((255, 255, 255))
        else:
            self.screen.blit(self.background, (0, 0))

        for poop in self.poops:
            image = (
                self.poop_images[poop["image_index"]]
                if poop["rotating"]
                else self.base_image
            )
            # x,y are the logical sprite center so rotation stays in place
            self.screen.blit(image, image.get_rect(center=(poop["x"], poop["y"])))

        text = self.font.render(str(self.count), True, (0, 0, 0))
        rect = text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
        # Black alone disappears into the darker patches of cloud, and which
        # patch sits under the centre is not something we control, so ring the
        # digits in white instead of trusting any one part of the sky.
        outline = self.font.render(str(self.count), True, (255, 255, 255))
        for dx in (-self.COUNTER_OUTLINE_WIDTH, 0, self.COUNTER_OUTLINE_WIDTH):
            for dy in (-self.COUNTER_OUTLINE_WIDTH, 0, self.COUNTER_OUTLINE_WIDTH):
                self.screen.blit(outline, rect.move(dx, dy))
        self.screen.blit(text, rect)

        pygame.display.flip()


def main():
    try:
        app = RainingPoopApp()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    except pygame.error as exc:
        print(f"Could not start pygame: {exc}", file=sys.stderr)
        return 1

    try:
        app.run()
    except KeyboardInterrupt:
        pass  # Ctrl+C is a documented way out; exit without a traceback
    return 0


if __name__ == "__main__":
    sys.exit(main())
