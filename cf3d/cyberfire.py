import sys
import time
from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QRadioButton, QSlider, QVBoxLayout, QWidget)

from core import (FIRE_DEPTH, FIRE_HEIGHT, FIRE_WIDTH, do_fire, firePixels,
                  get_palette_list, initialize_fire, render_scene, scene)


class FireWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_time = 0
        self.brush_radius = 25
        self.brush_changed = time.time() - 10
        self.mx = 0.5
        self.my = 0.5
        self.intensity_percent = 100

        # --- Camera rotation state ---
        self.camera_yaw = -np.pi / 2  # Start facing into the scene
        self.camera_pitch = -0.3      # Slightly above
        self.camera_distance = 2.5
        self.camera_target = np.array([FIRE_WIDTH / 2, FIRE_HEIGHT / 2, FIRE_DEPTH / 2], dtype=np.float32)
        self.last_mouse_pos = None
        self.is_dragging = False
        self.is_panning = False
        # --- Pan state ---
        self.camera_pan_x = 0.0
        self.camera_pan_y = 0.0
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
        scene.renderer.recompute_bbox()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

        self.setMouseTracking(True)
        self.label.setMouseTracking(True)
        self.label.mouseMoveEvent = self.mouseMoveEvent
        self.label.mousePressEvent = self.mousePressEvent
        self.label.mouseReleaseEvent = self.mouseReleaseEvent
        self.label.wheelEvent = self.wheelEvent

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

        # --- Frame Fire Button ---
        frame_btn = QPushButton("Frame Fire")
        frame_btn.clicked.connect(self.frame_fire)
        layout.addWidget(frame_btn)
        self.frame_btn = frame_btn

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
        scene.renderer.recompute_bbox()
        self.palettes[self.palette_idx][1]()
        # Reset camera
        self.camera_yaw = 0.0
        self.camera_pitch = 0.0
        self.camera_distance = 2.5
        self.camera_target = np.array([FIRE_WIDTH / 2, FIRE_HEIGHT / 2, FIRE_DEPTH / 2], dtype=np.float32)
        self.is_dragging = False
        self.is_panning = False
        self.last_mouse_pos = None


    def clear_fire(self):
        firePixels.fill(0)

    def frame_fire(self):
        # Recompute bbox
        scene.renderer.recompute_bbox()
        bbox_min = np.array(scene.renderer.bbox[0].to_numpy(), dtype=np.float32)
        bbox_max = np.array(scene.renderer.bbox[1].to_numpy(), dtype=np.float32)
        center = (bbox_min + bbox_max) / 2.0
        size = bbox_max - bbox_min
        # Set camera target to center
        self.camera_target = center.astype(np.float32)
        # Set camera distance to fit the bbox
        max_extent = np.linalg.norm(size)
        self.camera_distance = float(max_extent * 0.7 + 2.0)  # Add margin
        # Set camera angles to a default isometric view
        self.camera_yaw = -np.pi / 4
        self.camera_pitch = -np.pi / 6
        self.is_dragging = False
        self.is_panning = False
        self.last_mouse_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = (
                event.position() if hasattr(event, "position") else event.pos()
            )
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_panning = True
            self.last_mouse_pos = (
                event.position() if hasattr(event, "position") else event.pos()
            )

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        if self.last_mouse_pos is None:
            self.last_mouse_pos = pos
            return
        dx = pos.x() - self.last_mouse_pos.x()
        dy = pos.y() - self.last_mouse_pos.y()
        if self.is_dragging:
            # Orbit: update yaw/pitch
            self.camera_yaw += dx * 0.01
            self.camera_pitch += dy * 0.01
            self.camera_pitch = np.clip(self.camera_pitch, -np.pi / 2 + 0.05, np.pi / 2 - 0.05)
        elif self.is_panning:
            # Pan: move target in camera's right/up plane
            cam_pos, look_at, up = self.compute_camera()
            forward = look_at - cam_pos
            forward /= np.linalg.norm(forward)
            right = np.cross(forward, up)
            right /= np.linalg.norm(right)
            up_vec = np.cross(right, forward)
            up_vec /= np.linalg.norm(up_vec)
            pan_speed = self.camera_distance * 0.002
            self.camera_target += right * (-dx * pan_speed) + up_vec * (dy * pan_speed)
        self.last_mouse_pos = pos

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.last_mouse_pos = None
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_panning = False
            self.last_mouse_pos = None

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() / 120
        self.camera_distance *= np.exp(-delta * 0.1)
        self.camera_distance = np.clip(self.camera_distance, 0.1, 100.0)
        event.accept()

    def compute_camera(self):
        # Spherical coordinates to cartesian
        pitch = self.camera_pitch
        yaw = self.camera_yaw
        r = self.camera_distance
        target = self.camera_target
        # Camera position in world space
        x = target[0] + r * np.cos(pitch) * np.cos(yaw)
        y = target[1] + r * np.sin(pitch)
        z = target[2] + r * np.cos(pitch) * np.sin(yaw)
        cam_pos = np.array([x, y, z], dtype=np.float32)
        # Calculate up vector based on pitch/yaw
        # This keeps the up vector perpendicular to the view direction
        up = np.array([0, 1, 0], dtype=np.float32)
        view = target - cam_pos
        view /= np.linalg.norm(view)
        right = np.cross(up, view)
        right /= np.linalg.norm(right)
        up_corrected = np.cross(view, right)
        up_corrected /= np.linalg.norm(up_corrected)
        return cam_pos, target, up_corrected

    def update_frame(self):
        self.current_time += 0.05
        do_fire(self.current_time)

        cam_pos, look_at, up = self.compute_camera()
        scene.renderer.set_camera_pos(*cam_pos)
        scene.renderer.set_look_at(*look_at)
        scene.set_up(up)

        image = render_scene()
        np_img = image.to_numpy()
        np_img = np.rot90(np_img * 256)
        np_img = np.astype(np_img, np.uint8).copy()
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
