import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QRadioButton, QSpinBox,
                               QVBoxLayout, QWidget)


class ModeSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyberFire Launcher")
        layout = QVBoxLayout()

        self.radio_2d = QRadioButton("2D")
        self.radio_3d = QRadioButton("3D")
        self.radio_2d.setChecked(True)

        layout.addWidget(self.radio_2d)
        layout.addWidget(self.radio_3d)

        # --- FIRE_* Inputs ---
        self.width_input = QSpinBox()
        self.width_input.setRange(1, 8192)
        self.width_input.setValue(1440)
        self.width_input.setSingleStep(10)

        self.height_input = QSpinBox()
        self.height_input.setRange(1, 8192)
        self.height_input.setValue(960)
        self.height_input.setSingleStep(10)

        self.depth_input = QSpinBox()
        self.depth_input.setRange(1, 1000)
        self.depth_input.setValue(500)
        self.depth_input.setSingleStep(10)
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        width_layout.addWidget(self.width_input)
        layout.addLayout(width_layout)
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        height_layout.addWidget(self.height_input)
        layout.addLayout(height_layout)
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Depth:"))
        depth_layout.addWidget(self.depth_input)
        layout.addLayout(depth_layout)
        self.depth_input.setEnabled(False)
        self.radio_2d.toggled.connect(
            lambda checked: self.depth_input.setEnabled(not checked)
        )
        self.radio_3d.toggled.connect(
            lambda checked: self.depth_input.setEnabled(checked)
        )

        self.launch_btn = QPushButton("Launch")
        self.launch_btn.clicked.connect(self.launch)
        layout.addWidget(self.launch_btn)

        self.setLayout(layout)

    def launch(self):
        width = self.width_input.text()
        height = self.height_input.text()
        depth = self.depth_input.text()
        env = os.environ.copy()
        env["FIRE_WIDTH"] = width
        env["FIRE_HEIGHT"] = height
        if self.radio_2d.isChecked():
            env["PYTHONPATH"] = str(Path.cwd() / "cf2d")
            subprocess.Popen([sys.executable, "-m", "cf2d.cyberfire2d"], env=env)
            self.close()
            return
        elif self.radio_3d.isChecked():
            env["PYTHONPATH"] = str(Path.cwd() / "cf3d")
            env["FIRE_DEPTH"] = depth
            subprocess.Popen([sys.executable, "-m", "cf3d.cyberfire3d"], env=env)
            self.close()
            return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    selector = ModeSelector()
    selector.show()
    sys.exit(app.exec())
