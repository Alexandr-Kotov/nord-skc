from __future__ import annotations

import csv
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple

import yaml
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nord_skc.config import AppConfig, AssetConfig
from nord_skc.drivers import BaseDriver
from nord_skc.model import ReadResult


@dataclass
class Sample:
    ts: float
    values: Dict[str, float]


class ValueTile(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            """
            QFrame {
                border: 1px solid #2b2b2b;
                border-radius: 14px;
                padding: 8px;
            }
            """
        )
        l = QVBoxLayout(self)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(2)

        self.name_lbl = QLabel(name)
        self.name_lbl.setStyleSheet("color: #aaa;")

        self.val_lbl = QLabel("—")
        self.val_lbl.setStyleSheet("font-size: 18px; font-weight: 700;")

        l.addWidget(self.name_lbl)
        l.addWidget(self.val_lbl)

    def set_value(self, v: float):
        self.val_lbl.setText(f"{v:.3f}")


class ColorSwatch(QLabel):
    """Маленький квадратик цвета рядом с кнопкой 'Цвет'."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(18, 18)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #555; border-radius: 4px;")
        self.set_color(QColor(255, 255, 255))

    def set_color(self, c: QColor):
        self.setStyleSheet(
            f"background: {c.name()}; border: 1px solid #555; border-radius: 4px;"
        )


class AssetWindow(QWidget):
    """
    Окно агрегата:
    - верх: "плитки" значений
    - середина: график онлайн
    - низ: кнопки запись/очистка/сохранение + список линий (показать/скрыть/цвет)
    """
    def __init__(
        self,
        app_cfg: AppConfig,
        asset: AssetConfig,
        driver: BaseDriver,
        config_path: str = "config.yaml",
    ):
        super().__init__()
        self.app_cfg = app_cfg
        self.asset = asset
        self.driver = driver
        self.config_path = config_path

        self.setWindowTitle(f"NORD SKC — {asset.id} (Флот {asset.fleet_no})")

        # --- state ---
        self.series_visible: Dict[str, bool] = {}
        self.series_color: Dict[str, QColor] = {}
        self.buffers: Dict[str, Deque[Tuple[float, float]]] = {}
        self.curves: Dict[str, pg.PlotDataItem] = {}

        self.tiles: Dict[str, ValueTile] = {}

        # UI controls per series
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.swatches: Dict[str, ColorSwatch] = {}

        self.maxlen = max(60, int(self.app_cfg.history_seconds * self.app_cfg.poll_hz))

        self.recording: bool = False
        self.session: List[Sample] = []

        self.test_mode: bool = False
        self._test_t0 = time.time()

        # Предзагрузка UI-настроек из config.yaml
        self.saved_ui = self._load_ui_settings_for_asset()

        # --- UI ---
        self.status = QLabel("—")

        # tiles
        self.tiles_host = QWidget()
        self.tiles_grid = QGridLayout(self.tiles_host)
        self.tiles_grid.setContentsMargins(0, 0, 0, 0)
        self.tiles_grid.setHorizontalSpacing(10)
        self.tiles_grid.setVerticalSpacing(10)

        # plot
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True)

        # buttons row
        self.btn_start = QPushButton("Старт записи")
        self.btn_stop = QPushButton("Стоп")
        self.btn_save = QPushButton("Сохранить CSV")
        self.btn_clear = QPushButton("Очистить график")
        self.btn_save_ui = QPushButton("Сохранить настройки")
        self.btn_test = QPushButton("Тест")

        self.btn_stop.setEnabled(False)
        self.btn_save.setEnabled(False)

        self.btn_start.clicked.connect(self.start_recording)
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_save.clicked.connect(self.save_recording)
        self.btn_clear.clicked.connect(self.clear_plot)
        self.btn_save_ui.clicked.connect(self.save_ui_settings_to_yaml)
        self.btn_test.clicked.connect(self.toggle_test_mode)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_save_ui)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_test)

        # param list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.panel = QWidget()
        self.panel_layout = QVBoxLayout(self.panel)
        self.scroll.setWidget(self.panel)

        root = QVBoxLayout(self)
        root.addWidget(self.status)
        root.addWidget(self.tiles_host)
        root.addWidget(self.plot, 1)
        root.addLayout(btn_row)
        root.addWidget(self.scroll, 1)

        # timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / max(1, self.app_cfg.poll_hz)))

        # try connect
        try:
            self.driver.connect()
        except Exception:
            pass

    # ----------------- настройки UI в YAML -----------------
    def _load_ui_settings_for_asset(self) -> Dict[str, Dict]:
        """
        Читает config.yaml и возвращает словарь:
        {
          "pressure": {"visible": True, "color": "#ff00aa"},
          ...
        }
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            for a in raw.get("assets", []) or []:
                if str(a.get("id")) == self.asset.id:
                    ui = a.get("ui", {}) or {}
                    series = ui.get("series", {}) or {}
                    # series: {key: {visible: bool, color: str}}
                    return {str(k): dict(v or {}) for k, v in series.items()}
        except Exception:
            pass
        return {}

    def save_ui_settings_to_yaml(self):
        """Сохраняет видимость/цвета линий в config.yaml -> assets[].ui.series"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

            assets = raw.get("assets", []) or []
            for a in assets:
                if str(a.get("id")) != self.asset.id:
                    continue

                ui = a.get("ui", {}) or {}
                series = ui.get("series", {}) or {}

                # записываем текущие настройки
                for key in self.series_visible.keys():
                    series.setdefault(key, {})
                    series[key]["visible"] = bool(self.series_visible.get(key, True))
                    c = self.series_color.get(key)
                    if c is not None:
                        series[key]["color"] = c.name()

                ui["series"] = series
                a["ui"] = ui
                break

            raw["assets"] = assets
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)

            self.status.setText(f"{self.asset.id}: настройки сохранены в {self.config_path}")
        except Exception as e:
            self.status.setText(f"{self.asset.id}: ошибка сохранения настроек: {e}")

    # ----------------- цвета -----------------
    def _default_color(self, index: int) -> QColor:
        hue = (index * 37) % 360
        return QColor.fromHsv(hue, 200, 230)

    def _pick_color(self, key: str):
        current = self.series_color.get(key, QColor(255, 255, 255))
        c = QColorDialog.getColor(current, self, f"Цвет линии: {key}")
        if not c.isValid():
            return
        self.series_color[key] = c
        if key in self.curves:
            self.curves[key].setPen(c)
        if key in self.swatches:
            self.swatches[key].set_color(c)

    # ----------------- серии/контролы -----------------
    def _toggle(self, key: str, state: int):
        self.series_visible[key] = bool(state)

    def _apply_saved_ui_for_series(self, key: str, default_color: QColor) -> Tuple[bool, QColor]:
        """
        Возвращает (visible, color) из сохранённых настроек,
        если их нет — default.
        """
        s = self.saved_ui.get(key, {})
        visible = bool(s.get("visible", True))
        color_str = s.get("color")
        if isinstance(color_str, str) and color_str.startswith("#") and len(color_str) in (7, 9):
            c = QColor(color_str)
            if c.isValid():
                return visible, c
        return visible, default_color

    def _ensure_series(self, values: Dict[str, float]):
        for k in values.keys():
            # tile
            if k not in self.tiles:
                tile = ValueTile(k)
                idx = len(self.tiles)
                r = idx // 4
                c = idx % 4
                self.tiles_grid.addWidget(tile, r, c)
                self.tiles[k] = tile

            # series already exists
            if k in self.series_visible:
                continue

            # buffer
            self.buffers[k] = deque(maxlen=self.maxlen)

            # default color + apply saved
            default_color = self._default_color(len(self.series_color))
            visible, color = self._apply_saved_ui_for_series(k, default_color)

            self.series_visible[k] = visible
            self.series_color[k] = color

            # UI row: checkbox + swatch + color button
            row = QHBoxLayout()

            cb = QCheckBox(k)
            cb.setChecked(visible)
            cb.stateChanged.connect(lambda state, key=k: self._toggle(key, state))
            self.checkboxes[k] = cb

            sw = ColorSwatch()
            sw.set_color(color)
            self.swatches[k] = sw

            btn_color = QPushButton("Цвет")
            btn_color.setFixedWidth(90)
            btn_color.clicked.connect(lambda _=None, key=k: self._pick_color(key))

            row.addWidget(cb, 1)
            row.addWidget(sw)
            row.addWidget(btn_color)

            self.panel_layout.addLayout(row)

            # curve
            curve = self.plot.plot([], [])
            curve.setPen(color)
            self.curves[k] = curve

        # spacer один раз
        if self.panel_layout.count() and self.panel_layout.itemAt(self.panel_layout.count() - 1).spacerItem() is None:
            self.panel_layout.addStretch(1)

    # ----------------- запись -----------------
    def start_recording(self):
        self.recording = True
        self.session = []
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.status.setText(f"{self.asset.id}: запись начата…")

    def stop_recording(self):
        self.recording = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_save.setEnabled(True)
        self.status.setText(f"{self.asset.id}: запись остановлена ({len(self.session)} точек)")

    def save_recording(self):
        if not self.session:
            self.status.setText(f"{self.asset.id}: нечего сохранять")
            return

        os.makedirs("records", exist_ok=True)
        ts0 = int(self.session[0].ts)
        path = os.path.join("records", f"{self.asset.id}_fleet{self.asset.fleet_no:02d}_{ts0}.csv")

        keys = sorted({k for s in self.session for k in s.values.keys()})

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts"] + keys)
            for s in self.session:
                row = [f"{s.ts:.3f}"] + [s.values.get(k, "") for k in keys]
                w.writerow(row)

        self.status.setText(f"{self.asset.id}: сохранено -> {path}")
        self.btn_save.setEnabled(False)

    # ----------------- очистка графика -----------------
    def clear_plot(self):
        for k in self.buffers.keys():
            self.buffers[k].clear()
        for k in self.curves.keys():
            self.curves[k].setData([], [])
        self.status.setText(f"{self.asset.id}: график очищен")

    # ----------------- тест -----------------
    def toggle_test_mode(self):
        self.test_mode = not self.test_mode
        self.btn_test.setText("Тест: ВКЛ" if self.test_mode else "Тест")
        if self.test_mode:
            self._test_t0 = time.time()

    def _read_values(self) -> ReadResult:
        if not self.test_mode:
            try:
                rr = self.driver.read_once()
            except Exception as e:
                rr = ReadResult(ok=False, values={}, error=str(e))

            # Если связи нет/оборвалась — пробуем переподключиться один раз
            if (not rr.ok) and (rr.error or "").lower().find("not connected") >= 0:
                try:
                    self.driver.close()
                except Exception:
                    pass
                try:
                    self.driver.connect()
                    rr = self.driver.read_once()
                except Exception as e:
                    rr = ReadResult(ok=False, values={}, error=str(e))

            return rr

        import math

        t = time.time() - self._test_t0
        vals = {
            "pressure": 100.0 + 10.0 * (1.0 + math.sin(t / 3)),
            "flow": 50.0 + 5.0 * (1.0 + math.sin(t / 2)),
            "temp": 20.0 + 2.0 * (1.0 + math.sin(t / 5)),
        }
        return ReadResult(ok=True, values=vals)

    # ----------------- loop -----------------
    def tick(self):
        rr = self._read_values()
        if not rr.ok:
            self.status.setText(f"{self.asset.id}: ОШИБКА: {rr.error}")
            return

        if not rr.values:
            self.status.setText(f"{self.asset.id}: ОК (нет данных)")
            return

        self._ensure_series(rr.values)
        ts = time.time()

        # tiles
        for k, v in rr.values.items():
            if k in self.tiles:
                self.tiles[k].set_value(float(v))

        # buffers
        for k, v in rr.values.items():
            if k in self.buffers:
                self.buffers[k].append((ts, float(v)))

        # recording
        if self.recording:
            self.session.append(Sample(ts=ts, values={k: float(v) for k, v in rr.values.items()}))

        # draw
        for k, buf in self.buffers.items():
            if not self.series_visible.get(k, True):
                self.curves[k].setData([], [])
                continue
            xs = [p[0] for p in buf]
            ys = [p[1] for p in buf]
            self.curves[k].setData(xs, ys)

        if not self.recording:
            self.status.setText(f"{self.asset.id}: ОК ({len(rr.values)} параметров)")
