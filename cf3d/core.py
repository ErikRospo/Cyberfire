import os

import numpy as np
import taichi as ti

from constants import (ADD_MULT, DECAY_MULT, FIRE_DEPTH, FIRE_HEIGHT,
                       FIRE_WIDTH, MAX_INTENSITY)
from palettes import (palette_cold_fire, palette_cyber, palette_electric,
                      palette_fire, palette_gray, palette_sunset,
                      palette_toxic)
from ti_renderer.scene import Scene

ti.init(arch=ti.gpu)

# 3D Fire simulation field: (width, height, depth)
firePixels = ti.field(dtype=ti.i32, shape=(FIRE_WIDTH, FIRE_HEIGHT, FIRE_DEPTH))
# Color palette
colors = ti.Vector.field(3, dtype=ti.u8, shape=(MAX_INTENSITY + 1))

# --- Palette management ---

_PALETTE_LIST = [
    ("Fire", lambda: set_palette(palette_fire)),
    ("Cyber", lambda: set_palette(palette_cyber)),
    ("Gray", lambda: set_palette(palette_gray)),
    ("Cold Fire", lambda: set_palette(palette_cold_fire)),
    ("Sunset", lambda: set_palette(palette_sunset)),
    ("Toxic", lambda: set_palette(palette_toxic)),
    ("Electric", lambda: set_palette(palette_electric)),
]


def get_palette_list():
    return _PALETTE_LIST


def set_palette(palette_func):
    palette = palette_func()
    for i in range(MAX_INTENSITY + 1):
        colors[i] = ti.Vector([int(x) for x in palette[i]])  # Ensure vector of ints


# --- 3D Perlin noise and fire spread ---
@ti.func
def lerp(a, b, t):
    return a * (1 - t) + b * t


@ti.func
def fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


@ti.func
def grad(hash, x, y, z):
    h = hash & 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if (h == 12 or h == 14) else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


@ti.func
def permute(x):
    return ((34 * x + 1) * x) % 289


@ti.func
def perlin_noise(x, y, z):
    X = int(ti.floor(x)) & 255
    Y = int(ti.floor(y)) & 255
    Z = int(ti.floor(z)) & 255
    xf = x - ti.floor(x)
    yf = y - ti.floor(y)
    zf = z - ti.floor(z)
    u = fade(xf)
    v = fade(yf)
    w = fade(zf)
    A = permute(X) + Y
    AA = permute(A) + Z
    AB = permute(A + 1) + Z
    B = permute(X + 1) + Y
    BA = permute(B) + Z
    BB = permute(B + 1) + Z
    n000 = grad(int(permute(AA)), xf, yf, zf)
    n100 = grad(int(permute(BA)), xf - 1.0, yf, zf)
    n010 = grad(int(permute(AB)), xf, yf - 1.0, zf)
    n110 = grad(int(permute(BB)), xf - 1.0, yf - 1.0, zf)
    n001 = grad(int(permute(AA + 1)), xf, yf, zf - 1.0)
    n101 = grad(int(permute(BA + 1)), xf - 1.0, yf, zf - 1.0)
    n011 = grad(int(permute(AB + 1)), xf, yf - 1.0, zf - 1.0)
    n111 = grad(int(permute(BB + 1)), xf - 1.0, yf - 1.0, zf - 1.0)
    x1 = lerp(n000, n100, u)
    x2 = lerp(n010, n110, u)
    y1 = lerp(x1, x2, v)
    x3 = lerp(n001, n101, u)
    x4 = lerp(n011, n111, u)
    y2 = lerp(x3, x4, v)
    return (lerp(y1, y2, w) + 1) * 0.5


@ti.func
def spread_fire(x: int, y: int, z: int, time: float):
    if y < FIRE_HEIGHT - 1:
        offset = int(ti.random() * 3 + 1)
        sample_y = ti.min(y + offset, FIRE_HEIGHT - 1)
        below_intensity = firePixels[x, sample_y, z]
        offset_noise = perlin_noise(x * 0.05 + time, y * 0.05 + time, z * 0.05 + time)
        rand_offset_x = int(offset_noise * 5.0) - 2
        rand_offset_z = (
            int(perlin_noise(z * 0.05 + time, x * 0.05 + time, y * 0.05 + time) * 5.0)
            - 2
        )
        dst_x = ti.math.clamp(x + rand_offset_x, 0, FIRE_WIDTH - 1)
        dst_z = ti.math.clamp(z + rand_offset_z, 0, FIRE_DEPTH - 1)
        decay = int(ti.random() * DECAY_MULT) + 1
        rand_intensity = int(ti.random() * ADD_MULT)
        new_intensity = ti.max(0, below_intensity - decay + rand_intensity)
        firePixels[dst_x, y, dst_z] = new_intensity


@ti.kernel
def do_fire(time: float):
    for x, y, z in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT - 1, FIRE_DEPTH):
        spread_fire(x, y, z, time)


@ti.kernel
def initialize_fire():
    for x, z in ti.ndrange(FIRE_WIDTH, FIRE_DEPTH):
        firePixels[x, FIRE_HEIGHT - 1, z] = MAX_INTENSITY


scene = Scene(exposure=1, voxel_edges=0)
scene.set_background_color((0, 0, 0))


def set_camera_pos(pos):
    scene.set_camera_pos(pos)


def set_look_at(look_at):
    scene.set_look_at(look_at)


def set_up(up):
    scene.set_up(up)


def set_fov(fov):
    scene.set_fov(fov)


def set_directional_light(direction, direction_noise, color):
    scene.set_directional_light(direction, direction_noise, color)


def set_background_color(color):
    scene.set_background_color(color)


def render_scene(passes=1):
    scene.renderer.read_fire_pixels(firePixels, colors)
    scene.renderer.reset_framebuffer()
    for n in range(passes):
        scene.renderer.accumulate()
    img = scene.renderer.fetch_image()
    return img
