import pygame
from PIL import Image
import random
import math

class RainingPoopApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((400, 600))
        pygame.display.set_caption("Counting with Raining Poop")
        self.clock = pygame.time.Clock()
        self.fps = 60

        # Load and process poop emoji image with PIL
        poop_image = Image.open(r"poop_emoji.png")
        poop_image = poop_image.convert("RGBA")

        # Get the image data
        datas = poop_image.getdata()

        # Create a new image with transparent background
        new_data = []
        threshold = 230

        for item in datas:
            if item[0] >= threshold and item[1] >= threshold and item[2] >= threshold:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)

        poop_image.putdata(new_data)

        # Convert PIL image to Pygame surface
        self.base_image = pygame.image.fromstring(
            poop_image.tobytes(), poop_image.size, poop_image.mode
        ).convert_alpha()
        self.base_image = pygame.transform.scale(self.base_image, (30, 30))

        # Create rotated versions
        self.poop_images = []
        for angle in range(0, 360, 10):
            rotated = pygame.transform.rotate(self.base_image, angle)
            self.poop_images.append(rotated)

        # Font for counter
        self.font = pygame.font.Font(None, 48)

        # Counter variables
        self.count = 0
        self.max_count = 50

        # Timer for counter update
        pygame.time.set_timer(pygame.USEREVENT, 200)  # Every 200ms

        # List to store poop objects
        self.poops = []

        # Timer for creating new poop
        pygame.time.set_timer(pygame.USEREVENT + 1, 500)  # Every 500ms

    def run(self):
        running = True
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
            self.clock.tick(self.fps)

        pygame.quit()

    def update_counter(self):
        self.count += 1
        if self.count > self.max_count:
            self.count = 1

    def create_poop(self):
        x = random.randint(0, 370)  # Adjusted for image width

        pattern = random.choice(['zigzag', 'spiral', 'straight'])
        should_rotate = random.choice([True, False])

        poop = {
            'x': x,
            'y': -20,
            'speed': random.uniform(2, 5),
            'pattern': pattern,
            'phase': 0,
            'rotating': should_rotate,
            'angle': 0,
            'image_index': 0
        }

        self.poops.append(poop)

    def animate_poop(self):
        for poop in self.poops[:]:
            # Update rotation
            if poop['rotating']:
                poop['image_index'] = (poop['image_index'] + 1) % len(self.poop_images)

            # Calculate movement
            if poop['pattern'] == 'zigzag':
                amplitude = 30
                frequency = 0.05
                dx = amplitude * math.sin(poop['phase'])
                poop['phase'] += frequency
                poop['x'] += dx
            elif poop['pattern'] == 'spiral':
                radius = 20
                frequency = 0.1
                dx = radius * math.cos(poop['phase'])
                poop['phase'] += frequency
                poop['x'] += dx

            poop['y'] += poop['speed']

            # Remove if off screen
            if poop['y'] > 600:
                self.poops.remove(poop)

    def draw(self):
        self.screen.fill((255, 255, 255))  # White background

        # Draw poops
        for poop in self.poops:
            image = self.poop_images[poop['image_index']] if poop['rotating'] else self.base_image
            self.screen.blit(image, (poop['x'], poop['y']))

        # Draw counter
        text = self.font.render(str(self.count), True, (0, 0, 0))
        self.screen.blit(text, (200 - text.get_width() // 2, 300 - text.get_height() // 2))

        pygame.display.flip()

def main():
    app = RainingPoopApp()
    app.run()

if __name__ == "__main__":
    main()