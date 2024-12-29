import tkinter as tk
from PIL import Image, ImageTk
import random
import math

class RainingPoopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Counting with Raining Poop")
        
        # Set window size
        self.root.geometry("400x600")
        
        # Create canvas
        self.canvas = tk.Canvas(root, bg='white', width=400, height=600)
        self.canvas.pack(fill="both", expand=True)
        
        # Load and process poop emoji image
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
        
        # Store the base image (resized)
        base_image = poop_image.resize((30, 30), Image.Resampling.LANCZOS)
        self.base_photo = ImageTk.PhotoImage(base_image)
        
        # Create rotated versions of the image for animation
        self.poop_photos = []
        for angle in range(0, 360, 10):  # Create 36 rotated versions
            rotated = poop_image.rotate(angle, expand=True)
            rotated = rotated.resize((30, 30), Image.Resampling.LANCZOS)
            self.poop_photos.append(ImageTk.PhotoImage(rotated))
        
        # Counter variables
        self.count = 0
        self.max_count = 50
        
        # Counter label
        self.counter_label = self.canvas.create_text(
            200, 300,
            text="0",
            font=('Arial', 48, 'bold'),
            fill='black'
        )
        
        # List to store poop images with their properties
        self.poops = []
        
        # Start animations
        self.update_counter()
        self.create_poop()
        self.animate_poop()
    
    def update_counter(self):
        self.count += 1
        if self.count > self.max_count:
            self.count = 1
        self.canvas.itemconfig(self.counter_label, text=str(self.count))
        self.root.after(200, self.update_counter)
    
    def create_poop(self):
        x = random.randint(0, 350)
        
        # Randomly choose movement pattern
        pattern = random.choice(['zigzag', 'spiral', 'straight'])
        
        # Randomly decide if this poop will rotate (50% chance)
        should_rotate = random.choice([True, False])
        
        poop = {
            'id': self.canvas.create_image(x, -20, image=self.base_photo),
            'speed': random.uniform(2, 5),
            'pattern': pattern,
            'angle': 0,
            'phase': 0,
            'photo_index': 0,
            'x': x,
            'rotating': should_rotate
        }
        
        self.poops.append(poop)
        self.root.after(500, self.create_poop)
    
    def animate_poop(self):
        for poop in self.poops[:]:
            current_pos = self.canvas.coords(poop['id'])
            
            if current_pos:  # Check if poop still exists
                x, y = current_pos
                
                # Update rotation only if this poop is supposed to rotate
                if poop['rotating']:
                    poop['photo_index'] = (poop['photo_index'] + 1) % len(self.poop_photos)
                    self.canvas.itemconfig(poop['id'], image=self.poop_photos[poop['photo_index']])
                
                # Calculate movement based on pattern
                if poop['pattern'] == 'zigzag':
                    amplitude = 30
                    frequency = 0.05
                    dx = amplitude * math.sin(poop['phase'])
                    poop['phase'] += frequency
                    new_x = poop['x'] + dx
                    self.canvas.coords(poop['id'], new_x, y + poop['speed'])
                
                elif poop['pattern'] == 'spiral':
                    radius = 20
                    frequency = 0.1
                    dx = radius * math.cos(poop['phase'])
                    poop['phase'] += frequency
                    new_x = poop['x'] + dx
                    self.canvas.coords(poop['id'], new_x, y + poop['speed'])
                
                else:  # straight pattern
                    self.canvas.move(poop['id'], 0, poop['speed'])
                
                # Remove if off screen
                if y > 600:
                    self.canvas.delete(poop['id'])
                    self.poops.remove(poop)
                    
        self.root.after(20, self.animate_poop)

def main():
    root = tk.Tk()
    app = RainingPoopApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()