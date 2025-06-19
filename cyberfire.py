import time
import taichi as ti
from core import (
    firePixels, image,
    do_fire, update_image, initialize_fire, clear_fixed_pixels,
    highlight_fixed_pixels,
    initialize_palette_fire, initialize_palette_cyber, initialize_palette_gray,
    initialize_palette_cold_fire, initialize_palette_sunset, initialize_palette_toxic, initialize_palette_electric,
    FIRE_WIDTH, FIRE_HEIGHT
)
from tools import FireBrushTool, FireEraseTool, FixBrushTool, FixEraseTool, HighlightFixedTool

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
                delta_y = event.delta[1] if event.delta is not None else 0
                if now - brush_changed < 0.5:
                    accel = 1 / (now - brush_changed + 0.25)
                else:
                    accel = 1
                brush_radius += int(delta_y * accel / 32)
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
        for name, tool in tools.items():
            if tool.is_active():
                tool.apply(mx_int, my_int, brush_radius)
        update_image()
        if tools["highlight_fixed"].is_active():
            highlight_fixed_pixels()
        gui.set_image(image)
        if (time.time() - brush_changed) < 2:
            t = min(1.0, (time.time() - brush_changed) / 2.0)
            base_rgb = [0x50, 0x50, 0x50]
            r, g, b = [int(v * (1 - t)) for v in base_rgb]
            color = (r << 16) | (g << 8) | b
            gui.circle([mx, my], color=color, radius=brush_radius)
        gui.show()

if __name__ == "__main__":
    main()
