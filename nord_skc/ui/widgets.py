from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout


class AssetCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, plate: str, vendor: str):
        super().__init__()
        self.setObjectName("assetCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)
        layout.addLayout(top)

        # ===== Left icon (fleet silhouette) =====
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setFixedSize(72, 72)
        self.icon.setStyleSheet("border-radius: 14px; border: 1px solid #3a3a3a;")

        pix_truck = QPixmap("nord_skc/assets/fleet_truck.png")
        if not pix_truck.isNull():
            self.icon.setPixmap(
                pix_truck.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            # fallback если файл не загрузился
            self.icon.setText("F")
            f = QFont()
            f.setBold(True)
            self.icon.setFont(f)

        top.addWidget(self.icon)  # ✅ ВАЖНО: иначе иконка не отобразится

        # ===== Right block =====
        right = QVBoxLayout()
        right.setSpacing(6)
        top.addLayout(right, 1)

        # Title
        self.title_lbl = QLabel(title)
        tf = QFont()
        tf.setPointSize(12)
        tf.setBold(True)
        self.title_lbl.setFont(tf)
        right.addWidget(self.title_lbl)

        # Vendor logo (JEREH / SERVA)
        self.vendor_logo = QLabel()
        self.vendor_logo.setFixedHeight(18)
        self.vendor_logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        vendor_key = (vendor or "").strip().lower()
        vendor_path = ""
        if vendor_key == "jereh":
            vendor_path = "nord_skc/assets/logo_jereh.png"
        elif vendor_key == "serva":
            vendor_path = "nord_skc/assets/logo_serva.png"

        if vendor_path:
            pix_vendor = QPixmap(vendor_path)
            if not pix_vendor.isNull():
                self.vendor_logo.setPixmap(
                    pix_vendor.scaledToHeight(16, Qt.SmoothTransformation)
                )
        right.addWidget(self.vendor_logo)

        # Plate (text)
        self.plate_lbl = QLabel(f"Госномер: {plate}")
        self.plate_lbl.setStyleSheet("color: #aaa;")
        self.plate_lbl.setWordWrap(True)
        right.addWidget(self.plate_lbl)

        # Sizing + styles
        self.setMinimumHeight(135)
        self.setStyleSheet("""
            QFrame#assetCard {
                border: 1px solid #2b2b2b;
                border-radius: 16px;
                background: transparent;
            }
            QFrame#assetCard:hover {
                border: 1px solid #4a4a4a;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
