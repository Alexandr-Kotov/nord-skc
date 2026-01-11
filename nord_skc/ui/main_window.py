from __future__ import annotations
from typing import Dict

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import QProgressDialog
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
    QHBoxLayout,
    QSizePolicy,
    QMessageBox,
)

from nord_skc.config import Config, AssetConfig
from nord_skc.drivers import SiemensS7Driver, ServaTcpDriver, BaseDriver
from nord_skc.ui.widgets import AssetCard
from nord_skc.ui.asset_window import AssetWindow


class ConnectWorker(QObject):
    finished = Signal(object)          # driver
    failed = Signal(Exception)         # error

    def __init__(self, driver):
        super().__init__()
        self._driver = driver

    def run(self):
        try:
            self._driver.connect()
            self.finished.emit(self._driver)
        except Exception as e:
            self.failed.emit(e)


class MainWindow(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle(cfg.app.name)

        self.asset_windows: Dict[str, AssetWindow] = {}
        self.cards: Dict[str, AssetCard] = {}
        self.drivers: Dict[str, BaseDriver] = {}

        self._connect_thread: QThread | None = None
        self._connect_worker: ConnectWorker | None = None
        self._connect_dialog: QProgressDialog | None = None
        self._pending_asset: AssetConfig | None = None

        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ===== Header bar (logo + centered title) =====
        header_bar = QWidget()
        header_bar.setStyleSheet("background: #1f1f1f;")
        hb = QHBoxLayout(header_bar)
        hb.setContentsMargins(16, 10, 16, 10)
        hb.setSpacing(12)

        # Logo (optional). If file is missing, it will just be empty.
        logo = QLabel()
        try:
            pix = QPixmap("nord_skc/assets/logo.png")
            if not pix.isNull():
                logo.setPixmap(pix.scaledToHeight(36, Qt.SmoothTransformation))
        except Exception:
            pass
        logo.setFixedHeight(40)
        hb.addWidget(logo, 0, Qt.AlignVCenter)

        # Spacer to keep title truly centered
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hb.addWidget(left_spacer)

        header = QLabel("NORD SKC — выбор агрегата")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 20px; font-weight: 800;")
        hb.addWidget(header, 0, Qt.AlignVCenter)

        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hb.addWidget(right_spacer)

        v.addWidget(header_bar)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2f2f2f;")
        v.addWidget(sep)

        # ===== Scroll with cards =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
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
            title = f"Флот {a.fleet_no:02d}"
            vendor = a.extra.get("vendor", "")
            plate = a.plate or ""

            card = AssetCard(title=title, plate=plate, vendor=vendor)
            card.clicked.connect(lambda _=None, asset=a: self.open_asset(asset))
            grid.addWidget(card, row, col)
            self.cards[a.id] = card

            col += 1
            if col >= cols:
                col = 0
                row += 1

    # ---------- Драйверы ----------
    def _make_driver(self, a: AssetConfig) -> BaseDriver:
        """Создаём драйвер, но НЕ подключаемся. Подключение — только при открытии окна флота."""
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

        self.drivers[a.id] = d
        return d

    # ---------- Открытие окна агрегата ----------
    def open_asset(self, a: AssetConfig):
        # Защита от двойных кликов, пока идёт подключение
        if self._connect_dialog is not None:
            return

        d = self._make_driver(a)
        self._pending_asset = a

        # ===== Loader =====
        dlg = QProgressDialog("Подключение к агрегату…", "Отмена", 0, 0, self)
        dlg.setWindowTitle("Подключение")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(self._cancel_connect)
        dlg.show()

        self._connect_dialog = dlg

        # ===== Thread + worker =====
        try:
            t = QThread(self)
            w = ConnectWorker(d)
            w.moveToThread(t)

            t.started.connect(w.run)

            w.finished.connect(self._on_connect_ok)
            w.failed.connect(self._on_connect_fail)

            # остановить поток после завершения
            w.finished.connect(t.quit)
            w.failed.connect(t.quit)

            # корректная уборка
            t.finished.connect(w.deleteLater)
            t.finished.connect(t.deleteLater)
            t.finished.connect(self._on_connect_thread_finished)

            self._connect_thread = t
            self._connect_worker = w

            t.start()

        except Exception as e:
            # если что-то пошло не так — обязательно закрываем плоадер
            if self._connect_dialog:
                self._connect_dialog.close()
                self._connect_dialog = None
            self._pending_asset = None
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить подключение.\n\n{e}")
            return


    def _cancel_connect(self):
        # Важно: реальный socket connect отменить сложно (особенно если блокирующий),
        # но мы можем корректно закрыть диалог и не открывать окно.
        if self._connect_dialog:
            self._connect_dialog.close()
            self._connect_dialog = None
        self._pending_asset = None
        # поток сам завершится, когда connect() вернётся (успех/ошибка)


    def _on_connect_ok(self, driver):
        a = self._pending_asset
        self._pending_asset = None

        if self._connect_dialog:
            self._connect_dialog.close()
            self._connect_dialog = None

        # Если пользователь нажал "Отмена" — просто ничего не открываем
        if a is None:
            return

        if a.id not in self.asset_windows:
            w = AssetWindow(self.cfg.app, a, driver, config_path="config.yaml")
            self.asset_windows[a.id] = w

        self.asset_windows[a.id].show()
        self.asset_windows[a.id].raise_()
        self.asset_windows[a.id].activateWindow()


    def _on_connect_fail(self, e: Exception):
        a = self._pending_asset
        self._pending_asset = None

        if self._connect_dialog:
            self._connect_dialog.close()
            self._connect_dialog = None

        # Если пользователь нажал "Отмена" — не показываем ошибку
        if a is None:
            return

        from nord_skc.ui.errors import make_connect_error_box
        make_connect_error_box(self, a, e).exec()

    def _on_connect_thread_finished(self):
        # поток завершился — ссылки больше невалидны
        self._connect_thread = None
        self._connect_worker = None
