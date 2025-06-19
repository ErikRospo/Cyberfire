import taichi as ti

from constants import (ADD_MULT, DECAY_MULT, FIRE_HEIGHT, FIRE_WIDTH,
                       MAX_INTENSITY)
from palettes import (palette_cold_fire, palette_cyber, palette_electric,
                      palette_fire, palette_gray, palette_sunset,
                      palette_toxic)

ti.init(arch=ti.gpu)

# Fire simulation field: (width, height)
firePixels = ti.field(dtype=ti.i32, shape=(FIRE_WIDTH, FIRE_HEIGHT))
fixedPixels = ti.field(dtype=ti.i32, shape=(FIRE_WIDTH, FIRE_HEIGHT))
# Image: (width, height, 3)
image = ti.field(dtype=ti.u8, shape=(FIRE_WIDTH, FIRE_HEIGHT, 3))
# Color palette
colors = ti.Vector.field(3, dtype=ti.u8, shape=(MAX_INTENSITY + 1))

# Palette management


def set_palette(palette_func):
    palette = palette_func()
    for i in range(MAX_INTENSITY + 1):
        colors[i] = palette[i]


def initialize_palette_fire():
    set_palette(palette_fire)


def initialize_palette_cyber():
    set_palette(palette_cyber)


def initialize_palette_gray():
    set_palette(palette_gray)


def initialize_palette_cold_fire():
    set_palette(palette_cold_fire)


def initialize_palette_sunset():
    set_palette(palette_sunset)


def initialize_palette_toxic():
    set_palette(palette_toxic)


def initialize_palette_electric():
    set_palette(palette_electric)


# Perlin noise and fire spread
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
def spread_fire(x: int, y: int, time: float):
    if y < FIRE_HEIGHT - 1:
        offset = int(ti.random() * 3 + 1)
        sample_y = ti.min(y + offset, FIRE_HEIGHT - 1)
        below_intensity = firePixels[x, sample_y]
        offset_noise = perlin_noise(x * 0.05 + time, y * 0.05 + time, time * 0.5)
        rand_offset = int(offset_noise * 5.0) - 2
        dst_x = ti.math.clamp(x + rand_offset, 0, FIRE_WIDTH - 1)
        decay = int(ti.random() * DECAY_MULT) + 1
        rand_intensity = int(ti.random() * ADD_MULT)
        new_intensity = ti.max(0, below_intensity - decay + rand_intensity)
        if fixedPixels[dst_x, y] == 0:
            firePixels[dst_x, y] = new_intensity


@ti.kernel
def do_fire(time: float):
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT - 1):
        spread_fire(x, y, time)


@ti.kernel
def change_heat_at_position(mx: int, my: int, radius: int, multiplier: float):
    for dx, dy in ti.ndrange((-radius, radius), (-radius, radius)):
        x = mx + dx
        y = my + dy
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                delta = int(MAX_INTENSITY * (1 - dist / radius) * multiplier*multiplier)
                firePixels[x, y] = ti.min(MAX_INTENSITY, firePixels[x, y] + delta)


@ti.kernel
def set_fixed_pixels(mx: int, my: int, radius: int, state: int):
    for dx, dy in ti.ndrange((-radius, radius), (-radius, radius)):
        x = mx + dx
        y = my + dy
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                fixedPixels[x, y] = state


@ti.kernel
def update_image():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        intensity = ti.min(MAX_INTENSITY, ti.max(0, firePixels[x, y]))
        for c in ti.static(range(3)):
            image[x, FIRE_HEIGHT - 1 - y, c] = colors[intensity][c]


@ti.kernel
def initialize_fire():
    for x in range(FIRE_WIDTH):
        firePixels[x, FIRE_HEIGHT - 1] = MAX_INTENSITY


@ti.kernel
def clear_fixed_pixels():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        fixedPixels[x, y] = 0


@ti.kernel
def highlight_fixed_pixels():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        if fixedPixels[x, y] == 1:
            image[x, FIRE_HEIGHT - 1 - y, 0] = 0
            image[x, FIRE_HEIGHT - 1 - y, 1] = 255
            image[x, FIRE_HEIGHT - 1 - y, 2] = 255


@ti.kernel
def render_tool_radius(mx: int, my: int, brush_radius: int, alpha: int):
    rad_squared = brush_radius * brush_radius
    for dx, dy in ti.ndrange(
        (-brush_radius, brush_radius + 1), (-brush_radius, brush_radius + 1)
    ):
        x = mx + dx
        y = my + dy
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT:
            sq_dist = dx * dx + dy * dy
            if sq_dist <= rad_squared:
                for c in ti.static(range(3)):
                    orig = image[x, y, c]
                    grey = 128
                    blended = (orig * (255 - alpha) + grey * alpha) // 255
                    image[x, y, c] = blended


@ti.kernel
def fire_rectangle(xmin: int, xmax: int, ymin: int, ymax: int):
    for x, y in ti.ndrange((xmin, xmax + 1), (ymin, ymax + 1)):
        firePixels[x, y] = MAX_INTENSITY
