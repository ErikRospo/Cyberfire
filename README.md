# Cyberfire

Cyberfire is a real-time, interactive fire simulation written in Python using [Taichi](https://taichi.graphics/). It features multiple color palettes and realistic fire dynamics powered by Perlin noise. The base structure is inspired by DOOM fire, though much improved via modern techniques.

This code was originally inspired by [Fabien Sanglard's blog](https://fabiensanglard.net/doom_fire_psx/) on this topic.
## Features

- Real-time fire simulation using Taichi's GPU acceleration
- Multiple color palettes: fire, cyber, gray, cold fire, sunset, toxic, electric
- Interactive heat injection with mouse
- Palette switching with keyboard

## Requirements

- Python 3.8+
- [Taichi](https://taichi.graphics/) (install via `pip install taichi`)

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

- **Left Mouse Button:** Add heat to the fire at the cursor
- **Right Mouse Button:**: Remove heat from the fire at the cursor
- **Mouse Wheel**: Change the radius of the heat tool
- **P key:** Cycle through available color palettes
- **R key:** Reset the fire

