import sys
import time
from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QRadioButton, QSlider, QVBoxLayout, QWidget)

from core import (FIRE_HEIGHT, FIRE_WIDTH, clear_image, do_fire, firePixels,
                  get_palette_list, image, initialize_fire, marching_cubes,
                  num_triangles, rasterize)


class FireWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_time = 0
        self.brush_radius = 25
        self.brush_changed = time.time() - 10
        self.mx = 0.5
        self.my = 0.5
        self.intensity_percent = 100

        # --- FPS Counter ---
        self.last_fps_time = time.time()
        self.frame_count = 0
        self.fps = 0
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

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

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
        intensity_slider.setMinimum(20)
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

        # --- Reset/Clear Buttons ---
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_all)
        layout.addWidget(reset_btn)
        self.reset_btn = reset_btn

        clear_fire_btn = QPushButton("Clear Fire")
        clear_fire_btn.clicked.connect(self.clear_fire)
        layout.addWidget(clear_fire_btn)
        self.clear_fire_btn = clear_fire_btn

        layout.addStretch(1)

        # --- FPS Counter ---
        self.fps_label = QLabel("FPS: 0", panel)
        layout.addWidget(self.fps_label)

        panel.setLayout(layout)
        return panel

    def set_intensity(self, val: int, label=None):
        self.intensity_percent = val
        if label is not None:
            label.setText(f"Intensity: {val}%")

    def reset_all(self):
        firePixels.fill(0)
        initialize_fire()

        self.palettes[self.palette_idx][1]()

    def clear_fire(self):
        firePixels.fill(0)

    def update_frame(self):
        self.current_time += 0.05
        do_fire(self.current_time)

        marching_cubes()
        clear_image()
        rasterize()
        print(num_triangles)
        np_img = image.to_numpy()
        # This copy is annoying, as it likely introduces a lot of unneeded copies, but this needs to be an actual array and not a view for .data
        np_img = np.rot90(np_img).copy()
        h, w, ch = np_img.shape

        bytes_per_line = ch * w
        qimg = QImage(np_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qimg))

        # --- FPS Counter update ---
        self.frame_count += 1
        now = time.time()
        elapsed_fps = now - self.last_fps_time
        if elapsed_fps >= 0.25:
            self.fps = int(self.frame_count / elapsed_fps)
            self.fps_label.setText(f"FPS: {self.fps}")
            self.last_fps_time = now
            self.frame_count = 0


def main():
    app = QApplication(sys.argv)
    win = FireWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
