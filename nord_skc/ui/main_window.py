from __future__ import annotations
from typing import Dict

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea

from nord_skc.config import Config, AssetConfig
from nord_skc.drivers import SiemensS7Driver, ServaTcpDriver, BaseDriver
from nord_skc.ui.widgets import AssetCard
from nord_skc.ui.asset_window import AssetWindow

class MainWindow(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle(cfg.app.name)

        self.asset_windows: Dict[str, AssetWindow] = {}
        self.cards: Dict[str, AssetCard] = {}
        self.drivers: Dict[str, BaseDriver] = {}

        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)

        header = QLabel("NORD SKC — выбор агрегата")
        header.setStyleSheet("font-size: 18px; font-weight: 700;")
        v.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        v.addWidget(scroll, 1)

        grid_host = QWidget()
        scroll.setWidget(grid_host)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        cols = 4
        row = col = 0
        for a in sorted(cfg.assets, key=lambda x: x.fleet_no):
            title = f"Fleet {a.fleet_no:02d}"
            subtitle = f"Plate: {a.plate}" if a.plate else "Plate: (empty)"
            card = AssetCard(title=title, subtitle=subtitle)
            card.clicked.connect(lambda _=None, asset=a: self.open_asset(asset))
            grid.addWidget(card, row, col)
            self.cards[a.id] = card

            col += 1
            if col >= cols:
                col = 0
                row += 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_statuses)
        self.timer.start(1000)  # 1 Hz

    def _make_driver(self, a: AssetConfig) -> BaseDriver:
        if a.id in self.drivers:
            return self.drivers[a.id]

        if a.type == "siemens_s7":
            tags = a.extra.get("tags") or {}
            d = SiemensS7Driver(
                ip=a.ip,
                rack=int(a.extra.get("rack", 0)),
                slot=int(a.extra.get("slot", 1)),
                tags=tags,
            )
        elif a.type == "serva_tcp":
            d = ServaTcpDriver(
                ip=a.ip,
                port=int(a.extra.get("port", 6565)),
                timeout_s=float(a.extra.get("timeout_s", 2.0)),
                field_names=list(a.extra.get("field_names") or []),
            )
        else:
            raise ValueError(f"Unknown asset type: {a.type}")

        try:
            d.connect()
        except Exception:
            pass

        self.drivers[a.id] = d
        return d

    def refresh_statuses(self):
        for a in self.cfg.assets:
            card = self.cards.get(a.id)
            if not card:
                continue

            # Если окно агрегата уже открыто, не трогаем драйвер (иначе будет конфликт чтения из сокета).
            if a.id in self.asset_windows:
                w = self.asset_windows[a.id]
                if w.isVisible():
                    continue

            d = self._make_driver(a)
            # Лёгкая проверка: пробуем 1 раз прочитать. Если агрегат не отвечает — offline.
            # Важно: этот read_once будет потреблять ответ, поэтому мы не делаем это, когда окно открыто.
            rr = d.read_once()
            if rr.ok:
                card.status_lbl.setText("● online")
                card.status_lbl.setStyleSheet("color: #6d6;")
            else:
                card.status_lbl.setText("● offline")
                card.status_lbl.setStyleSheet("color: #d66;")

    def open_asset(self, a: AssetConfig):
        d = self._make_driver(a)
        if a.id not in self.asset_windows:
            w = AssetWindow(self.cfg.app, a, d, config_path="config.yaml")
            self.asset_windows[a.id] = w
        self.asset_windows[a.id].show()
        self.asset_windows[a.id].raise_()
        self.asset_windows[a.id].activateWindow()
