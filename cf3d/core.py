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

# Marching cubes output: triangles (max N triangles, 3 vertices, 3 coords)
MAX_TRIANGLES = 100000
triangles = ti.Vector.field(3, dtype=ti.f32, shape=(MAX_TRIANGLES, 3))
triangle_colors = ti.Vector.field(3, dtype=ti.u8, shape=(MAX_TRIANGLES,))
num_triangles = ti.field(dtype=ti.i32, shape=())

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
        colors[i] = palette[i]


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


iso_level = MAX_INTENSITY * 0.2


@ti.func
def vertex_interp(p1, p2, valp1: int, valp2: int):
    if abs(iso_level - valp1) < 1e-5:
        return p1
    if abs(iso_level - valp2) < 1e-5:
        return p2
    if abs(valp1 - valp2) < 1e-5:
        return p1
    mu = (iso_level - valp1) / (valp2 - valp1)
    return p1 + mu * (p2 - p1)


# --- Rendering setup ---
scene = Scene(exposure=10)
scene.set_background_color((0, 1, 0))


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


# Update scene voxels from firePixels
@ti.kernel
def update_scene_voxels_from_fire():
    for x, y, z in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT, FIRE_DEPTH):
        intensity = firePixels[x, y, z]
        intensity=ti.math.clamp(intensity,0,MAX_INTENSITY-1)

        if intensity > 0:
            color = colors[intensity]
            scene.renderer.set_voxel(
                ti.Vector([x, y, z]), 2, ti.Vector([color[0]//256, color[1]//256, color[2]//256])
            )
        else:
            # Optionally clear voxel (set material to 0)
            scene.renderer.set_voxel(ti.Vector([x, y, z]), 0, ti.Vector([0, 0, 0]))


def render_scene():
    update_scene_voxels_from_fire()
    # Camera parameters must be set from the GUI before calling this function
    scene.renderer.reset_framebuffer()
    for n in range(10):
        scene.renderer.accumulate()
    img = scene.renderer.fetch_image()
    return img


# --- Utility kernels for fire manipulation (3D) ---
@ti.kernel
def change_heat_at_position(mx: int, my: int, mz: int, radius: int, multiplier: float):
    for dx, dy, dz in ti.ndrange(
        (-radius, radius), (-radius, radius), (-radius, radius)
    ):
        x = mx + dx
        y = my + dy
        z = mz + dz
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT and 0 <= z < FIRE_DEPTH:
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            if dist <= radius:
                delta = int(
                    MAX_INTENSITY
                    * (1 - dist / radius)
                    * multiplier
                    * multiplier
                    * (ti.abs(multiplier) / multiplier)
                )
                firePixels[x, y, z] = ti.min(MAX_INTENSITY, firePixels[x, y, z] + delta)
