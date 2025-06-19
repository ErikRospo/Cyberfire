import sys
import time
from enum import Enum, auto
from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QRadioButton, QSlider, QVBoxLayout, QWidget)

from core import (FIRE_HEIGHT, FIRE_WIDTH, clear_fixed_pixels, do_fire,
                  firePixels, highlight_fixed_pixels, image, initialize_fire,
                  get_palette_list, render_tool_radius, update_image)
from modes import FireLineMode, FireMode, FireRectMode, FixMode, ModeType
from tools import (FireBrushTool, FireEraseTool, FireLineTool, FireRectTool,
                   FixBrushTool, FixEraseTool, HighlightFixedTool, Tool,
                   ToolType)


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
        self.intensity_percent = 100
        self.modes = {
            ModeType.FIRE: FireMode(),
            ModeType.FIX: FixMode(),
            ModeType.FIRE_LINE: FireLineMode(),
            ModeType.FIRE_RECT: FireRectMode(),
        }
        self.mode = ModeType.FIRE  # Default mode

        self.tools: Dict[ToolType, Tool] = {
            ToolType.FIRE_BRUSH: FireBrushTool(),
            ToolType.FIRE_ERASE: FireEraseTool(),
            ToolType.FIX_BRUSH: FixBrushTool(),
            ToolType.FIX_ERASE: FixEraseTool(),
            ToolType.HIGHLIGHT_FIXED: HighlightFixedTool(),
            ToolType.FIRE_LINE: FireLineTool(),
            ToolType.FIRE_RECT: FireRectTool(),
        }

        # Use palette list from core.py
        self.palettes = get_palette_list()
        self.palette_idx = 0
        self.palettes[self.palette_idx][1]()
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
        # Refactored palette as list of (name, function) tuples

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # ~60 FPS

        self.setMouseTracking(True)
        self.label.setMouseTracking(True)
        self.label.mouseMoveEvent = self.mouseMoveEvent

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

        # --- Intensity Slider ---
        intensity_label = QLabel(f"Intensity: {self.intensity_percent}%", panel)
        intensity_slider = QSlider(Qt.Orientation.Horizontal, panel)
        intensity_slider.setMinimum(0)
        intensity_slider.setMaximum(100)
        intensity_slider.setValue(self.intensity_percent)
        intensity_slider.setTickInterval(10)
        intensity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        intensity_slider.valueChanged.connect(
            lambda val: self.set_intensity(val, intensity_label)
        )
        layout.addWidget(intensity_label)
        layout.addWidget(intensity_slider)
        self.intensity_slider = intensity_slider
        self.intensity_label = intensity_label

        # --- Palette Dropdown ---
        palette_combo = QComboBox(panel)
        palette_combo.addItems([name for name, _ in self.palettes])
        palette_combo.setCurrentIndex(self.palette_idx)
        palette_combo.currentIndexChanged.connect(self.set_palette_idx)
        layout.addWidget(palette_combo)
        self.palette_combo = palette_combo

        # --- Mode Radio Buttons ---
        mode_group = QButtonGroup(panel)
        fire_radio = QRadioButton("Fire Mode")
        fix_radio = QRadioButton("Fix Mode")
        fireline_radio = QRadioButton("Fire Line Mode")
        firerect_radio = QRadioButton("Fire Rect Mode")
        fire_radio.setChecked(self.mode == ModeType.FIRE)
        fix_radio.setChecked(self.mode == ModeType.FIX)
        fireline_radio.setChecked(self.mode == ModeType.FIRE_LINE)
        firerect_radio.setChecked(self.mode == ModeType.FIRE_RECT)
        mode_group.addButton(fire_radio)
        mode_group.addButton(fix_radio)
        mode_group.addButton(fireline_radio)
        mode_group.addButton(firerect_radio)
        fire_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIRE) if checked else None
        )
        fix_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIX) if checked else None
        )
        fireline_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIRE_LINE) if checked else None
        )
        firerect_radio.toggled.connect(
            lambda checked: self.set_mode(ModeType.FIRE_RECT) if checked else None
        )
        layout.addWidget(fire_radio)
        layout.addWidget(fix_radio)
        layout.addWidget(fireline_radio)
        layout.addWidget(firerect_radio)
        self.fire_radio = fire_radio
        self.fix_radio = fix_radio
        self.fireline_radio = fireline_radio
        self.firerect_radio = firerect_radio

        # --- Highlight Fixed Button ---
        highlight_btn = QPushButton("Toggle Highlight Fixed")
        highlight_btn.setCheckable(True)
        highlight_btn.setChecked(self.tools[ToolType.HIGHLIGHT_FIXED].is_active())
        highlight_btn.clicked.connect(self.toggle_highlight_fixed)
        layout.addWidget(highlight_btn)
        self.highlight_btn = highlight_btn

        # --- Reset/Clear Buttons ---
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_all)
        layout.addWidget(reset_btn)
        self.reset_btn = reset_btn

        clear_fire_btn = QPushButton("Clear Fire")
        clear_fire_btn.clicked.connect(self.clear_fire)
        layout.addWidget(clear_fire_btn)
        self.clear_fire_btn = clear_fire_btn

        reset_fixed_btn = QPushButton("Reset Fixed Pixels")
        reset_fixed_btn.clicked.connect(self.reset_fixed_pixels)
        layout.addWidget(reset_fixed_btn)
        self.reset_fixed_btn = reset_fixed_btn

        layout.addStretch(1)
        panel.setLayout(layout)
        return panel

    def set_intensity(self, val: int, label=None):
        self.intensity_percent = val
        if label is not None:
            label.setText(f"Intensity: {val}%")

    def reset_all(self):
        firePixels.fill(0)
        initialize_fire()
        clear_fixed_pixels()
        self.palettes[self.palette_idx][1]()
        self.update_tool_buttons()

    def clear_fire(self):
        firePixels.fill(0)
        self.update_tool_buttons()

    def reset_fixed_pixels(self):
        clear_fixed_pixels()
        self.update_tool_buttons()

    def set_mode(self, mode):
        if mode == self.mode:
            return
        # Deactivate previous mode
        self.modes[self.mode].deactivate(self.tools)
        # Clear FireLineTool or FireRectTool state if leaving those modes
        if self.mode == ModeType.FIRE_LINE:
            s = self.tools[ToolType.FIRE_LINE]
            assert type(s) == FireLineTool  # Keep Pylance happy
            s.clear_first_point()
        if self.mode == ModeType.FIRE_RECT:
            s = self.tools[ToolType.FIRE_RECT]
            assert type(s) == FireRectTool  # Keep Pylance happy
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

    def set_palette_idx(self, idx):
        self.palette_idx = idx
        self.palettes[self.palette_idx][1]()
        self.palette_combo.setCurrentIndex(self.palette_idx)
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
        self.firerect_radio.setChecked(self.mode == ModeType.FIRE_RECT)
        # Update highlight button
        active = self.tools[ToolType.HIGHLIGHT_FIXED].is_active()
        self.highlight_btn.setChecked(active)
        if active:
            self.highlight_btn.setStyleSheet("font-weight: bold;")
        else:
            self.highlight_btn.setStyleSheet("")
        # Update palette combo
        if hasattr(self, "palette_combo"):
            self.palette_combo.setCurrentIndex(self.palette_idx)

    def update_frame(self):
        self.current_time += 0.05
        do_fire(self.current_time)
        mx_int = self.imx
        my_int = self.imy
        intensity = float(self.intensity_percent / 100)

        for ttype, tool in self.tools.items():
            if tool.is_active():
                try:
                    tool.apply(mx_int, my_int, self.brush_radius, intensity)
                except TypeError:
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
        intensity: float = float(self.intensity_percent / 100)
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
                    fire_line_tool.apply(mx_int, my_int, self.brush_radius, intensity)
                    fire_line_tool.trigger_off()
                    fire_line_tool.clear_first_point()
                self.pressing_rmb = True
            self.update_tool_buttons()
            return
        if self.mode == ModeType.FIRE_RECT:
            fire_rect_tool = self.tools[ToolType.FIRE_RECT]
            assert type(fire_rect_tool) == FireRectTool
            if event.button() == Qt.MouseButton.LeftButton:
                fire_rect_tool.set_first_point(mx_int, my_int)
                fire_rect_tool.trigger_off()
                self.pressing_lmb = True
            elif event.button() == Qt.MouseButton.RightButton:
                if fire_rect_tool.first_point is not None:
                    fire_rect_tool.trigger_on()
                    fire_rect_tool.apply(mx_int, my_int, self.brush_radius, intensity)
                    fire_rect_tool.trigger_off()
                    fire_rect_tool.clear_first_point()
                self.pressing_rmb = True
            self.update_tool_buttons()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.tools[lmb_tool].trigger_on()
            self.tools[rmb_tool].trigger_off()
            self.brush_changed = 0
            self.pressing_lmb = True
            # FIXME: This certainly is one way to do this, but it seems very hacky
            # Pass intensity to tool if it supports it
            if hasattr(self.tools[lmb_tool], "apply"):
                try:
                    self.tools[lmb_tool].apply(
                        mx_int, my_int, self.brush_radius, intensity
                    )
                except TypeError:
                    self.tools[lmb_tool].apply(mx_int, my_int, self.brush_radius)
        elif event.button() == Qt.MouseButton.RightButton:
            self.tools[rmb_tool].trigger_on()
            self.tools[lmb_tool].trigger_off()
            self.brush_changed = 0
            self.pressing_rmb = True
            if hasattr(self.tools[rmb_tool], "apply"):
                try:
                    self.tools[rmb_tool].apply(
                        mx_int, my_int, self.brush_radius, intensity
                    )
                except TypeError:
                    self.tools[rmb_tool].apply(mx_int, my_int, self.brush_radius)
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
        if self.mode == ModeType.FIRE_RECT:
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

    def update_mouse_position(self, event: QMouseEvent | QWheelEvent):
        x = event.position().x()
        y = event.position().y()
        self.imx = x
        self.imy = y

    def wheelEvent(self, event: QWheelEvent):
        self.update_mouse_position(event)
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
            self.palette_idx = (self.palette_idx + 1) % len(self.palettes)
            self.palettes[self.palette_idx][1]()
            if hasattr(self, "palette_combo"):
                self.palette_combo.setCurrentIndex(self.palette_idx)
            print(self.palettes[self.palette_idx][0])
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
