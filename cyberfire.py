import sys
import time
from enum import Enum, auto
from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

import tools
from core import (FIRE_HEIGHT, FIRE_WIDTH, clear_fixed_pixels, do_fire,
                  firePixels, highlight_fixed_pixels, image, initialize_fire,
                  initialize_palette_cold_fire, initialize_palette_cyber,
                  initialize_palette_electric, initialize_palette_fire,
                  initialize_palette_gray, initialize_palette_sunset,
                  initialize_palette_toxic, render_tool_radius, update_image)
from tools import (FireBrushTool, FireEraseTool, FireLineTool, FixBrushTool,
                   FixEraseTool, HighlightFixedTool, Tool, ToolType)


class ModeType(Enum):
    FIRE = auto()
    FIX = auto()
    FIRE_LINE = auto()  # New mode


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


class FireWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_time = 0
        self.brush_radius = 25
        self.brush_changed = time.time() - 10
        self.mx = 0.5
        self.my = 0.5
        self.pressing_lmb = False
        self.pressing_rmb = False
        self.modes = {
            ModeType.FIRE: FireMode(),
            ModeType.FIX: FixMode(),
            ModeType.FIRE_LINE: FireLineMode(),  # Add FireLineMode
        }
        self.mode = ModeType.FIRE  # Default mode

        self.tools: Dict[ToolType, Tool] = {
            ToolType.FIRE_BRUSH: FireBrushTool(),
            ToolType.FIRE_ERASE: FireEraseTool(),
            ToolType.FIX_BRUSH: FixBrushTool(),
            ToolType.FIX_ERASE: FixEraseTool(),
            ToolType.HIGHLIGHT_FIXED: HighlightFixedTool(),
            ToolType.FIRE_LINE: FireLineTool(),  # Add FireLineTool
        }
        self.setWindowTitle("Fire Effect (PySide6)")
        self.label = QLabel(self)
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # --- Sidepanel UI ---
        self.tool_buttons = {}
        self.sidepanel = self.init_sidepanel()
        main_layout.addWidget(self.label, stretch=1)
        main_layout.addWidget(self.sidepanel)

        self.resize(FIRE_WIDTH, FIRE_HEIGHT)
        initialize_fire()
        self.palette_idx = 0
        self.palette_functions = [
            initialize_palette_fire,
            initialize_palette_cyber,
            initialize_palette_gray,
            initialize_palette_cold_fire,
            initialize_palette_sunset,
            initialize_palette_toxic,
            initialize_palette_electric,
        ]
        self.palette_functions[self.palette_idx]()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # ~60 FPS

        self.setMouseTracking(True)
        self.label.setMouseTracking(True)

    @property
    def imx(self):
        return int(self.mx * FIRE_WIDTH)

    @imx.setter
    def imx(self, value):
        self.mx = np.clip(value / FIRE_WIDTH, 0, 1)

    @property
    def imy(self):
        return int(self.my * FIRE_HEIGHT)

    @imy.setter
    def imy(self, value):
        self.my = np.clip(value / FIRE_HEIGHT, 0, 1)

    def init_sidepanel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Mode Radio Buttons ---
        mode_group = QButtonGroup(panel)
        fire_radio = QRadioButton("Fire Mode")
        fix_radio = QRadioButton("Fix Mode")
        fireline_radio = QRadioButton("Fire Line Mode")  # New radio button
        fire_radio.setChecked(self.mode == ModeType.FIRE)
        fix_radio.setChecked(self.mode == ModeType.FIX)
        fireline_radio.setChecked(self.mode == ModeType.FIRE_LINE)
        mode_group.addButton(fire_radio)
        mode_group.addButton(fix_radio)
        mode_group.addButton(fireline_radio)
        fire_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIRE) if checked else None
        )
        fix_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIX) if checked else None
        )
        fireline_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIRE_LINE) if checked else None
        )
        layout.addWidget(fire_radio)
        layout.addWidget(fix_radio)
        layout.addWidget(fireline_radio)
        self.fire_radio = fire_radio
        self.fix_radio = fix_radio
        self.fireline_radio = fireline_radio

        # --- Highlight Fixed Button ---
        highlight_btn = QPushButton("Toggle Highlight Fixed")
        highlight_btn.setCheckable(True)
        highlight_btn.setChecked(self.tools[ToolType.HIGHLIGHT_FIXED].is_active())
        highlight_btn.clicked.connect(self.toggle_highlight_fixed)
        layout.addWidget(highlight_btn)
        self.highlight_btn = highlight_btn

        layout.addStretch(1)
        panel.setLayout(layout)
        return panel

    def set_mode(self, mode):
        if mode == self.mode:
            return
        # Deactivate previous mode
        self.modes[self.mode].deactivate(self.tools)
        # Clear FireLineTool state if leaving FireLine mode
        if self.mode == ModeType.FIRE_LINE:
            s = self.tools[ToolType.FIRE_LINE]
            assert type(s) == tools.FireLineTool
            s.clear_first_point()
        self.mode = mode
        # Activate new mode
        self.modes[self.mode].activate(self.tools)
        # Activate tool depending on mouse buttons
        lmb_tool = self.modes[self.mode].lmb_tool_type
        rmb_tool = self.modes[self.mode].rmb_tool_type
        if self.pressing_lmb:
            self.tools[lmb_tool].trigger_on()
            self.tools[rmb_tool].trigger_off()
        elif self.pressing_rmb:
            self.tools[rmb_tool].trigger_on()
            self.tools[lmb_tool].trigger_off()
        self.brush_changed = 0
        self.update_tool_buttons()

    def toggle_highlight_fixed(self):
        tool = self.tools[ToolType.HIGHLIGHT_FIXED]
        if tool.is_active():
            tool.trigger_off()
        else:
            tool.trigger_on()
        self.update_tool_buttons()

    def update_tool_buttons(self):
        # Update radio buttons
        self.fire_radio.setChecked(self.mode == ModeType.FIRE)
        self.fix_radio.setChecked(self.mode == ModeType.FIX)
        self.fireline_radio.setChecked(self.mode == ModeType.FIRE_LINE)
        # Update highlight button
        active = self.tools[ToolType.HIGHLIGHT_FIXED].is_active()
        self.highlight_btn.setChecked(active)
        if active:
            self.highlight_btn.setStyleSheet(
                "background-color: #aaf; font-weight: bold;"
            )
        else:
            self.highlight_btn.setStyleSheet("")

    def update_frame(self):
        self.current_time += 0.05
        do_fire(self.current_time)
        mx_int = self.imx
        my_int = self.imy
        for ttype, tool in self.tools.items():
            if tool.is_active():
                tool.apply(mx_int, my_int, self.brush_radius)
        update_image()
        # Show highlight if highlight_fixed is active or if fix mode is active
        if (
            self.tools[ToolType.HIGHLIGHT_FIXED].is_active()
            or self.mode == ModeType.FIX
        ):
            highlight_fixed_pixels()
        # Fade alpha from 80 to 0 over 2 seconds
        elapsed = time.time() - self.brush_changed
        if elapsed < 2:
            alpha = int(80 * min(1, (1 - elapsed / 2)))
            render_tool_radius(
                self.imx,
                int((1 - self.my) * FIRE_HEIGHT),
                self.brush_radius,
                alpha,
            )
        np_img = image.to_numpy()
        # This copy is annoying, as it likely introduces a lot of unneeded copies, but this needs to be an actual array and not a view for .data
        np_img = np.rot90(np_img).copy()
        h, w, ch = np_img.shape

        bytes_per_line = ch * w
        qimg = QImage(np_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qimg))

    def mousePressEvent(self, event: QMouseEvent):
        self.update_mouse_position(event)
        lmb_tool = self.modes[self.mode].lmb_tool_type
        rmb_tool = self.modes[self.mode].rmb_tool_type
        mx_int = self.imx
        my_int = self.imy
        if self.mode == ModeType.FIRE_LINE:
            fire_line_tool = self.tools[ToolType.FIRE_LINE]
            assert type(fire_line_tool) == FireLineTool
            if event.button() == Qt.MouseButton.LeftButton:
                fire_line_tool.set_first_point(mx_int, my_int)
                fire_line_tool.trigger_off()  # Don't draw yet
                self.pressing_lmb = True
            elif event.button() == Qt.MouseButton.RightButton:
                if fire_line_tool.first_point is not None:
                    fire_line_tool.trigger_on()
                    fire_line_tool.apply(mx_int, my_int, self.brush_radius)
                    fire_line_tool.trigger_off()
                    fire_line_tool.clear_first_point()
                self.pressing_rmb = True
            self.update_tool_buttons()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.tools[lmb_tool].trigger_on()
            self.tools[rmb_tool].trigger_off()
            self.brush_changed = 0
            self.pressing_lmb = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.tools[rmb_tool].trigger_on()
            self.tools[lmb_tool].trigger_off()
            self.brush_changed = 0
            self.pressing_rmb = True
        self.update_tool_buttons()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.update_mouse_position(event)
        if self.mode == ModeType.FIRE_LINE:
            if event.button() == Qt.MouseButton.LeftButton:
                self.pressing_lmb = False
            elif event.button() == Qt.MouseButton.RightButton:
                self.pressing_rmb = False
            self.update_tool_buttons()
            return
        lmb_tool = self.modes[self.mode].lmb_tool_type
        rmb_tool = self.modes[self.mode].rmb_tool_type
        if event.button() == Qt.MouseButton.LeftButton:
            self.tools[lmb_tool].trigger_off()
            self.pressing_lmb = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.tools[rmb_tool].trigger_off()
            self.pressing_rmb = False
        self.update_tool_buttons()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.update_mouse_position(event)

    def update_mouse_position(self, event: QMouseEvent):
        x = event.position().x()
        y = event.position().y()
        self.imx = x
        self.imy = y

    def wheelEvent(self, event: QWheelEvent):
        now = time.time()
        delta_y = event.angleDelta().y()
        if now - self.brush_changed < 0.5:
            accel = 1 / (now - self.brush_changed + 0.25)
        else:
            accel = 1
        delta_with_accel = int(delta_y * accel / 32)
        self.brush_radius += delta_with_accel
        self.brush_radius = max(1, min(self.brush_radius, 400))
        self.brush_changed = now

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_B:
            self.set_mode(ModeType.FIRE)
        elif key == Qt.Key.Key_F:
            self.set_mode(ModeType.FIX)
        elif key == Qt.Key.Key_V:
            self.toggle_highlight_fixed()
        elif key == Qt.Key.Key_P:
            self.palette_idx = (self.palette_idx + 1) % len(self.palette_functions)
            self.palette_functions[self.palette_idx]()
            print(
                self.palette_functions[self.palette_idx]
                .__name__.replace("initialize_palette_", "")
                .capitalize()
                .replace("_", " ")
            )
        elif key == Qt.Key.Key_R:
            firePixels.fill(0)
            initialize_fire()
            clear_fixed_pixels()
        elif key == Qt.Key.Key_S:
            self.brush_changed = time.time() + 3
        self.update_tool_buttons()


def main():
    app = QApplication(sys.argv)
    win = FireWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
