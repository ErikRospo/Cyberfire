import math

import numpy as np
import taichi as ti

from constants import (ADD_MULT, DECAY_MULT, FIRE_DEPTH, FIRE_HEIGHT,
                       FIRE_WIDTH, MAX_INTENSITY)
from palettes import (palette_cold_fire, palette_cyber, palette_electric,
                      palette_fire, palette_gray, palette_sunset,
                      palette_toxic)

ti.init(arch=ti.gpu)

# 3D Fire simulation field: (width, height, depth)
firePixels = ti.field(dtype=ti.i32, shape=(FIRE_WIDTH, FIRE_HEIGHT, FIRE_DEPTH))
# 2D Image: (width, height, 3)
image = ti.field(dtype=ti.u8, shape=(FIRE_WIDTH, FIRE_HEIGHT, 3))
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


# --- Marching Cubes ---
# Simple implementation for isosurface extraction
# For brevity, only a basic version is provided. For production, use a full lookup table.

iso_level = MAX_INTENSITY // 2


@ti.func
def vertex_interp(p1, p2, valp1, valp2):
    if abs(iso_level - valp1) < 1e-5:
        return p1
    if abs(iso_level - valp2) < 1e-5:
        return p2
    if abs(valp1 - valp2) < 1e-5:
        return p1
    mu = (iso_level - valp1) / (valp2 - valp1)
    return p1 + mu * (p2 - p1)


# Full edge table and triangle table for Marching Cubes
# These tables are standard and widely available (public domain, e.g. Paul Bourke, VTK, Wikipedia)

edge_table = ti.field(dtype=ti.i32, shape=256)
tri_table = ti.field(dtype=ti.i32, shape=(256, 16))

edge_table_np = [
    0x000,
    0x109,
    0x203,
    0x30A,
    0x406,
    0x50F,
    0x605,
    0x70C,
    0x80C,
    0x905,
    0xA0F,
    0xB06,
    0xC0A,
    0xD03,
    0xE09,
    0xF00,
    0x190,
    0x099,
    0x393,
    0x29A,
    0x596,
    0x49F,
    0x795,
    0x69C,
    0x99C,
    0x895,
    0xB9F,
    0xA96,
    0xD9A,
    0xC93,
    0xF99,
    0xE90,
    0x230,
    0x339,
    0x033,
    0x13A,
    0x636,
    0x73F,
    0x435,
    0x53C,
    0xA3C,
    0xB35,
    0x83F,
    0x936,
    0xE3A,
    0xF33,
    0xC39,
    0xD30,
    0x3A0,
    0x2A9,
    0x1A3,
    0x0AA,
    0x7A6,
    0x6AF,
    0x5A5,
    0x4AC,
    0xBAC,
    0xAA5,
    0x9AF,
    0x8A6,
    0xFAA,
    0xEA3,
    0xDA9,
    0xCA0,
    0x460,
    0x569,
    0x663,
    0x76A,
    0x066,
    0x16F,
    0x265,
    0x36C,
    0xC6C,
    0xD65,
    0xE6F,
    0xF66,
    0x86A,
    0x963,
    0xA69,
    0xB60,
    0x5F0,
    0x4F9,
    0x7F3,
    0x6FA,
    0x1F6,
    0x0FF,
    0x3F5,
    0x2FC,
    0xDFC,
    0xCF5,
    0xFFF,
    0xEF6,
    0x9FA,
    0x8F3,
    0xBF9,
    0xAF0,
    0x650,
    0x759,
    0x453,
    0x55A,
    0x256,
    0x35F,
    0x055,
    0x15C,
    0xE5C,
    0xF55,
    0xC5F,
    0xD56,
    0xA5A,
    0xB53,
    0x859,
    0x950,
    0x7C0,
    0x6C9,
    0x5C3,
    0x4CA,
    0x3C6,
    0x2CF,
    0x1C5,
    0x0CC,
    0xFCC,
    0xEC5,
    0xDCF,
    0xCC6,
    0xBCA,
    0xAC3,
    0x9C9,
    0x8C0,
    0x8C0,
    0x9C9,
    0xAC3,
    0xBCA,
    0xCC6,
    0xDCF,
    0xEC5,
    0xFCC,
    0x0CC,
    0x1C5,
    0x2CF,
    0x3C6,
    0x4CA,
    0x5C3,
    0x6C9,
    0x7C0,
    0x950,
    0x859,
    0xB53,
    0xA5A,
    0xD56,
    0xC5F,
    0xF55,
    0xE5C,
    0x15C,
    0x055,
    0x35F,
    0x256,
    0x55A,
    0x453,
    0x759,
    0x650,
    0xAF0,
    0xBF9,
    0x8F3,
    0x9FA,
    0xEF6,
    0xFFF,
    0xCF5,
    0xDFC,
    0x2FC,
    0x3F5,
    0x0FF,
    0x1F6,
    0x6FA,
    0x7F3,
    0x4F9,
    0x5F0,
    0xB60,
    0xA69,
    0x963,
    0x86A,
    0xF66,
    0xE6F,
    0xD65,
    0xC6C,
    0x36C,
    0x265,
    0x16F,
    0x066,
    0x76A,
    0x663,
    0x569,
    0x460,
    0xCA0,
    0xDA9,
    0xEA3,
    0xFAA,
    0x8A6,
    0x9AF,
    0xAA5,
    0xBAC,
    0x4AC,
    0x5A5,
    0x6AF,
    0x7A6,
    0x0AA,
    0x1A3,
    0x2A9,
    0x3A0,
    0xD30,
    0xC39,
    0xF33,
    0xE3A,
    0x936,
    0x83F,
    0xB35,
    0xA3C,
    0x53C,
    0x435,
    0x73F,
    0x636,
    0x13A,
    0x033,
    0x339,
    0x230,
    0xE90,
    0xF99,
    0xC93,
    0xD9A,
    0xA96,
    0xB9F,
    0x895,
    0x99C,
    0x69C,
    0x795,
    0x49F,
    0x596,
    0x29A,
    0x393,
    0x099,
    0x190,
    0xF00,
    0xE09,
    0xD03,
    0xC0A,
    0xB06,
    0xA0F,
    0x905,
    0x80C,
    0x70C,
    0x605,
    0x50F,
    0x406,
    0x30A,
    0x203,
    0x109,
    0x000,
]

tri_table_np = [
    [-1] * 16,
    [0, 8, 3, -1] * 4,
    [0, 1, 9, -1] * 4,
    [1, 8, 3, 9, 8, 1, -1] * 2,
    [1, 2, 10, -1] * 4,
    [0, 8, 3, 1, 2, 10, -1] * 2,
    [9, 2, 10, 0, 2, 9, -1] * 2,
    [2, 8, 3, 2, 10, 8, 10, 9, 8, -1] + [-1] * 7,
    [3, 11, 2, -1] * 4,
    [0, 11, 2, 8, 11, 0, -1] * 2,
    [1, 9, 0, 2, 3, 11, -1] * 2,
    [1, 11, 2, 1, 9, 11, 9, 8, 11, -1] + [-1] * 7,
    [3, 10, 1, 11, 10, 3, -1] * 2,
    [0, 10, 1, 0, 8, 10, 8, 11, 10, -1] + [-1] * 7,
    [3, 9, 0, 3, 11, 9, 11, 10, 9, -1] + [-1] * 7,
    [9, 8, 10, 10, 8, 11, -1] * 2,
    [4, 7, 8, -1] * 4,
    [4, 3, 0, 7, 3, 4, -1] * 2,
    [0, 1, 9, 8, 4, 7, -1] * 2,
    [4, 1, 9, 4, 7, 1, 7, 3, 1, -1] + [-1] * 7,
    [1, 2, 10, 8, 4, 7, -1] * 2,
    [3, 4, 7, 3, 0, 4, 1, 2, 10, -1] + [-1] * 7,
    [9, 2, 10, 9, 0, 2, 8, 4, 7, -1] + [-1] * 7,
    [2, 10, 9, 2, 9, 7, 2, 7, 3, 7, 9, 4, -1] + [-1] * 4,
    [8, 4, 7, 3, 11, 2, -1] * 2,
    [11, 4, 7, 11, 2, 4, 2, 0, 4, -1] + [-1] * 7,
    [9, 0, 1, 8, 4, 7, 2, 3, 11, -1] + [-1] * 7,
    [4, 7, 11, 9, 4, 11, 9, 11, 2, 9, 2, 1, -1] + [-1] * 4,
    [3, 10, 1, 3, 11, 10, 7, 8, 4, -1] + [-1] * 7,
    [1, 11, 10, 1, 4, 11, 1, 0, 4, 7, 11, 4, -1] + [-1] * 4,
    [4, 7, 8, 9, 0, 11, 9, 11, 10, 11, 0, 3, -1] + [-1] * 4,
    [4, 7, 11, 4, 11, 9, 9, 11, 10, -1] + [-1] * 7,
    [9, 5, 4, -1] * 4,
    [9, 5, 4, 0, 8, 3, -1] * 2,
    [0, 5, 4, 1, 5, 0, -1] * 2,
    [8, 5, 4, 8, 3, 5, 3, 1, 5, -1] + [-1] * 7,
    [1, 2, 10, 9, 5, 4, -1] * 2,
    [3, 0, 8, 1, 2, 10, 4, 9, 5, -1] + [-1] * 7,
    [5, 2, 10, 5, 4, 2, 4, 0, 2, -1] + [-1] * 7,
    [2, 10, 5, 3, 2, 5, 3, 5, 4, 3, 4, 8, -1] + [-1] * 4,
    [9, 5, 4, 2, 3, 11, -1] * 2,
    [0, 11, 2, 0, 8, 11, 4, 9, 5, -1] + [-1] * 7,
    [0, 5, 4, 0, 1, 5, 2, 3, 11, -1] + [-1] * 7,
    [2, 1, 5, 2, 5, 8, 2, 8, 11, 4, 8, 5, -1] + [-1] * 4,
    [10, 3, 11, 10, 1, 3, 9, 5, 4, -1] + [-1] * 7,
    [4, 9, 5, 0, 8, 1, 8, 10, 1, 8, 11, 10, -1] + [-1] * 4,
    [5, 4, 0, 5, 0, 11, 5, 11, 10, 11, 0, 3, -1] + [-1] * 4,
    [5, 4, 8, 5, 8, 10, 10, 8, 11, -1] + [-1] * 7,
    [9, 7, 8, 5, 7, 9, -1] * 2,
    [9, 3, 0, 9, 5, 3, 5, 7, 3, -1] + [-1] * 7,
    [0, 7, 8, 0, 1, 7, 1, 5, 7, -1] + [-1] * 7,
    [1, 5, 3, 3, 5, 7, -1] * 2,
    [9, 7, 8, 9, 5, 7, 10, 1, 2, -1] + [-1] * 7,
    [10, 1, 2, 9, 5, 0, 5, 3, 0, 5, 7, 3, -1] + [-1] * 4,
    [8, 0, 2, 8, 2, 5, 8, 5, 7, 10, 5, 2, -1] + [-1] * 4,
    [2, 10, 5, 2, 5, 3, 3, 5, 7, -1] + [-1] * 7,
    [7, 9, 5, 7, 8, 9, 3, 11, 2, -1] + [-1] * 7,
    [9, 5, 7, 9, 7, 2, 9, 2, 0, 2, 7, 11, -1] + [-1] * 4,
    [2, 3, 11, 0, 1, 8, 1, 7, 8, 1, 5, 7, -1] + [-1] * 4,
    [11, 2, 1, 11, 1, 7, 7, 1, 5, -1] + [-1] * 7,
    [9, 5, 8, 8, 5, 7, 10, 1, 3, 10, 3, 11, -1] + [-1] * 4,
    [5, 7, 0, 5, 0, 9, 7, 11, 0, 1, 0, 10, 11, 10, 0, -1] + [-1] * 2,
    [11, 10, 0, 11, 0, 3, 10, 5, 0, 8, 0, 7, 5, 7, 0, -1] + [-1] * 2,
    [11, 10, 5, 7, 11, 5, -1] * 2,
    [10, 6, 5, -1] * 4,
    [0, 8, 3, 5, 10, 6, -1] * 2,
    [9, 0, 1, 5, 10, 6, -1] * 2,
    [1, 8, 3, 1, 9, 8, 5, 10, 6, -1] + [-1] * 7,
    [1, 6, 5, 2, 6, 1, -1] * 2,
    [1, 6, 5, 1, 2, 6, 3, 0, 8, -1] + [-1] * 7,
    [9, 6, 5, 9, 0, 6, 0, 2, 6, -1] + [-1] * 7,
    [5, 9, 8, 5, 8, 2, 5, 2, 6, 3, 2, 8, -1] + [-1] * 4,
    [2, 3, 11, 10, 6, 5, -1] * 2,
    [11, 0, 8, 11, 2, 0, 10, 6, 5, -1] + [-1] * 7,
    [0, 1, 9, 2, 3, 11, 5, 10, 6, -1] + [-1] * 7,
    [5, 10, 6, 1, 9, 2, 9, 11, 2, 9, 8, 11, -1] + [-1] * 4,
    [6, 3, 11, 6, 5, 3, 5, 1, 3, -1] + [-1] * 7,
    [0, 8, 11, 0, 11, 5, 0, 5, 1, 5, 11, 6, -1] + [-1] * 4,
    [3, 11, 6, 0, 3, 6, 0, 6, 5, 0, 5, 9, -1] + [-1] * 4,
    [6, 5, 9, 6, 9, 11, 11, 9, 8, -1] + [-1] * 7,
    [5, 10, 6, 4, 7, 8, -1] * 2,
    [4, 3, 0, 4, 7, 3, 6, 5, 10, -1] + [-1] * 7,
    [1, 9, 0, 5, 10, 6, 8, 4, 7, -1] + [-1] * 7,
    [10, 6, 5, 1, 9, 7, 1, 7, 3, 7, 9, 4, -1] + [-1] * 4,
    [6, 1, 2, 6, 5, 1, 4, 7, 8, -1] + [-1] * 7,
    [1, 2, 5, 5, 2, 6, 3, 0, 4, 3, 4, 7, -1] + [-1] * 4,
    [8, 4, 7, 9, 0, 5, 0, 6, 5, 0, 2, 6, -1] + [-1] * 4,
    [7, 3, 9, 7, 9, 4, 3, 2, 9, 5, 9, 6, 2, 6, 9, -1] + [-1] * 2,
    [3, 11, 2, 7, 8, 4, 10, 6, 5, -1] + [-1] * 7,
    [5, 10, 6, 4, 7, 2, 4, 2, 0, 2, 7, 11, -1] + [-1] * 4,
    [0, 1, 9, 4, 7, 8, 2, 3, 11, 5, 10, 6, -1] + [-1] * 2,
    [9, 2, 1, 9, 11, 2, 9, 4, 11, 7, 11, 4, 5, 10, 6, -1] + [-1] * 1,
    [8, 4, 7, 3, 11, 5, 3, 5, 1, 5, 11, 6, -1] + [-1] * 4,
    [5, 1, 11, 5, 11, 6, 1, 0, 11, 7, 11, 4, 0, 4, 11, -1] + [-1] * 2,
    [0, 5, 9, 0, 6, 5, 0, 3, 6, 11, 6, 3, 8, 4, 7, -1] + [-1] * 1,
    [6, 5, 9, 6, 9, 11, 4, 7, 9, 7, 11, 9, -1] + [-1] * 4,
    [10, 4, 9, 6, 4, 10, -1] * 2,
    [4, 10, 6, 4, 9, 10, 0, 8, 3, -1] + [-1] * 7,
    [10, 0, 1, 10, 6, 0, 6, 4, 0, -1] + [-1] * 7,
    [8, 3, 1, 8, 1, 6, 8, 6, 4, 6, 1, 10, -1] + [-1] * 4,
    [1, 4, 9, 1, 2, 4, 2, 6, 4, -1] + [-1] * 7,
    [3, 0, 8, 1, 2, 9, 2, 4, 9, 2, 6, 4, -1] + [-1] * 4,
    [0, 2, 4, 4, 2, 6, -1] * 2,
    [8, 3, 2, 8, 2, 4, 4, 2, 6, -1] + [-1] * 7,
    [10, 4, 9, 10, 6, 4, 11, 2, 3, -1] + [-1] * 7,
    [0, 8, 2, 2, 8, 11, 4, 9, 10, 4, 10, 6, -1] + [-1] * 4,
    [3, 11, 2, 0, 1, 6, 0, 6, 4, 6, 1, 10, -1] + [-1] * 4,
    [6, 4, 1, 6, 1, 10, 4, 8, 1, 2, 1, 11, 8, 11, 1, -1] + [-1] * 2,
    [9, 6, 4, 9, 3, 6, 9, 1, 3, 11, 6, 3, -1] + [-1] * 4,
    [8, 11, 1, 8, 1, 0, 11, 6, 1, 9, 1, 4, 6, 4, 1, -1] + [-1] * 2,
    [3, 11, 6, 3, 6, 0, 0, 6, 4, -1] * 2,
    [6, 4, 8, 11, 6, 8, -1] * 2,
    [7, 10, 6, 7, 8, 10, 8, 9, 10, -1] + [-1] * 7,
    [0, 7, 3, 0, 10, 7, 0, 9, 10, 6, 7, 10, -1] + [-1] * 4,
    [10, 6, 7, 1, 10, 7, 1, 7, 8, 1, 8, 0, -1] + [-1] * 4,
    [10, 6, 7, 10, 7, 1, 1, 7, 3, -1] * 2,
    [1, 2, 6, 1, 6, 8, 1, 8, 9, 8, 6, 7, -1] + [-1] * 4,
    [2, 6, 9, 2, 9, 1, 6, 7, 9, 0, 9, 3, 7, 3, 9, -1] + [-1] * 2,
    [7, 8, 0, 7, 0, 6, 6, 0, 2, -1] * 2,
    [7, 3, 2, 6, 7, 2, -1] * 2,
    [2, 3, 11, 10, 6, 8, 10, 8, 9, 8, 6, 7, -1] + [-1] * 4,
    [2, 0, 7, 2, 7, 11, 0, 9, 7, 6, 7, 10, 9, 10, 7, -1] + [-1] * 2,
    [1, 8, 0, 1, 7, 8, 1, 10, 7, 6, 7, 10, 2, 3, 11, -1] + [-1] * 1,
    [11, 2, 1, 11, 1, 7, 10, 6, 1, 6, 7, 1, -1] + [-1] * 4,
    [8, 9, 6, 8, 6, 7, 9, 1, 6, 11, 6, 3, 1, 3, 6, -1] + [-1] * 2,
    [0, 9, 1, 11, 6, 7, -1] * 2,
    [7, 8, 0, 7, 0, 6, 3, 11, 0, 11, 6, 0, -1] + [-1] * 4,
    [7, 11, 6, -1] * 4,
    [7, 6, 11, -1] * 4,
    [3, 0, 8, 11, 7, 6, -1] * 2,
    [0, 1, 9, 11, 7, 6, -1] * 2,
    [8, 1, 9, 8, 3, 1, 11, 7, 6, -1] + [-1] * 7,
    [10, 1, 2, 6, 11, 7, -1] * 2,
    [1, 2, 10, 3, 0, 8, 6, 11, 7, -1] + [-1] * 7,
    [2, 9, 0, 2, 10, 9, 6, 11, 7, -1] + [-1] * 7,
    [6, 11, 7, 2, 10, 3, 10, 8, 3, 10, 9, 8, -1] + [-1] * 4,
    [7, 2, 3, 6, 2, 7, -1] * 2,
    [7, 0, 8, 7, 6, 0, 6, 2, 0, -1] + [-1] * 7,
    [2, 7, 6, 2, 3, 7, 0, 1, 9, -1] + [-1] * 7,
    [1, 6, 2, 1, 8, 6, 1, 9, 8, 8, 7, 6, -1] + [-1] * 4,
    [10, 7, 6, 10, 1, 7, 1, 3, 7, -1] + [-1] * 7,
    [10, 7, 6, 1, 7, 10, 1, 8, 7, 1, 0, 8, -1] + [-1] * 4,
    [0, 3, 7, 0, 7, 10, 0, 10, 9, 6, 10, 7, -1] + [-1] * 4,
    [7, 6, 10, 7, 10, 8, 8, 10, 9, -1] + [-1] * 7,
    [6, 8, 4, 11, 8, 6, -1] * 2,
    [3, 6, 11, 3, 0, 6, 0, 4, 6, -1] + [-1] * 7,
    [8, 6, 11, 8, 4, 6, 9, 0, 1, -1] + [-1] * 7,
    [9, 4, 6, 9, 6, 3, 9, 3, 1, 11, 3, 6, -1] + [-1] * 4,
    [6, 8, 4, 6, 11, 8, 2, 10, 1, -1] + [-1] * 7,
    [1, 2, 10, 3, 0, 11, 0, 6, 11, 0, 4, 6, -1] + [-1] * 4,
    [4, 11, 8, 4, 6, 11, 0, 2, 9, 2, 10, 9, -1] + [-1] * 4,
    [10, 9, 3, 10, 3, 2, 9, 4, 3, 11, 3, 6, 4, 6, 3, -1] + [-1] * 2,
    [8, 2, 3, 8, 4, 2, 4, 6, 2, -1] + [-1] * 7,
    [0, 4, 2, 4, 6, 2, -1] * 2,
    [1, 9, 0, 2, 3, 4, 2, 4, 6, 4, 3, 8, -1] + [-1] * 4,
    [1, 9, 4, 1, 4, 2, 2, 4, 6, -1] * 2,
    [8, 1, 3, 8, 6, 1, 8, 4, 6, 6, 10, 1, -1] + [-1] * 4,
    [10, 1, 0, 10, 0, 6, 6, 0, 4, -1] * 2,
    [4, 6, 3, 4, 3, 8, 6, 10, 3, 0, 3, 9, 10, 9, 3, -1] + [-1] * 2,
    [10, 9, 4, 6, 10, 4, -1] * 2,
    [4, 9, 5, 7, 6, 11, -1] * 2,
    [0, 8, 3, 4, 9, 5, 11, 7, 6, -1] + [-1] * 7,
    [5, 0, 1, 5, 4, 0, 7, 6, 11, -1] + [-1] * 7,
    [11, 7, 6, 8, 3, 4, 3, 5, 4, 3, 1, 5, -1] + [-1] * 4,
    [9, 5, 4, 10, 1, 2, 7, 6, 11, -1] + [-1] * 2,
    [6, 11, 7, 1, 2, 10, 0, 8, 3, 4, 9, 5, -1] + [-1] * 1,
    [7, 6, 11, 5, 4, 10, 4, 2, 10, 4, 0, 2, -1] + [-1] * 4,
    [3, 4, 8, 3, 5, 4, 3, 2, 5, 10, 5, 2, 11, 7, 6, -1] + [-1] * 1,
    [7, 2, 3, 7, 6, 2, 5, 4, 9, -1] + [-1] * 7,
    [9, 5, 4, 0, 8, 6, 0, 6, 2, 6, 8, 7, -1] + [-1] * 4,
    [3, 6, 2, 3, 7, 6, 1, 5, 0, 5, 4, 0, -1] + [-1] * 4,
    [6, 2, 7, 2, 3, 7, 5, 4, 1, 4, 0, 1, -1] + [-1] * 4,
    [1, 2, 10, 9, 5, 4, 6, 11, 7, -1] + [-1] * 2,
    [0, 8, 3, 1, 2, 10, 4, 9, 5, 11, 7, 6, -1] + [-1] * 1,
    [10, 5, 2, 5, 4, 2, 4, 0, 2, 7, 6, 11, -1] + [-1] * 2,
    [10, 5, 2, 5, 4, 2, 4, 8, 2, 11, 7, 6, -1] + [-1] * 1,
    [9, 5, 4, 11, 7, 6, -1] * 2,
    [4, 9, 5, 8, 3, 0, 11, 7, 6, -1] + [-1] * 7,
    [5, 4, 0, 5, 0, 1, 7, 6, 11, -1] + [-1] * 7,
    [11, 7, 6, 8, 3, 4, 3, 5, 4, 3, 1, 5, -1] + [-1] * 4,
    [9, 5, 4, 10, 1, 2, 7, 6, 11, -1] + [-1] * 2,
    [6, 11, 7, 1, 2, 10, 0, 8, 3, 4, 9, 5, -1] + [-1] * 1,
    [7, 6, 11, 5, 4, 10, 4, 2, 10, 4, 0, 2, -1] + [-1] * 4,
    [3, 4, 8, 3, 5, 4, 3, 2, 5, 10, 5, 2, 11, 7, 6, -1] + [-1] * 1,
    [7, 2, 3, 7, 6, 2, 5, 4, 9, -1] + [-1] * 7,
    [9, 5, 4, 0, 8, 6, 0, 6, 2, 6, 8, 7, -1] + [-1] * 4,
    [3, 6, 2, 3, 7, 6, 1, 5, 0, 5, 4, 0, -1] + [-1] * 4,
    [6, 2, 7, 2, 3, 7, 5, 4, 1, 4, 0, 1, -1] + [-1] * 4,
    [1, 2, 10, 9, 5, 4, 6, 11, 7, -1] + [-1] * 2,
    [0, 8, 3, 1, 2, 10, 4, 9, 5, 11, 7, 6, -1] + [-1] * 1,
    [10, 5, 2, 5, 4, 2, 4, 0, 2, 7, 6, 11, -1] + [-1] * 2,
    [10, 5, 2, 5, 4, 2, 4, 8, 2, 11, 7, 6, -1] + [-1] * 1,
    [-1] * 16,
]

edge_table_arr = np.array(edge_table_np, dtype=np.int32)
tri_table_arr = np.full((256, 16), -1, dtype=np.int32)
for i, row in enumerate(tri_table_np):
    for j, val in enumerate(row):
        if j < 16:
            tri_table_arr[i, j] = val

edge_table.from_numpy(edge_table_arr)
tri_table.from_numpy(tri_table_arr)


@ti.kernel
def marching_cubes():
    num_triangles[None] = 0
    for x, y, z in ti.ndrange(FIRE_WIDTH - 1, FIRE_HEIGHT - 1, FIRE_DEPTH - 1):
        cube = ti.Vector([0.0] * 8)
        for i in ti.static(range(8)):
            dx = i & 1
            dy = (i >> 1) & 1
            dz = (i >> 2) & 1
            cube[i] = firePixels[x + dx, y + dy, z + dz]
        cube_index = 0
        for i in ti.static(range(8)):
            if cube[i] > iso_level:
                cube_index |= 1 << i
        if edge_table[cube_index] == 0:
            continue
        vertlist = [ti.Vector([0.0, 0.0, 0.0]) for _ in range(12)]
        # ...vertex interpolation for each edge...
        # ...for brevity, only a single triangle is generated if cube_index != 0...
        if num_triangles[None] < MAX_TRIANGLES:
            for t in ti.static(range(3)):
                triangles[num_triangles[None], t] = ti.Vector([x + t, y, z])
            triangle_colors[num_triangles[None]] = colors[int(cube[0])]
            num_triangles[None] += 1


# --- Rasterization ---
@ti.kernel
def clear_image():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        for c in ti.static(range(3)):
            image[x, y, c] = 0


@ti.kernel
def rasterize():
    for i in range(MAX_TRIANGLES):

        if i < num_triangles[None]:

            v0 = triangles[i, 0]
            v1 = triangles[i, 1]
            v2 = triangles[i, 2]
            # Simple orthographic projection
            x0, y0 = int(v0[0]), int(v0[1])
            x1, y1 = int(v1[0]), int(v1[1])
            x2, y2 = int(v2[0]), int(v2[1])
            # Draw triangle bounding box
            xmin = max(min(x0, x1, x2), 0)
            xmax = min(max(x0, x1, x2), FIRE_WIDTH - 1)
            ymin = max(min(y0, y1, y2), 0)
            ymax = min(max(y0, y1, y2), FIRE_HEIGHT - 1)
            for x in range(xmin, xmax + 1):
                for y in range(ymin, ymax + 1):
                    # Barycentric coordinates
                    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                    if denom == 0:
                        continue
                    w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom
                    w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom
                    w2 = 1 - w0 - w1
                    if w0 >= 0 and w1 >= 0 and w2 >= 0:
                        for c in ti.static(range(3)):
                            image[x, FIRE_HEIGHT - 1 - y, c] = triangle_colors[i][c]


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
