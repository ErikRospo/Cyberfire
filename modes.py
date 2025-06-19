from enum import Enum, auto

from tools import ToolType


class ModeType(Enum):
    FIRE = auto()
    FIX = auto()
    FIRE_LINE = auto()
    FIRE_RECT = auto()
    FIX_RECT = auto()


class Mode:
    def __init__(self, lmb_tool_type, rmb_tool_type):
        self.lmb_tool_type = lmb_tool_type
        self.rmb_tool_type = rmb_tool_type

    def activate(self, tools):
        # Deactivate all tools except highlight
        for ttype, tool in tools.items():
            if ttype != ToolType.HIGHLIGHT_FIXED:
                tool.trigger_off()
        return tools

    def deactivate(self, tools):
        # Deactivate all tools except highlight
        for ttype, tool in tools.items():
            if ttype != ToolType.HIGHLIGHT_FIXED:
                tool.trigger_off()
        return tools


class FireMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIRE_BRUSH, ToolType.FIRE_ERASE)


class FixMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIX_BRUSH, ToolType.FIX_ERASE)


class FireLineMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIRE_LINE, ToolType.FIRE_LINE)


class FireRectMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIRE_RECT, ToolType.FIRE_RECT)


class FixRectMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIX_RECT, ToolType.FIX_RECT)
