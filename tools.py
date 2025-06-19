from enum import Enum, auto
from typing import Optional

from core import (change_heat_at_position, fire_rectangle,
                  highlight_fixed_pixels, set_fixed_pixels)


class ToolType(Enum):
    FIRE_BRUSH = auto()
    FIRE_ERASE = auto()
    FIX_BRUSH = auto()
    FIX_ERASE = auto()
    HIGHLIGHT_FIXED = auto()
    FIRE_LINE = auto()  # New tool type
    FIRE_RECT = auto()  # Rectangle fire tool


class Tool:
    registry = {}
    tool_type: Optional[ToolType]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "tool_type"):
            Tool.registry[cls.tool_type] = cls

    def __init__(self):
        self.active = False

    def trigger_on(self):
        self.active = True

    def trigger_off(self):
        self.active = False

    def is_active(self):
        return self.active

    def apply(self, *args, **kwargs):
        raise NotImplementedError("Tool subclasses must implement apply()")


class FireBrushTool(Tool):
    tool_type = ToolType.FIRE_BRUSH

    def apply(self, mx_int, my_int, brush_radius, intensity:float=1):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=intensity)
class FireEraseTool(Tool):
    tool_type = ToolType.FIRE_ERASE

    def apply(self, mx_int, my_int, brush_radius, intensity:float=1):

        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=-intensity)


class FixBrushTool(Tool):
    tool_type = ToolType.FIX_BRUSH

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 1)


class FixEraseTool(Tool):
    tool_type = ToolType.FIX_ERASE

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 0)


class HighlightFixedTool(Tool):
    tool_type = ToolType.HIGHLIGHT_FIXED

    def apply(self, _mx_int, _my_int, _brush_radius):
        highlight_fixed_pixels()


class FireLineTool(Tool):
    tool_type = ToolType.FIRE_LINE

    def __init__(self):
        super().__init__()
        self.first_point = None

    def set_first_point(self, mx_int, my_int):
        self.first_point = (mx_int, my_int)

    def clear_first_point(self):
        self.first_point = None

    def apply(self, mx_int: int, my_int: int, brush_radius, intensity:float=1):
        # Only draw if first_point is set and this is the second click
        if self.first_point is not None:
            x0, y0 = self.first_point
            x1, y1 = mx_int, my_int

            # Bresenham's line algorithm
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            x, y = x0, y0
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            if dx > dy:
                err = dx // 2
                while x != x1:
                    change_heat_at_position(x, y, radius=brush_radius, multiplier=intensity)
                    err -= dy
                    if err < 0:
                        y += sy
                        err += dx
                    x += sx
                change_heat_at_position(x, y, radius=brush_radius, multiplier=intensity)
            else:
                err = dy // 2
                while y != y1:
                    change_heat_at_position(x, y, radius=brush_radius, multiplier=intensity)
                    err -= dx
                    if err < 0:
                        x += sx
                        err += dy
                    y += sy
                change_heat_at_position(x, y, radius=brush_radius, multiplier=intensity)
            self.clear_first_point()


class FireRectTool(Tool):
    tool_type = ToolType.FIRE_RECT

    def __init__(self):
        super().__init__()
        self.first_point = None

    def set_first_point(self, mx_int: int, my_int: int):
        self.first_point = (mx_int, my_int)

    def clear_first_point(self):
        self.first_point = None

    def apply(self, mx_int: int, my_int: int, _brush_radius: int, intensity:float=1):
        # Only draw if first_point is set and this is the second click
        if self.first_point is not None:
            x0, y0 = self.first_point
            x1, y1 = mx_int, my_int
            xmin, xmax = sorted([x0, x1])
            ymin, ymax = sorted([y0, y1])
            # Draw the rectangle with intensity percent
            for x in range(xmin, xmax + 1):
                for y in range(ymin, ymax + 1):
                    change_heat_at_position(x, y, radius=1, multiplier=intensity)
            self.clear_first_point()
