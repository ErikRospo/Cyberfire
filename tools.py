from core import (
    change_heat_at_position,
    set_fixed_pixels,
    highlight_fixed_pixels,
)


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

    def apply(self, _mx_int, _my_int, _brush_radius):
        highlight_fixed_pixels()
