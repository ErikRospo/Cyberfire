import sys
import time
from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from core import (FIRE_HEIGHT, FIRE_WIDTH, clear_fixed_pixels, do_fire,
                  firePixels, highlight_fixed_pixels, image, initialize_fire,
                  initialize_palette_cold_fire, initialize_palette_cyber,
                  initialize_palette_electric, initialize_palette_fire,
                  initialize_palette_gray, initialize_palette_sunset,
                  initialize_palette_toxic, render_tool_radius, update_image)
from tools import (FireBrushTool, FireEraseTool, FixBrushTool, FixEraseTool,
                   HighlightFixedTool, Tool)


class FireWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fire Effect (PySide6)")
        self.label = QLabel(self)
        self.setCentralWidget(self.label)
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
        self.current_time = 0
        self.brush_radius = 25
        self.brush_changed = time.time() - 10
        self.mx = 0.5
        self.my = 0.5
        self.tools: Dict[str, Tool] = {
            "fire_brush": FireBrushTool(),
            "fire_erase": FireEraseTool(),
            "fix_brush": FixBrushTool(),
            "fix_erase": FixEraseTool(),
            "highlight_fixed": HighlightFixedTool(),
        }
        self.setMouseTracking(True)
        self.label.setMouseTracking(True)
        self.pressing_lmb = False
        self.pressing_rmb = False

    def update_frame(self):
        self.current_time += 0.05
        do_fire(self.current_time)
        mx_int = int(self.mx * FIRE_WIDTH)
        my_int = int(self.my * FIRE_HEIGHT)
        for name, tool in self.tools.items():
            if tool.is_active():
                tool.apply(mx_int, my_int, self.brush_radius)
        update_image()
        if self.tools["highlight_fixed"].is_active():
            highlight_fixed_pixels()
        # Fade alpha from 80 to 0 over 2 seconds
        elapsed = time.time() - self.brush_changed
        if elapsed < 2:
            alpha = int(80 * min(1, (1 - elapsed / 2)))
            render_tool_radius(
                int(self.mx * FIRE_WIDTH),
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
        if event.button() == Qt.MouseButton.LeftButton:
            self.tools["fire_brush"].trigger_on()
            self.tools["fire_erase"].trigger_off()
            self.brush_changed = 0
            self.pressing_lmb = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.tools["fire_erase"].trigger_on()
            self.tools["fire_brush"].trigger_off()
            self.brush_changed = 0
            self.pressing_rmb = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.tools["fire_brush"].trigger_off()
            self.pressing_lmb = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.tools["fire_erase"].trigger_off()
            self.pressing_rmb = False

    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        y = event.position().y()
        self.mx = np.clip(x / FIRE_WIDTH, 0, 1)
        self.my = np.clip(y / FIRE_HEIGHT, 0, 1)

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
        if key == Qt.Key.Key_F:
            self.tools["fix_brush"].trigger_on()
            self.tools["fix_erase"].trigger_off()
            self.brush_changed = 0
        elif key == Qt.Key.Key_U:
            self.tools["fix_erase"].trigger_on()
            self.tools["fix_brush"].trigger_off()
            self.brush_changed = 0
        elif key == Qt.Key.Key_V:
            if self.tools["highlight_fixed"].is_active():
                self.tools["highlight_fixed"].trigger_off()
            else:
                self.tools["highlight_fixed"].trigger_on()
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

    def keyReleaseEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_F:
            self.tools["fix_brush"].trigger_off()
        elif key == Qt.Key.Key_U:
            self.tools["fix_erase"].trigger_off()


def main():
    app = QApplication(sys.argv)
    win = FireWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
