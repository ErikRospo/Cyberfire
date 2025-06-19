from enum import Enum, auto
from typing import Optional
from core import change_heat_at_position, highlight_fixed_pixels, set_fixed_pixels


class ToolType(Enum):
    FIRE_BRUSH = auto()
    FIRE_ERASE = auto()
    FIX_BRUSH = auto()
    FIX_ERASE = auto()
    HIGHLIGHT_FIXED = auto()


class Tool:
    registry = {}
    tool_type:Optional[ToolType]
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

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=1)


class FireEraseTool(Tool):
    tool_type = ToolType.FIRE_ERASE

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=-1)


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
