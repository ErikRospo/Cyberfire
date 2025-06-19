from core import change_heat_at_position, highlight_fixed_pixels, set_fixed_pixels


class Tool:
    name = "BaseTool"
    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and cls.name != "BaseTool":
            Tool.registry[cls.name] = cls

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
    name = "Fire Paint"

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=1)


class FireEraseTool(Tool):
    name = "Fire Erase"

    def apply(self, mx_int, my_int, brush_radius):
        change_heat_at_position(mx_int, my_int, radius=brush_radius, multiplier=-1)


class FixBrushTool(Tool):
    name = "Fix Brush"

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 1)


class FixEraseTool(Tool):
    name = "Fix Erase"

    def apply(self, mx_int, my_int, brush_radius):
        set_fixed_pixels(mx_int, my_int, brush_radius, 0)


class HighlightFixedTool(Tool):
    name = "Highlight Fixed"

    def apply(self, _mx_int, _my_int, _brush_radius):
        highlight_fixed_pixels()


def get_tool_by_name(name):
    cls = Tool.registry.get(name)
    if cls:
        return cls()
    raise ValueError(f"No tool registered with name: {name}")


def list_tool_names():
    return list(Tool.registry.keys())
