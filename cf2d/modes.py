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


class HighlightFixedMixin(Mode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._highlight_fixed_prev_state = None

    def activate(self, tools):
        highlight_tool = tools.get(ToolType.HIGHLIGHT_FIXED)
        if highlight_tool:
            self._highlight_fixed_prev_state = highlight_tool.is_active()
            highlight_tool.trigger_on()
        super().activate(tools)
        return tools

    def deactivate(self, tools):
        highlight_tool = tools.get(ToolType.HIGHLIGHT_FIXED)
        if highlight_tool and self._highlight_fixed_prev_state is not None:
            if not self._highlight_fixed_prev_state:
                highlight_tool.trigger_off()
        super().deactivate(tools)
        return tools


class FixMode(HighlightFixedMixin, Mode):
    def __init__(self):
        super().__init__(ToolType.FIX_BRUSH, ToolType.FIX_ERASE)


class FixRectMode(HighlightFixedMixin, Mode):
    def __init__(self):
        super().__init__(ToolType.FIX_RECT, ToolType.FIX_RECT)


class FireLineMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIRE_LINE, ToolType.FIRE_LINE)


class FireRectMode(Mode):
    def __init__(self):
        super().__init__(ToolType.FIRE_RECT, ToolType.FIRE_RECT)
