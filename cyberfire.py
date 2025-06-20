import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)


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

        self.launch_btn = QPushButton("Launch")
        self.launch_btn.clicked.connect(self.launch)
        layout.addWidget(self.launch_btn)

        self.setLayout(layout)

    def launch(self):
        if self.radio_2d.isChecked():

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd() / "cf2d")
            subprocess.Popen([sys.executable, "-m", "cf2d.cyberfire"], env=env)
            self.close()
            return
        elif self.radio_3d.isChecked():
            QMessageBox.warning(self, "Info", "3D mode not implemented yet.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    selector = ModeSelector()
    selector.show()
    sys.exit(app.exec())
