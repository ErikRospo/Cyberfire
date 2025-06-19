# Cyberfire

Cyberfire is a real-time, interactive stylized fire simulation written in Python using [Taichi](https://taichi.graphics/). It features multiple color palettes, fire dynamics powered by Perlin noise, and a powerful interactive toolset for painting, erasing, fixing, and highlighting fire pixels. The base structure is inspired by DOOM fire, but much improved via modern techniques.

This code was originally inspired by [Fabien Sanglard's blog](https://fabiensanglard.net/doom_fire_psx/) on this topic.

## Features

- Real-time fire simulation using Taichi's GPU acceleration
- Multiple color palettes: Fire, Cyber, Gray, Cold Fire, Sunset, Toxic, Electric
- Interactive heat injection/removal with mouse
- Palette switching via UI or keyboard
- Adjustable brush radius (mouse wheel) and intensity (slider)
- **Fire tools:** Paint fire, erase fire, draw fire lines, draw fire rectangles
- **Fix tools:** Mark/unmark pixels as "fixed" (immune to fire spread)
- **Highlight fixed pixels:** Toggle highlight overlay for fixed pixels
- **Reset/Clear:** Reset fire, clear fire, reset fixed pixels
- Modern PySide6 GUI with side panel for tool and palette selection

## Requirements

- Python 3.11+
- [Taichi](https://taichi.graphics/) (install via `pip install taichi`)
- [PySide6](https://pypi.org/project/PySide6/) (install via `pip install PySide6`)
- numpy

## Usage

1. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

2. Run the simulation:
    ```sh
    python cyberfire.py
    ```

## Controls

### Mouse

- **Left Mouse Button:** Use the current tool at the cursor (paint/erase/fix/unfix/draw line/draw rectangle)
- **Right Mouse Button:** Use the alternate tool (erase/unfix/complete line/complete rectangle)
- **Mouse Wheel:** Change the radius of the brush/tool

### Keyboard

- **B:** Switch to Fire mode (paint/erase fire)
- **F:** Switch to Fix mode (mark/unmark fixed pixels)
- **V:** Toggle highlight of fixed pixels
- **P:** Cycle through available color palettes
- **R:** Reset fire and fixed pixels
- **S:** Temporarily show brush radius overlay

### UI Side Panel

- **Intensity Slider:** Adjust fire tool intensity (0–100%)
- **Palette Dropdown:** Select color palette
- **Mode Radio Buttons:** Switch between Fire, Fix, Fire Line, and Fire Rect modes
- **Highlight Fixed Button:** Toggle highlight overlay for fixed pixels
- **Reset All:** Reset fire and fixed pixels, and restore palette
- **Clear Fire:** Clear all fire pixels
- **Reset Fixed Pixels:** Unmark all fixed pixels

## Tools

- **Fire Brush:** Paint fire with adjustable radius and intensity
- **Fire Erase:** Remove fire with adjustable radius and intensity
- **Fix Brush:** Mark pixels as fixed (fire will not spread through them)
- **Fix Erase:** Unmark fixed pixels
- **Highlight Fixed:** Overlay highlight on fixed pixels
- **Fire Line:** Draw a line of fire between two points (click to start, right-click to end)
- **Fire Rect:** Draw a rectangle of fire between two points (click to start, right-click to end)


