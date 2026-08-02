# 💩 Raining Poop App

A fun and interactive Python application featuring animated poop emoji rain with a counting animation! Watch as poop emojis fall from the sky in different patterns while a counter tracks time in the center of the screen.

## ✨ Features

- **Animated Poop Emojis**: Poop emojis fall from the top of the window following different movement patterns
- **Multiple Movement Patterns**: 
  - 🔄 **Zigzag**: Emojis sway left and right as they fall
  - 🌀 **Spiral**: Emojis follow a circular motion while descending
  - ⬇️ **Straight**: Direct downward movement
- **Rotating Animation**: Some poop emojis rotate as they fall for dynamic visual effects
- **Live Counter**: A counter in the center increments from 1 to 50, then loops back, outlined in white so it stays readable over the sky
- **Cloudy Sky Backdrop**: A photographic sky (`background.jpg`) is scaled to cover the window; if the file is missing the app falls back to a plain white background
- **Transparent Background**: Clean emoji rendering with background removal
- **Customizable**: Easily modify speed, patterns, and appearance

## 🎮 Built With

- **Pygame**: High-performance game development library for graphics and animations
- **Pillow (PIL)**: Advanced image processing for emoji manipulation and transparency
- **Python 3.10+**: Compatible with modern Python (tested on 3.12)

## 📋 Requirements

- Python 3.10 or higher
- See `requirements.txt` for package dependencies

## 🚀 Installation & Setup

### Using Conda (Recommended)

The project expects a dedicated environment named **`poop`**. No other environment
on this machine ships a compatible pygame, so create it before the first run:

1. **Create and activate the environment**:
   ```bash
   conda create -n poop python=3.12
   conda activate poop
   ```

2. **Install dependencies** (pygame 2.5+ and pillow 10+, matching `requirements.txt`):
   ```bash
   conda install -c conda-forge "pygame>=2.5" "pillow>=10"
   ```

3. **Run the application**:
   ```bash
   python poop.py
   ```

### Using pip

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python poop.py
   ```

## 🎯 How to Use

1. Run the application using one of the methods above
2. A 400x600 window will open showing the raining poop animation
3. Watch as poop emojis fall with different patterns and rotations
4. The counter in the center will increment from 1 to 50 and loop
5. Close the window or press Ctrl+C to exit

## 🩺 Troubleshooting

**`X Error of failed request: BadValue ... NV-GLX` on startup (Linux/X11)**

SDL probes the NVIDIA GLX path and the X server rejects it, so the window never
opens. Force SDL onto EGL instead:

```bash
SDL_VIDEO_X11_FORCE_EGL=1 python poop.py
```

Add `export SDL_VIDEO_X11_FORCE_EGL=1` to your shell profile to make it stick.
This is a driver/display issue, not an application bug — `LIBGL_ALWAYS_SOFTWARE`
and `SDL_RENDER_DRIVER=software` do **not** work around it.

## 🖼️ Assets

| File | Source | License |
| --- | --- | --- |
| `background.jpg` | [Cumulus clouds in the sky](https://commons.wikimedia.org/wiki/File:Cumulus_clouds_in_the_sky.jpg) on Wikimedia Commons, originally [posted to Pixabay by *desilia*](https://pixabay.com/photos/clouds-sky-blue-sky-clouds-blue-2483302/) | [CC0 1.0 Universal Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/deed.en) — no attribution required, commercial use permitted |
| `poop_emoji.png` | Bundled with the project | — |

`background.jpg` is a downscaled (1920×1280) copy of the 5184×3456 Commons
original; CC0 permits the modification. Swapping in your own image only
requires replacing the file — `poop.py` scales whatever it finds to cover the
400×600 window.

## 🛠️ Dependencies

| Package | Version | Used for |
| --- | --- | --- |
| [pygame](https://www.pygame.org/) | `>=2.5.0` | Window management, sprite blitting, rotation, timers, event loop |
| [Pillow](https://python-pillow.org/) | `>=10.0.0` | Loading `poop_emoji.png` and keying its white background to transparent |

Install both at once with `pip install -r requirements.txt`.
