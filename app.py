from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from nord_skc.config import load_config
from nord_skc.ui.main_window import MainWindow

def main() -> int:
    cfg = load_config("config.yaml")
    app = QApplication(sys.argv)
    with open("nord_skc/ui/style.qss", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    w = MainWindow(cfg)
    w.resize(1400, 800)
    w.show()

    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
