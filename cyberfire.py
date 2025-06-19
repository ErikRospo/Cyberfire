import time
import taichi as ti

from constants import DECAY_MULT, FIRE_HEIGHT, FIRE_WIDTH, MAX_INTENSITY, ADD_MULT
from palettes import (
    palette_fire,
    palette_cyber,
    palette_gray,
    palette_cold_fire,
    palette_sunset,
    palette_toxic,
    palette_electric,
)

ti.init(arch=ti.gpu)

# Fire simulation field: (width, height)
firePixels = ti.field(dtype=ti.i32, shape=(FIRE_WIDTH, FIRE_HEIGHT))
fixedPixels=ti.field(dtype=ti.i32,shape=(FIRE_WIDTH,FIRE_HEIGHT))
# Image: (width, height, 3)
image = ti.field(dtype=ti.u8, shape=(FIRE_WIDTH, FIRE_HEIGHT, 3))
# Color palette
colors = ti.Vector.field(3, dtype=ti.u8, shape=(MAX_INTENSITY + 1))


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


@ti.func
def lerp(a, b, t):
    return a * (1 - t) + b * t


@ti.func
def fade(t):
    # Perlin's fade function
    return t * t * t * (t * (t * 6 - 15) + 10)


@ti.func
def grad(hash, x, y, z):
    # Gradient directions for 3D Perlin noise
    h = hash & 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if (h == 12 or h == 14) else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


@ti.func
def permute(x):
    # Simple permutation function for hashing
    return ((34 * x + 1) * x) % 289


@ti.func
def perlin_noise(x, y, z):
    # Find unit cube that contains point
    X = int(ti.floor(x)) & 255
    Y = int(ti.floor(y)) & 255
    Z = int(ti.floor(z)) & 255

    # Find relative x, y, z of point in cube
    xf = x - ti.floor(x)
    yf = y - ti.floor(y)
    zf = z - ti.floor(z)

    # Compute fade curves for each of x, y, z
    u = fade(xf)
    v = fade(yf)
    w = fade(zf)

    # Hash coordinates of the 8 cube corners
    A = permute(X) + Y
    AA = permute(A) + Z
    AB = permute(A + 1) + Z
    B = permute(X + 1) + Y
    BA = permute(B) + Z
    BB = permute(B + 1) + Z

    # Calculate gradients and dot products for each corner
    n000 = grad(int(permute(AA)), xf, yf, zf)
    n100 = grad(int(permute(BA)), xf - 1.0, yf, zf)
    n010 = grad(int(permute(AB)), xf, yf - 1.0, zf)
    n110 = grad(int(permute(BB)), xf - 1.0, yf - 1.0, zf)
    n001 = grad(int(permute(AA + 1)), xf, yf, zf - 1.0)
    n101 = grad(int(permute(BA + 1)), xf - 1.0, yf, zf - 1.0)
    n011 = grad(int(permute(AB + 1)), xf, yf - 1.0, zf - 1.0)
    n111 = grad(int(permute(BB + 1)), xf - 1.0, yf - 1.0, zf - 1.0)

    # Interpolate
    x1 = lerp(n000, n100, u)
    x2 = lerp(n010, n110, u)
    y1 = lerp(x1, x2, v)

    x3 = lerp(n001, n101, u)
    x4 = lerp(n011, n111, u)
    y2 = lerp(x3, x4, v)

    return (lerp(y1, y2, w) + 1) * 0.5  # Normalize to [0,1]


@ti.func
def spread_fire(x: int, y: int, time: float):
    if y < FIRE_HEIGHT - 1:
        offset = int(ti.random() * 3 + 1)
        sample_y = ti.min(y + offset, FIRE_HEIGHT - 1)
        below_intensity = firePixels[x, sample_y]

        # Use 3D Perlin noise instead of value noise
        offset_noise = perlin_noise(x * 0.05 + time, y * 0.05 + time, time * 0.5)
        rand_offset = int(offset_noise * 5.0) - 2  # [-2, 2]

        dst_x = ti.math.clamp(x + rand_offset, 0, FIRE_WIDTH - 1)
        decay = int(ti.random() * DECAY_MULT) + 1
        rand_intensity = int(ti.random() * ADD_MULT)
        new_intensity = ti.max(0, below_intensity - decay + rand_intensity)
        if fixedPixels[dst_x,y]==0:
            firePixels[dst_x, y] = new_intensity
    


@ti.kernel
def do_fire(time: float):
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT - 1):
        spread_fire(x, y, time)


@ti.kernel
def change_heat_at_position(mx: int, my: int, radius: int, multiplier: int):
    for dx, dy in ti.ndrange((-radius, radius), (-radius, radius)):
        x = mx + dx
        y = my + dy
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                # Add intensity falloff based on distance (optional)
                delta = int(MAX_INTENSITY * (1 - dist / radius)) * multiplier
                firePixels[x, y] = ti.min(MAX_INTENSITY, firePixels[x, y] + delta)
@ti.kernel
def set_fixed_pixels(mx: int, my: int, radius: int,state:int):
    for dx, dy in ti.ndrange((-radius, radius), (-radius, radius)):
        x = mx + dx
        y = my + dy
        if 0 <= x < FIRE_WIDTH and 0 <= y < FIRE_HEIGHT:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                fixedPixels[x,y]=state

@ti.kernel
def update_image():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        intensity = ti.min(MAX_INTENSITY, ti.max(0, firePixels[x, y]))
        for c in ti.static(range(3)):
            image[x, FIRE_HEIGHT - 1 - y, c] = colors[intensity][c]


@ti.kernel
def initialize_fire():
    for x in range(FIRE_WIDTH):
        firePixels[x, FIRE_HEIGHT - 1] = MAX_INTENSITY  # Bottom row

@ti.kernel
def clear_fixed_pixels():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        fixedPixels[x,y]=0
        
class Tool:
    def __init__(self, name):
        self.name = name
        self.active = False

    def trigger_on(self):
        self.active = True

    def trigger_off(self):
        self.active = False

    def is_active(self):
        return self.active

    def apply(self, *args, **kwargs):
        pass

class FireBrushTool(Tool):
    def __init__(self):
        super().__init__("Fire Paint")

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=1)

class FireEraseTool(Tool):
    def __init__(self):
        super().__init__("Fire Erase")

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=-1)

class FixBrushTool(Tool):
    def __init__(self):
        super().__init__("Fix Brush")

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 1)

class FixEraseTool(Tool):
    def __init__(self):
        super().__init__("Fix Erase")

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 0)

class HighlightFixedTool(Tool):
    def __init__(self):
        super().__init__("Highlight Fixed")

    def apply(self):
        highlight_fixed_pixels()

@ti.kernel
def highlight_fixed_pixels():
    for x, y in ti.ndrange(FIRE_WIDTH, FIRE_HEIGHT):
        if fixedPixels[x, y] == 1:
            # Cyan: R=0, G=255, B=255
            image[x, FIRE_HEIGHT - 1 - y, 0] = 0
            image[x, FIRE_HEIGHT - 1 - y, 1] = 255
            image[x, FIRE_HEIGHT - 1 - y, 2] = 255


def main():
    current_time = 0
    mx = 0.5
    my = 0.5
    initialize_fire()
    palette_idx = 0
    palette_functions = [
        initialize_palette_fire,
        initialize_palette_cyber,
        initialize_palette_gray,
        initialize_palette_cold_fire,
        initialize_palette_sunset,
        initialize_palette_toxic,
        initialize_palette_electric,
    ]

    palette_functions[palette_idx]()
    gui = ti.GUI("Fire Effect", res=(FIRE_WIDTH, FIRE_HEIGHT))  # type: ignore
    brush_radius = 25  # Initial brush radius
    brush_changed = time.time() - 10

    # Tool instances
    tools = {
        "fire_brush": FireBrushTool(),
        "fire_erase": FireEraseTool(),
        "fix_brush": FixBrushTool(),
        "fix_erase": FixEraseTool(),
        "highlight_fixed": HighlightFixedTool(),
    }

    while gui.running:
        current_time += 0.05

        do_fire(current_time)
        for event in gui.get_events():
            if event.key == ti.GUI.LMB:
                if event.type == ti.GUI.PRESS:
                    tools["fire_brush"].trigger_on()
                    tools["fire_erase"].trigger_off()
                    brush_changed = 0
                if event.type == ti.GUI.RELEASE:
                    tools["fire_brush"].trigger_off()
            if event.key == ti.GUI.RMB:
                if event.type == ti.GUI.PRESS:
                    tools["fire_erase"].trigger_on()
                    tools["fire_brush"].trigger_off()
                    brush_changed = 0
                if event.type == ti.GUI.RELEASE:
                    tools["fire_erase"].trigger_off()
            if event.key == "f":
                if event.type == ti.GUI.PRESS:
                    tools["fix_brush"].trigger_on()
                    tools["fix_erase"].trigger_off()
                    brush_changed = 0
                if event.type == ti.GUI.RELEASE:
                    tools["fix_brush"].trigger_off()
            if event.key == "u":
                if event.type == ti.GUI.PRESS:
                    tools["fix_erase"].trigger_on()
                    tools["fix_brush"].trigger_off()
                    brush_changed = 0
                if event.type == ti.GUI.RELEASE:
                    tools["fix_erase"].trigger_off()
            if event.key == "v":
                if event.type == ti.GUI.PRESS:
                    if tools["highlight_fixed"].is_active():
                        tools["highlight_fixed"].trigger_off()
                    else:
                        tools["highlight_fixed"].trigger_on()
            if event.key == ti.GUI.WHEEL:
                now = time.time()
                if now - brush_changed < 0.5:
                    accel = 1 / (now - brush_changed + 0.25)
                else:
                    accel = 1
                brush_radius += int(event.delta[1] * accel / 32)
                brush_radius = max(1, min(brush_radius, 400))
                brush_changed = now
            if event.key == "p" and event.type == ti.GUI.PRESS:
                palette_idx += 1
                palette_idx %= len(palette_functions)
                palette_functions[palette_idx]()
                print(
                    palette_functions[palette_idx]
                    .__name__.replace("initialize_palette_", "")
                    .capitalize()
                    .replace("_", " ")
                )
            if event.key == "r" and event.type == ti.GUI.PRESS:
                firePixels.fill(0)
                initialize_fire()
                clear_fixed_pixels()

        mx, my = gui.get_cursor_pos()
        mx_int = int(mx * FIRE_WIDTH)
        my_int = int((1 - my) * FIRE_HEIGHT)

        # Apply active tools
        for name, tool in tools.items():
            if tool.is_active():
                if name == "highlight_fixed":
                    tool.apply()
                else:
                    tool.apply(mx_int, my_int, brush_radius)

        update_image()
        # Highlight fixed pixels after updating the image if the tool is active
        if tools["highlight_fixed"].is_active():
            highlight_fixed_pixels()

        gui.set_image(image)
        if (time.time() - brush_changed) < 2:
            t = min(1.0, (time.time() - brush_changed) / 2.0)
            base_rgb = [0x50, 0x50, 0x50]
            r,g,b = [int(v * (1 - t)) for v in base_rgb]
            color = (r << 16) | (g << 8) | b
            gui.circle([mx, my], color=color, radius=brush_radius)
            
        gui.show()

if __name__ == "__main__":
    main()
