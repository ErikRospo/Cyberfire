import numpy as np
import taichi as ti

from constants import (ADD_MULT, DECAY_MULT, FIRE_DEPTH, FIRE_HEIGHT,
                       FIRE_WIDTH, MAX_INTENSITY)
from mc_constants import edge_table_np, tri_table_np
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

proj = ti.field(dtype=ti.i32, shape=(3,2))

@ti.kernel
def rasterize(yaw: float, pitch: float, distance: float):
    # Camera parameters
    cx = FIRE_WIDTH / 2
    cy = FIRE_HEIGHT / 2
    cz = FIRE_DEPTH / 2
    fov = 1.2  # radians, for perspective
    aspect = FIRE_WIDTH / FIRE_HEIGHT
    for i in range(MAX_TRIANGLES):
        if i < num_triangles[None]:
            v0 = triangles[i, 0]
            v1 = triangles[i, 1]
            v2 = triangles[i, 2]
            verts = ti.Matrix.rows([v0, v1, v2])
            for idx in ti.static(range(3)):
                # Center
                x = verts[idx, 0] - cx
                y = verts[idx, 1] - cy
                z = verts[idx, 2] - cz
                # Rotate around Y (yaw)
                xz = x * ti.cos(yaw) - z * ti.sin(yaw)
                zz = x * ti.sin(yaw) + z * ti.cos(yaw)
                x, z = xz, zz
                # Rotate around X (pitch)
                yz = y * ti.cos(pitch) - z * ti.sin(pitch)
                zz = y * ti.sin(pitch) + z * ti.cos(pitch)
                y, z = yz, zz
                # Move camera back
                z += distance * max(FIRE_WIDTH, FIRE_HEIGHT, FIRE_DEPTH)
                # Perspective projection
                px = x / (z * ti.tan(fov / 2) + 1e-5) * aspect
                py = y / (z * ti.tan(fov / 2) + 1e-5)
                # Map to image coordinates
                sx = int((px + 0.5) * FIRE_WIDTH)
                sy = int((py + 0.5) * FIRE_HEIGHT)
                proj[0, idx] = sx
                proj[1, idx] = sy
            x0, y0 = proj[0, 0], proj[1, 0]
            x1, y1 = proj[0, 1], proj[1, 1]
            x2, y2 = proj[0, 2], proj[1, 2]
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
